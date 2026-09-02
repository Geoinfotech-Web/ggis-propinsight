from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.state_readiness import (
    normalize_state_code,
    readiness_label,
    resolve_state_context,
    state_layer_versions,
)


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    async def execute(self, _query, params=None):  # noqa: ANN001
        self.params = params
        return _FakeResult(self.rows)


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


def test_state_code_normalization_and_labels():
    assert normalize_state_code(" fc ") == "FC"
    assert normalize_state_code("") is None
    assert readiness_label("setup_required") == "Setup required"
    assert readiness_label("ready") == "Ready"


@pytest.mark.asyncio
async def test_state_layer_versions_gate_unpublished_state_layers():
    session = _FakeSession(
        [
            SimpleNamespace(layer="poi", status="unpublished", version="unpublished"),
            SimpleNamespace(layer="roads", status="published", version="2026.09.2"),
        ]
    )
    effective = await state_layer_versions(
        session,  # type: ignore[arg-type]
        {"poi": "2026.09.1", "roads": "2026.09.1", "hazard": "live"},
        "LA",
    )

    assert "poi" not in effective
    assert effective["roads"] == "2026.09.1"
    assert effective["hazard"] == "live"
    assert effective["state:LA:poi"] == "unpublished"
    assert effective["state:LA:roads"] == "2026.09.2"


@pytest.mark.asyncio
async def test_resolve_state_context_rejects_out_of_state_point():
    session = _FakeSession(
        [
            SimpleNamespace(
                code="FC",
                name="FCT",
                readiness="ready",
                bbox=[6.75, 8.25, 7.75, 9.35],
                published=True,
                contains=False,
            )
        ]
    )

    with pytest.raises(HTTPException) as exc_info:
        await resolve_state_context(session, 3.4, 6.45, "FC")  # type: ignore[arg-type]

    assert exc_info.value.status_code == 422
    assert "outside FCT" in str(exc_info.value.detail)
