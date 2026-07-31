"""Serve data/processed/ the way R2 will, for testing the client locally.

Point the client at this instead of a real bucket:

    python serve_processed.py                     # http://localhost:8787
    cd ../client && VITE_DATA_BASE_URL=http://localhost:8787 npm run build
    npm run preview

Two things this does that http.server does NOT, both of which the client
depends on:

  1. Byte ranges. PMTiles reads an archive by range - a header, then a
     directory, then individual tiles - and never downloads the whole file to
     render a tile. Python's SimpleHTTPRequestHandler ignores Range entirely
     and answers 200 with the full body, so a 1.18 GB archive would be pulled
     in full for one tile and pmtiles would reject the response anyway.

  2. CORS, including exposing Content-Range. The client is served from one
     origin and the data from another, which is also true in production, so
     testing without it would pass locally and fail on the first real deploy.

This is a development tool. It is single-threaded, does no authentication and
should not be exposed beyond localhost.
"""

import argparse
import re
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parent / "data" / "processed"

# "bytes=0-1023", "bytes=1024-" - the two forms pmtiles actually sends. A
# suffix range ("bytes=-500") is valid HTTP but never sent here, so it is
# rejected rather than half-implemented.
RANGE_PATTERN = re.compile(r"^bytes=(\d+)-(\d*)$")

CHUNK_SIZE = 1 << 20


class RangeRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Range")
        # Without this the browser hides Content-Range from the page even
        # though the response carried it, and pmtiles cannot tell whether its
        # range was honoured.
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        range_header = self.headers.get("Range")
        if range_header is None:
            super().do_GET()
            return

        match = RANGE_PATTERN.match(range_header.strip())
        if match is None:
            self.send_error(400, "Malformed Range header")
            return

        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404, "Not found")
            return

        size = path.stat().st_size
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else size - 1
        end = min(end, size - 1)

        if start >= size:
            # 416 has to carry the real size, since that is how a client that
            # guessed too far learns what to ask for instead.
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return

        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--directory", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()

    if not args.directory.is_dir():
        raise SystemExit(f"No such directory: {args.directory}\nRun the export scripts first.")

    handler = partial(RangeRequestHandler, directory=str(args.directory))
    server = HTTPServer(("127.0.0.1", args.port), handler)

    print(f"Serving {args.directory} at http://localhost:{args.port}")
    print("Point the client at it with VITE_DATA_BASE_URL, then Ctrl-C here when done.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
