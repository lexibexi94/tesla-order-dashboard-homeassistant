"""Read only the documented Tesla Fleet user endpoints."""
import re

from aiohttp import ClientError, ClientTimeout, hdrs
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import OWNER_HOST, REGIONS

PUBLIC_KEYS = {
    "model": ("modelCode", "model"),
    "status": ("orderStatus",),
    "vin": ("vin",),
    "delivery_window": ("deliveryWindowDisplay",),
    "delivery_center": ("deliveryAddressTitle",),
    "appointment": ("deliveryAppointmentDate",),
    "production_status": ("productionStatus",),
}
MODEL_NAMES = {
    "m3": "Model 3", "my": "Model Y", "ms": "Model S", "mx": "Model X", "ct": "Cybertruck",
}


class FleetError(Exception):
    """Fixed diagnostic code with an optional rate limit."""

    def __init__(self, kind, retry_after=None):
        super().__init__(kind)
        self.kind = kind
        self.retry_after = retry_after


def order_reference(order):
    """Read a reference for selection without exposing it in entity state."""
    return order.get("referenceNumber") or order.get("order_number")


def project(order):
    """Return only explicit, display-safe values from the order list."""
    result = {}
    for field, keys in PUBLIC_KEYS.items():
        for key in keys:
            value = order.get(key)
            if not isinstance(value, str) or not (value := value.strip()):
                continue
            if field == "vin":
                value = value.upper()
                if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value):
                    continue
            if field == "model":
                value = MODEL_NAMES.get(value.lower(), value)
            # HA sensor state is limited to 255 characters.
            result[field] = value[:255]
            break
    return result


async def read_orders(hass, token, host):
    """Use fixed TLS origins and never forward Authorization on redirect."""
    if host != OWNER_HOST and host not in REGIONS.values():
        raise FleetError("invalid_response")
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{host}/api/1/users/orders",
            headers={hdrs.AUTHORIZATION: f"Bearer {token}"},
            timeout=ClientTimeout(total=20),
            allow_redirects=False,
        ) as response:
            if response.status == 401:
                raise FleetError("auth_required")
            if response.status in {403, 412}:
                raise FleetError("access_denied")
            if response.status == 429:
                raise FleetError("rate_limited", response.headers.get("Retry-After"))
            if response.status != 200:
                raise FleetError("api_error")
            body = await response.json()
    except (ClientError, TimeoutError, ValueError):
        raise FleetError("connection_error") from None
    if not isinstance(body, dict) or "response" not in body:
        raise FleetError("invalid_response")
    return body["response"]


async def orders(hass, token, host):
    """Return validated order records with distinct private references."""
    result = await read_orders(hass, token, host)
    if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
        raise FleetError("invalid_response")
    refs = [order_reference(row) for row in result]
    if any(not isinstance(ref, str) or not ref for ref in refs) or len(set(refs)) != len(refs):
        raise FleetError("invalid_response")
    return result
