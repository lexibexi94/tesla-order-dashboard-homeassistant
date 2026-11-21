"""Regression tests for order privacy, change detection and rate limits."""
import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from custom_components.tesla_order_tracker import api
from custom_components.tesla_order_tracker.coordinator import accept, retry_seconds

NOW = datetime(2040, 1, 2, 3, 4, tzinfo=UTC).isoformat()


def test_first_read_is_baseline_and_missing_fields_are_preserved():
    initial, event = accept({}, {"status": "BOOKED", "delivery_window": "7–15 March"}, NOW)
    assert event is None
    partial, event = accept(initial, {"status": "BOOKED"}, NOW)
    assert event is None
    assert partial["snapshot"]["delivery_window"] == "7–15 March"


def test_only_explicit_order_fields_and_valid_vin_are_projected():
    row = {
        "referenceNumber": "TEST123", "modelCode": "my", "orderStatus": "BOOKED",
        "name": "example person", "vin": "invalid", "deliveryWindowDisplay": "14–20 May",
    }
    assert api.project(row) == {
        "model": "Model Y", "status": "BOOKED", "delivery_window": "14–20 May",
    }


def test_vin_is_saved_without_copying_it_to_history():
    initial, _ = accept({}, {"status": "BOOKED"}, NOW)
    vin = "TESTVIN1234567890"
    new, event = accept(initial, {"vin": vin, "status": "SCHEDULED"}, NOW)
    assert new["snapshot"]["vin"] == vin
    assert {"field": "vin"} in event["changes"]
    assert vin not in str(new["history"])
    _, repeat = accept(new, {"vin": vin, "status": "SCHEDULED"}, NOW)
    assert repeat is None


def test_history_is_bounded_and_ordered():
    saved = {}
    for idx in range(50):
        saved, _ = accept(saved, {"status": str(idx)}, NOW)
    assert len(saved["history"]) == 40
    assert saved["history"][0]["changes"][0]["after"] == "49"
    assert saved["history"][-1]["changes"][0]["after"] == "10"


def test_rate_limit_never_shortens_server_cooldown():
    assert retry_seconds("7200") == 7200
    assert retry_seconds("15") == 1800
    assert retry_seconds("invalid") == 1800


def test_non_fleet_origin_rejected_before_request(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(api, "async_get_clientsession", session)
    with pytest.raises(api.FleetError, match="invalid_response"):
        asyncio.run(api.read_orders(None, "example-token", "https://not-tesla.invalid"))
    session.assert_not_called()


def test_orders_reject_ambiguous_references(monkeypatch):
    monkeypatch.setattr(api, "read_orders", AsyncMock(return_value=[
        {"referenceNumber": "TEST123"}, {"referenceNumber": "TEST123"}
    ]))
    with pytest.raises(api.FleetError, match="invalid_response"):
        asyncio.run(api.orders(None, "example-token", "unused"))
