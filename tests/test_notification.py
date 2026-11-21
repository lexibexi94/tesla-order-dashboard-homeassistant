"""Verify the push boundary without a real Companion App or Tesla account."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.tesla_order_tracker.coordinator import TrackerCoordinator


def test_demo_push_is_opt_in_and_omits_private_values():
    service = AsyncMock()
    registered = SimpleNamespace(
        has_service=lambda domain, name: (domain, name) == ("notify", "mobile_app_demo"),
        async_call=service,
    )
    event = {"changes": [{"field": "vin"}, {
        "field": "delivery_window", "after": "Sensitive delivery value",
    }]}
    coordinator = SimpleNamespace(
        entry=SimpleNamespace(options={}, entry_id="example"),
        hass=SimpleNamespace(services=registered),
        demo=True,
    )
    asyncio.run(TrackerCoordinator._async_notify(coordinator, event))
    service.assert_not_awaited()

    coordinator.entry.options["notify_service"] = "mobile_app_demo"
    asyncio.run(TrackerCoordinator._async_notify(coordinator, event))
    service.assert_awaited_once()
    domain, name, payload = service.call_args.args
    assert (domain, name) == ("notify", "mobile_app_demo")
    assert "Demo" in payload["title"]
    assert "Sensitive delivery value" not in str(payload)
    assert payload["data"]["url"] == "/tesla-order-tracker"
