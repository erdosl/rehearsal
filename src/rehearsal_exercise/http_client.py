"""JSON stdin/stdout bridge used by docker exec, also usable without Docker."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(
        "http://127.0.0.1:8080" + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = build_opener(ProxyHandler({})).open(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return {"status": response.code, "body": json.load(response)}


if __name__ == "__main__":
    try:
        print(json.dumps([request(**item) for item in json.load(sys.stdin)]))
    except Exception:
        # Deliberately fixed diagnostic: urllib/driver details aren't public evidence.
        print('{"error":"local HTTP request failed"}')
        sys.exit(1)
