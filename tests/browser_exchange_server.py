"""Loopback-only ResearchDesk fixture for the two-application browser roundtrip.

Serves the real Desk (persistent store, RLock, single-worker executor, exchange routes) with
only the external `search_provider` boundary mocked to deterministic synthetic hits. A hard
outbound guard makes any unexpected provider traffic fail loudly. All state lives in a
TemporaryDirectory removed on exit; no real research data or credentials are touched.

Run: python3 tests/browser_exchange_server.py
Prints exactly one readiness line on stdout:
  {"fixture": "mocked-provider-v1", "host": "127.0.0.1", "port": N, "blueprintId": "..."}
"""
import json
import signal
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import regen  # noqa: E402
import regen_desk  # noqa: E402

ALLOWED_PROVIDERS = {"pubmed"}


def mock_search_provider(provider, query, limit):
    """Deterministic labeled synthetic records for allowlisted fixture shapes only."""
    if provider not in ALLOWED_PROVIDERS:
        raise regen_desk.ProviderError(f"Fixture provider not allowed: {provider}")
    if not isinstance(query, str) or not 1 <= len(query) <= 500:
        raise regen_desk.ProviderError("Fixture query shape is not allowlisted")
    if not isinstance(limit, int) or not 1 <= limit <= 10:
        raise regen_desk.ProviderError("Fixture limit is not allowlisted")
    rows = [
        regen_desk.hit(provider, f"Synthetic fixture record {index} (mocked provider)",
                       f"https://example.invalid/mock/{provider}/{index}", "2026-01-01", pmid=str(1000 + index))
        for index in range(min(limit, 3))
    ]
    return {"fixture": "mocked-provider-v1", "provider": provider, "query": query}, rows


def main():
    temp = tempfile.TemporaryDirectory(prefix="desk-browser-fixture-")
    root = Path(temp.name)
    for name in ("DATA", "CACHE", "PROV"):
        patch.object(regen, name, root / name.lower()).start()
    patch.object(regen_desk, "fetch_json",
                 side_effect=AssertionError("Outbound provider traffic is blocked in the browser fixture")).start()
    patch.object(regen_desk, "search_provider", side_effect=mock_search_provider).start()
    desk = regen_desk.Desk(root / "desk")
    blueprint = desk.blueprint({"title": "Browser fixture blueprint (synthetic)"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), regen_desk.make_handler(desk))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(json.dumps({"fixture": "mocked-provider-v1", "host": "127.0.0.1",
                      "port": server.server_address[1], "blueprintId": blueprint["id"]}), flush=True)

    def _stop(signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        while True:
            time.sleep(1)
    finally:
        server.shutdown()
        server.server_close()
        desk.executor.shutdown(wait=True)
        temp.cleanup()


if __name__ == "__main__":
    main()
