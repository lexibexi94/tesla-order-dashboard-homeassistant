"""Use Home Assistant's Application Credentials store for Tesla OAuth."""
from homeassistant.components.application_credentials import AuthImplementation, AuthorizationServer

from .const import AUTHORIZE, EUROPE, TOKEN


class TeslaOrderAuth(AuthImplementation):
    """Authorize read access and receive a rotating refresh token."""

    audience = EUROPE

    @property
    def extra_authorize_data(self):
        return {
            "scope": "openid offline_access vehicle_device_data",
            "prompt_missing_scopes": "true",
        }

    @property
    def extra_token_resolve_data(self):
        return {"audience": self.audience}


async def async_get_auth_implementation(hass, auth_domain, credential):
    """Build the OAuth implementation for a user's own registered application."""
    return TeslaOrderAuth(
        hass, auth_domain, credential, AuthorizationServer(AUTHORIZE, TOKEN)
    )
