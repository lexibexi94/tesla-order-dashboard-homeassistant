"""Expose order values for Home Assistant dashboards and automations."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FIELDS


async def async_setup_entry(hass, entry, async_add_entities):
    """Create the order sensors and the diagnostics summary."""
    async_add_entities([
        TrackerSensor(entry, key, label) for key, label in FIELDS.items()
    ] + [TrackerSensor(entry, "health", "Tracker health")])


def tracker_device(entry):
    """Associate the integration entities with the tracked order."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Tesla",
        entry_type=DeviceEntryType.SERVICE,
    )


class TrackerSensor(CoordinatorEntity, SensorEntity):
    """Represent an explicit order value or the current tracker health."""

    _attr_has_entity_name = True

    def __init__(self, entry, key, label):
        super().__init__(entry.runtime_data)
        self.entity_description = SensorEntityDescription(
            key=key, name=label,
            entity_category=EntityCategory.DIAGNOSTIC if key == "health" else None,
        )
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = tracker_device(entry)
        self.entry_id = entry.entry_id

    @property
    def native_value(self):
        if self.entity_description.key == "health":
            return self.coordinator.data["health"]
        return self.coordinator.data.get("snapshot", {}).get(self.entity_description.key)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key == "vin":
            return {"tesla_order_tracker_id": self.entry_id, "tesla_order_role": "vin"}
        if self.entity_description.key != "health":
            return None
        data = self.coordinator.data
        return {
            "tesla_order_tracker_id": self.entry_id,
            "tesla_order_role": "health",
            "is_demo": data["is_demo"],
            "order": {k: v for k, v in data.get("snapshot", {}).items() if k != "vin"},
            "history": data.get("history", []),
            "last_check": data.get("last_check"),
            "last_success": data.get("last_success"),
        }
