"""Local fixture servers so the tests never touch the real internet."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FixtureServer:
    """HTTP server with a route table: path -> (status, body, headers)."""

    def __init__(self, routes):
        routes_ref = routes

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                status, body, headers = routes_ref.get(self.path, (404, b"not found", {}))
                if isinstance(body, str):
                    body = body.encode()
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class RawServer:
    """TCP server with a behaviour: 'reset' (close at once) or 'blackhole' (accept, never answer)."""

    def __init__(self, mode):
        self.mode = mode
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.held = []
        self.stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.sock.settimeout(0.2)
        while not self.stop:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            if self.mode == "reset":
                conn.close()
            else:
                self.held.append(conn)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop = True
        for c in self.held:
            c.close()
        self.sock.close()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
