"""Poll a selected order and retain the last good snapshot across failures."""
import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from time import monotonic

from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import FleetError, order_reference, orders, project
from .const import DOMAIN, FIELDS, LOGGER, POLL_INTERVAL

DEMO_STEPS = (
    {"model": "Model 3", "status": "BOOKED", "delivery_window": "10–24 March",
     "delivery_center": "Example Delivery Center"},
    {"status": "BOOKED", "delivery_window": "7–15 March"},
    {"status": "DELIVERY_SCHEDULED", "appointment": "12 March, 10:30"},
)


def retry_seconds(value):
    """Respect a Retry-After delta or HTTP date, with a 30-minute floor."""
    try:
        return max(1800, int(value))
    except (ValueError, TypeError):
        try:
            return max(1800, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 1800


def accept(previous, update, observed):
    """Merge explicit observations and capture a bounded, VIN-free timeline."""
    snapshot = previous.get("snapshot", {})
    merged = {**snapshot, **update}
    changes = [
        {"field": field, "before": snapshot.get(field), "after": merged[field]}
        for field in FIELDS
        if field in update and snapshot.get(field) != merged[field] and field != "vin"
    ]
    if update.get("vin") and update["vin"] != snapshot.get("vin"):
        changes.append({"field": "vin"})
    history = previous.get("history", [])
    event = {"at": observed, "changes": changes} if snapshot and changes else None
    if event:
        history = [event, *history][:40]
    return {**previous, "snapshot": merged, "history": history, "last_success": observed}, event


class TrackerCoordinator(DataUpdateCoordinator):
    """Keep diagnostics separate from order data and enforce a poll cooldown."""

    def __init__(self, hass, entry, oauth=None):
        self.entry = entry
        self.oauth = oauth
        self.demo = entry.data.get("demo", False)
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}", private=True)
        self.saved = {}
        self.next_poll = 0.0
        self._demo_lock = asyncio.Lock()
        super().__init__(
            hass, LOGGER, name=DOMAIN, config_entry=entry,
            update_interval=None if self.demo else POLL_INTERVAL,
        )

    async def async_load(self):
        self.saved = await self.store.async_load() or {}
        # Restore a server-mandated cooldown across a restart.
        remaining = self.saved.get("retry_until", 0) - datetime.now(UTC).timestamp()
        self.next_poll = monotonic() + max(remaining, 0)

    def data_for(self, health, checked):
        return {
            **self.saved,
            "health": health,
            "last_check": checked,
            "is_demo": self.demo,
        }

    async def _async_update_data(self):
        if self.demo:
            return await self._async_save(DEMO_STEPS[0], datetime.now(UTC).isoformat())
        if monotonic() < self.next_poll:
            return self.data or self.data_for("rate_limited", None)
        self.next_poll = monotonic() + 60
        now = datetime.now(UTC).isoformat()
        try:
            await self.oauth.async_ensure_token_valid()
            rows = await orders(
                self.hass, self.oauth.token["access_token"], self.entry.data["host"]
            )
            row = next(
                (row for row in rows if order_reference(row) == self.entry.data["reference"]),
                None,
            )
            if row is None:
                raise FleetError("order_missing")
            update = project(row)
            if not update:
                raise FleetError("invalid_response")
        except OAuth2TokenRequestReauthError:
            return self.data_for("auth_required", now)
        except (OAuth2TokenRequestError, OAuth2TokenRequestConnectionError):
            return self.data_for("connection_error", now)
        except FleetError as err:
            if err.kind == "auth_required":
                self.entry.async_start_reauth_if_available(self.hass)
            if err.kind == "rate_limited":
                wait = retry_seconds(err.retry_after)
                self.next_poll = monotonic() + wait
                self.saved = {
                    **self.saved, "retry_until": (datetime.now(UTC) + timedelta(seconds=wait)).timestamp()
                }
                await self.store.async_save(self.saved)
            return self.data_for(err.kind, now)
        return await self._async_save(update, now)

    async def async_advance_demo(self):
        """Simulate the next example update once, with a separate store."""
        async with self._demo_lock:
            step = self.saved.get("demo_step", 0) + 1
            if step >= len(DEMO_STEPS):
                return
            self.async_set_updated_data(await self._async_save(
                DEMO_STEPS[step], datetime.now(UTC).isoformat(), demo_step=step
            ))

    async def _async_save(self, update, now, **extra):
        if self.demo and self.saved and not extra:
            return self.data_for("demo", self.saved.get("last_success"))
        saved, event = accept(self.saved, update, now)
        saved.pop("retry_until", None)
        saved.update(extra)
        await self.store.async_save(saved)
        self.saved = saved
        if event:
            await self._async_notify(event)
        return self.data_for("demo" if self.demo else "ok", now)

    async def _async_notify(self, event):
        name = self.entry.options.get("notify_service", "")
        if not name.startswith("mobile_app_") or not self.hass.services.has_service("notify", name):
            return
        fields = ", ".join(FIELDS[change["field"]] for change in event["changes"])
        try:
            async with asyncio.timeout(10):
                await self.hass.services.async_call("notify", name, {
                    "title": "Tesla Order Tracker · Demo" if self.demo else "Tesla order updated",
                    "message": f"Changed: {fields}",
                    "data": {"url": f"/{DOMAIN.replace('_', '-')}", "tag": self.entry.entry_id},
                }, blocking=True)
        except (HomeAssistantError, TimeoutError):
            LOGGER.warning("The selected Companion App notification could not be sent")
