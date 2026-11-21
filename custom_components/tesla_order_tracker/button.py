"""Provide an explicit read-only refresh or a synthetic demo update."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .sensor import tracker_device


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TrackerButton(entry)])


class TrackerButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self._attr_name = "Simulate change" if self.coordinator.demo else "Refresh order"
        self._attr_unique_id = f"{entry.entry_id}_update"
        self._attr_device_info = tracker_device(entry)
        self._attr_extra_state_attributes = {"tesla_order_tracker_id": entry.entry_id}

    async def async_press(self):
        if self.coordinator.demo:
            await self.coordinator.async_advance_demo()
        else:
            await self.coordinator.async_request_refresh()
