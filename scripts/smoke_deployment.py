"""Bounded read-only deployed checks; no model calls or keys are created."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx


def rpc(client: httpx.Client, method: str, params: dict, request_id: int) -> dict:
    response = client.post(
        "/mcp", json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload or payload.get("result", {}).get("isError"):
        raise RuntimeError(f"MCP {method} failed: {payload}")
    return payload["result"]


def check(
    base_url: str,
    *,
    expected_version: str | None = None,
    key: str | None = None,
    expected_runs: list[str] | None = None,
) -> list[str]:
    headers = {"Accept": "application/json, text/event-stream"}
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=15) as client:
        response = client.get("/healthz")
        response.raise_for_status()
        health = response.json()
        if health["status"] != "ok" or (expected_version and health["version"] != expected_version):
            raise RuntimeError("deployed health/version did not match")
        client.get("/readyz").raise_for_status()
        demo = client.get("/demo")
        demo.raise_for_status()
        if "simulated" not in demo.text.lower():
            raise RuntimeError("public demo did not label simulated prices")
        rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "rsf-release-smoke", "version": "1"},
            },
            1,
        )
        tools = rpc(client, "tools/list", {}, 2)
        if "list_runs" not in {tool["name"] for tool in tools["tools"]}:
            raise RuntimeError("MCP tool discovery failed")
        runs = rpc(client, "tools/call", {"name": "list_runs", "arguments": {"limit": 10}}, 3)
        data = runs.get("structuredContent")
        if data is None:
            data = json.loads(runs["content"][0]["text"])
        if not data["runs"]:
            raise RuntimeError("public demo has no recorded runs")
        run_ids = [run["run_id"] for run in data["runs"]]
        for request_id, run_id in enumerate(expected_runs or run_ids[:1], 10):
            rpc(client, "tools/call", {"name": "get_run_report", "arguments": {"run_id": run_id}}, request_id)
        invalid = client.post(
            "/mcp", headers={"Authorization": "Bearer deliberately-invalid-smoke-token"}, json={}
        )
        if invalid.status_code != 401:
            raise RuntimeError("invalid credentials were not rejected")
        if key:
            client.headers["Authorization"] = f"Bearer {key}"
            rpc(client, "tools/call", {"name": "list_runs", "arguments": {"limit": 1}}, 4)
        return run_ids


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--version")
    parser.add_argument("--require-key", action="store_true")
    parser.add_argument("--record-runs", type=Path)
    parser.add_argument("--expect-runs", type=Path)
    args = parser.parse_args()
    key = os.environ.get("RSF_SMOKE_API_KEY")
    if args.require_key and not key:
        parser.error("RSF_SMOKE_API_KEY (a viewer key) is required")
    expected_runs = json.loads(args.expect_runs.read_text()) if args.expect_runs else None
    deadline = time.monotonic() + 90
    while True:
        try:
            run_ids = check(args.url, expected_version=args.version, key=key, expected_runs=expected_runs)
            if args.record_runs:
                args.record_runs.parent.mkdir(parents=True, exist_ok=True)
                args.record_runs.write_text(json.dumps(run_ids), encoding="utf-8")
            print("readiness, demo, MCP and authentication smoke passed")
            return
        except (httpx.HTTPError, RuntimeError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)


if __name__ == "__main__":
    main()
