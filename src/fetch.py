"""Idempotent raw downloads.

Sources are pinned to commit SHAs in config.yaml, so a file already on disk with
the expected minimum size is never re-downloaded: fetch is safe to run on every
pipeline invocation and on every CI build.
"""
from __future__ import annotations

import hashlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config.yaml"


class FetchError(RuntimeError):
    """A source could not be downloaded, or came back implausibly small."""


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    file: Path
    min_bytes: int

    @property
    def sha256(self) -> str:
        return sha256_file(self.file)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sources_from_config(config: dict | None = None, root: Path = REPO_ROOT) -> list[Source]:
    """Turn config.yaml's source block into Source records."""
    cfg = config if config is not None else load_config()
    return [
        Source(
            key=key,
            url=spec["url"],
            file=root / spec["file"],
            min_bytes=int(spec["min_bytes"]),
        )
        for key, spec in cfg["sources"].items()
    ]


def download(url: str, dest: Path, *, timeout: float = 60.0, attempts: int = 3) -> None:
    """Download url to dest atomically (.part then rename); retry with backoff."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp, open(tmp, "wb") as out:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            tmp.replace(dest)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(attempt)  # 1s, 2s backoff
    tmp.unlink(missing_ok=True)
    raise FetchError(f"failed to download {url} after {attempts} attempts: {last}")


def fetch_source(source: Source, *, force: bool = False) -> str:
    """Fetch one source. Returns 'downloaded' or 'skipped'."""
    if not force and source.file.exists() and source.file.stat().st_size >= source.min_bytes:
        return "skipped"
    download(source.url, source.file)
    size = source.file.stat().st_size
    if size < source.min_bytes:
        source.file.unlink(missing_ok=True)
        raise FetchError(
            f"{source.url} produced only {size} bytes (< {source.min_bytes} min); "
            "refusing to keep a truncated file"
        )
    return "downloaded"


def fetch_all(*, force: bool = False, config: dict | None = None) -> dict[str, str]:
    return {s.key: fetch_source(s, force=force) for s in sources_from_config(config)}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        for key, status in fetch_all(force="--force" in argv).items():
            print(f"[fetch] {key}: {status}")
    except FetchError as exc:
        print(f"[fetch] ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
