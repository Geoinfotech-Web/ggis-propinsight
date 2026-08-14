"""Smoke tests for FCT pilot readiness (Phase B / staging sign-off)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
POINT = {"type": "Point", "coordinates": [7.3986, 8.9634]}

PROFILES = ("home_buyer", "tenant", "investor", "developer")
EXCLUDED: dict[str, set[str]] = {
    "home_buyer": {"feasibility", "tenure"},
    "tenant": {"feasibility", "tenure"},
    "investor": set(),
    "developer": set(),
}


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def main() -> int:
    failures: list[str] = []

    try:
        health = get("/health")
        if health.get("status") != "ok":
            failures.append(f"/health unexpected: {health}")
    except urllib.error.URLError as exc:
        failures.append(f"/health failed: {exc}")
        _report(failures)
        return 1

    readiness = get("/v1/meta/readiness")
    not_ready = [r["domain"] for r in readiness.get("domains", []) if not r.get("ready")]
    if not_ready:
        failures.append(f"readiness not ready: {not_ready}")

    layer_versions = readiness.get("layer_versions", {})
    for layer in ("roads", "security", "planning"):
        version = layer_versions.get(layer, "")
        if "demo" in version:
            failures.append(f"layer {layer} still demo version: {version}")

    demo_sources = [
        layer
        for layer, version in layer_versions.items()
        if version == "2026.07.demo"
    ]
    if demo_sources:
        failures.append(f"demo layer versions remain: {demo_sources}")

    for profile in PROFILES:
        try:
            result = post(
                "/v1/locations/analyze",
                {"geometry": POINT, "profile": profile, "radius_m": 5000},
            )
        except urllib.error.HTTPError as exc:
            failures.append(f"analyze {profile}: HTTP {exc.code}")
            continue

        domains: dict = result.get("domains", {})
        leaked = EXCLUDED[profile] & set(domains.keys())
        if leaked:
            failures.append(f"{profile}: excluded domains present: {sorted(leaked)}")

        if "flood" not in domains:
            failures.append(f"{profile}: missing flood domain")

        amenities = domains.get("amenities")
        if amenities and amenities.get("score") is not None:
            nearby = (amenities.get("evidence") or {}).get("nearby")
            if not nearby:
                failures.append(f"{profile}: amenities missing nearby list")

        security = domains.get("security")
        if security:
            src = (security.get("evidence") or {}).get("data_source", "")
            if "demonstration" in src.lower() or src == "demo-seed":
                failures.append(f"{profile}: security still demo-labelled: {src!r}")

    _report(failures)
    return 1 if failures else 0


def _report(failures: list[str]) -> None:
    if failures:
        print("PILOT SMOKE FAILED:")
        for item in failures:
            print(f"  - {item}")
    else:
        print(f"PILOT SMOKE PASSED ({BASE})")


if __name__ == "__main__":
    raise SystemExit(main())
