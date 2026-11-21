"""Set up the order tracker and its local sidebar panel."""
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ImplementationUnavailableError,
    UnknownImplementationError,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, PANEL
from .coordinator import TrackerCoordinator

PLATFORMS = (Platform.SENSOR, Platform.BUTTON)


async def async_setup(hass, config):
    """Serve only the static panel code, with no data or external resources."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{PANEL}-assets/panel.js", str(Path(__file__).parent / "panel.js"), False)
    ])
    hass.data[DOMAIN] = set()
    return True


async def async_setup_entry(hass, entry):
    """Load the saved order, set up entities, and add the shared sidebar."""
    oauth = None
    if not entry.data.get("demo"):
        try:
            implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        except UnknownImplementationError as err:
            raise ConfigEntryAuthFailed from err
        except ImplementationUnavailableError as err:
            raise ConfigEntryNotReady from err
        oauth = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    coordinator = TrackerCoordinator(hass, entry, oauth)
    entry.runtime_data = coordinator
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entries = hass.data[DOMAIN]
    if not entries:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL,
            webcomponent_name="tesla-order-tracker-panel",
            sidebar_title="Tesla Order Tracker",
            sidebar_icon="mdi:car-clock",
            module_url=f"/{PANEL}-assets/panel.js?v=0.1.0",
            require_admin=True,
        )
    entries.add(entry.entry_id)
    return True


async def async_unload_entry(hass, entry):
    """Remove the sidebar when the last tracker is removed."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entries = hass.data[DOMAIN]
    entries.discard(entry.entry_id)
    if not entries:
        frontend.async_remove_panel(hass, PANEL)
    return True


async def async_remove_entry(hass, entry):
    """Delete the associated local history when the user removes the entry."""
    from homeassistant.helpers.storage import Store

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}", private=True).async_remove()
