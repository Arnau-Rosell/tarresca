"""Serve ``docs/`` locally, with HTTP range requests so videos play in Safari.

Python's built-in ``http.server`` ignores ``Range`` headers. Chrome copes, but
Safari (including iPhone) refuses to play video without them.

Usage:
    python3 serve.py [port]
"""

from __future__ import annotations

import os
import re
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO

SITE_DIR = Path(__file__).resolve().parent / "docs"
DEFAULT_PORT = 8002
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")
CHUNK_SIZE = 64 * 1024


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """Static file handler that also answers single-range requests."""

    range_remaining: int | None = None

    def send_head(self) -> BinaryIO | None:
        """Serve a byte range when asked for one, else defer to the base class."""
        match = RANGE_PATTERN.match(self.headers.get("Range", "").strip())
        path = Path(self.translate_path(self.path))
        if not match or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        start_text, end_text = match.groups()
        if start_text:
            start = int(start_text)
            end = min(int(end_text), size - 1) if end_text else size - 1
        else:
            start, end = max(size - int(end_text or 0), 0), size - 1
        if start > end or start >= size:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        file = path.open("rb")
        file.seek(start)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self.range_remaining = end - start + 1
        return file

    def copyfile(self, source: BinaryIO, outputfile: BinaryIO) -> None:
        """Copy only the requested range when one is being served."""
        remaining = self.range_remaining
        if remaining is None:
            super().copyfile(source, outputfile)
            return
        while remaining > 0:
            chunk = source.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self.range_remaining = None

    def end_headers(self) -> None:
        """Advertise range support on every response."""
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def main() -> None:
    """Start the server on the port given as the first argument, or 8002."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    handler = partial(RangeRequestHandler, directory=os.fspath(SITE_DIR))
    with ThreadingHTTPServer(("", port), handler) as server:
        print(f"Serving {SITE_DIR.name}/ at http://localhost:{port}/")
        server.serve_forever()


if __name__ == "__main__":
    main()
