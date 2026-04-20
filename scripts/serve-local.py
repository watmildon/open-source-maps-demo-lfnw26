#!/usr/bin/env python3
"""
Local dev server with HTTP Range request support for PMTiles.
Python's built-in http.server doesn't support Range requests,
which PMTiles requires to fetch tile data efficiently.
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler that supports Range requests for serving PMTiles."""

    def do_GET(self):
        # Check for Range header
        range_header = self.headers.get("Range")
        if range_header is None:
            # No range request — serve normally
            super().do_GET()
            return

        # Parse range header (e.g., "bytes=0-511")
        try:
            path = self.translate_path(self.path)
            if not os.path.isfile(path):
                self.send_error(404)
                return

            file_size = os.path.getsize(path)
            range_spec = range_header.replace("bytes=", "")
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1

            if start >= file_size or end >= file_size:
                self.send_error(416, "Range Not Satisfiable")
                return

            content_length = end - start + 1

            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(content_length))
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(path, "rb") as f:
                f.seek(start)
                self.wfile.write(f.read(content_length))

        except (ValueError, IOError) as e:
            self.send_error(500, str(e))

    def end_headers(self):
        # Add CORS headers for all responses
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length, Accept-Ranges")
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3721
    root = Path(__file__).resolve().parent.parent / "docs"
    os.chdir(root)

    print(f"Serving at: http://localhost:{port}/")
    print(f"Root: {root}")
    print("Press Ctrl+C to stop\n")

    server = HTTPServer(("", port), RangeRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
