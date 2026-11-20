"""fetch: sha256, idempotency, and truncation guards — no network required."""
from pathlib import Path

import pytest

from src.fetch import FetchError, Source, fetch_source, sha256_file


def _source(tmp_path: Path, url: str, *, min_bytes: int = 5) -> Source:
    return Source(key="fixture", url=url, file=tmp_path / "fixture.csv", min_bytes=min_bytes)


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    small = tmp_path / "small.bin"
    small.write_bytes(b"energy")
    assert sha256_file(small) == hashlib.sha256(b"energy").hexdigest()

    # larger than one read chunk (1 MiB) to exercise the streaming path
    big = tmp_path / "big.bin"
    payload = (b"0123456789abcdef" * (1 << 16))  # 1 MiB
    big.write_bytes(payload)
    assert sha256_file(big) == hashlib.sha256(payload).hexdigest()


def test_fetch_downloads_then_skips(tmp_path: Path) -> None:
    origin = tmp_path / "origin.csv"
    origin.write_text("country,year\nWorld,2023\n", encoding="utf-8")
    src = _source(tmp_path, origin.as_uri())

    assert fetch_source(src) == "downloaded"
    assert src.file.read_text(encoding="utf-8").startswith("country,year")

    # second call must be a no-op (idempotent)
    mtime = src.file.stat().st_mtime_ns
    assert fetch_source(src) == "skipped"
    assert src.file.stat().st_mtime_ns == mtime


def test_fetch_force_redownloads(tmp_path: Path) -> None:
    origin = tmp_path / "origin.csv"
    origin.write_text("a,b\n1,2\n", encoding="utf-8")
    src = _source(tmp_path, origin.as_uri())
    assert fetch_source(src) == "downloaded"
    assert fetch_source(src, force=True) == "downloaded"


def test_fetch_rejects_truncated_download(tmp_path: Path) -> None:
    origin = tmp_path / "origin.csv"
    origin.write_text("tiny", encoding="utf-8")
    src = _source(tmp_path, origin.as_uri(), min_bytes=10_000)

    with pytest.raises(FetchError, match="truncated"):
        fetch_source(src)
    # a rejected download must not linger where the loader could pick it up
    assert not src.file.exists()
