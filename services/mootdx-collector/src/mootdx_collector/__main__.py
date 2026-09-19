from __future__ import annotations

import argparse
import fcntl
import json
import secrets
import signal
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mootdx_collector.collector import Collector, active_session
from mootdx_collector.config import Settings
from mootdx_collector.provider import Provider, discover
from mootdx_collector.spool import Spool
from mootdx_collector.transport import Sender


def status(spool: Spool) -> dict:
    latest = spool.get("latest_round")
    return {"queue": spool.stats(), "runtime": spool.get("runtime"), "latest_round": latest}


def serve_health(settings: Settings, spool: Spool) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            code, body = 200, {"status": "alive"}
            if self.path == "/status":
                token = self.headers.get("X-Service-Token", "")
                if not settings.service_token or not secrets.compare_digest(
                    token,
                    settings.service_token,
                ):
                    code, body = 401, {"error": "unauthorized"}
                else:
                    body = status(spool)
            elif self.path != "/health/live":
                code, body = 404, {"error": "not_found"}
            encoded = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer((settings.health_host, settings.health_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["once", "run", "status"])
    args = parser.parse_args()
    settings = Settings.from_env()
    spool = Spool(settings.spool_path)
    if args.command == "status":
        print(json.dumps(status(spool), ensure_ascii=False))
        spool.close()
        return 0
    if not settings.service_token:
        raise ValueError("MARKET_INGEST_SERVICE_TOKEN is required")
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_args: stop.set())
    lock = settings.spool_path.with_suffix(".lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    server = serve_health(settings, spool) if args.command == "run" else None
    sender = Sender(settings, spool)

    def deliver():
        while not stop.is_set():
            if not sender.send_one():
                stop.wait(sender.delay)

    sending = threading.Thread(target=deliver, daemon=True)
    sending.start()
    collector = None
    try:
        previous = spool.get("active_round")
        if previous:
            spool.set("interrupted_round", previous)
        spool.set("runtime", {"state": "probing"})
        nodes = []
        while not stop.is_set():
            nodes = discover(settings)
            if nodes or args.command == "once":
                break
            spool.set("runtime", {"state": "no_healthy_tdx_node"})
            stop.wait(30)
        if not nodes:
            print(json.dumps({"status": "no_healthy_tdx_node", "queue": spool.stats()}))
            return 2
        spool.set(
            "runtime",
            {
                "state": "running",
                "nodes": [{"alias": node.alias, "latency_ms": node.latency_ms} for node in nodes],
            },
        )
        collector = Collector(settings, spool, Provider(settings, nodes))
        while not stop.is_set():
            started = time.monotonic()
            report = collector.once()
            print(
                json.dumps(
                    {
                        key: report.get(key)
                        for key in (
                            "round_id",
                            "status",
                            "expected",
                            "received",
                            "duration_ms",
                        )
                    }
                ),
                flush=True,
            )
            if args.command == "once":
                deadline = time.monotonic() + 30
                while spool.stats()["pending"] and time.monotonic() < deadline:
                    if stop.wait(0.25):
                        break
                print(json.dumps(status(spool), ensure_ascii=False))
                return 0
            interval = (
                settings.sweep_seconds
                if active_session(datetime.now(UTC))
                else settings.closed_seconds
            )
            stop.wait(max(0.1, interval - (time.monotonic() - started)))
        return 0
    finally:
        stop.set()
        if collector:
            collector.close()
        sending.join(timeout=20)
        sender.close()
        if server:
            server.shutdown()
            server.server_close()
        spool.set("runtime", {"state": "stopped", "at": datetime.now(UTC).isoformat()})
        spool.close()
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
