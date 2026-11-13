"""Local exercise HTTP server. This bounded synthetic service is not production hosting."""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID

import psycopg

from rehearsal_orders import db
from rehearsal_orders.domain import order_input


class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # socketserver's default prints arbitrary exception text and connection addresses.
        print("order request failed", file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No request bodies, credentials, connection details or raw exceptions in logs.

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path == "/health/live":
                return self.reply(200, {"application": "available"})
            if self.path == "/health/ready":
                ok = db.ready()
                return self.reply(200 if ok else 503, {"database": "ready" if ok else "unready"})
            if self.path.startswith("/orders/"):
                order = db.get_order(str(UUID(self.path.removeprefix("/orders/"))))
                return self.reply(200 if order else 404, order or {"error": "not found"})
            return self.reply(404, {"error": "not found"})
        except (ValueError, TypeError):
            return self.reply(400, {"error": "invalid order ID"})
        except (psycopg.Error, OSError, KeyError):
            return self.reply(503, {"error": "database unavailable"})

    def do_POST(self):
        if self.path != "/orders":
            return self.reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                return self.reply(400, {"error": "bounded JSON body required"})
            order = order_input(json.loads(self.rfile.read(length)))
            result, created = db.create_order(order)
            return self.reply(201 if created else 200, result)
        except (ValueError, TypeError, OverflowError):
            return self.reply(400, {"error": "invalid or conflicting order"})
        except (psycopg.Error, OSError, KeyError):
            return self.reply(503, {"error": "database unavailable"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = Server((args.bind, args.port), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
