"""Set up a demo or connect the fleet API and select an active order."""
import hashlib

import probatio
from homeassistant.config_entries import SOURCE_REAUTH, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    SelectOptionDict, SelectSelector, SelectSelectorConfig,
    TextSelector, TextSelectorConfig, TextSelectorType,
)

from .api import FleetError, order_reference, orders, project
from .const import DOMAIN, LOGGER, OWNER_HOST, REGIONS
from .local_auth import LOCAL_IMPLEMENTATION, LocalAuth, LocalLogin


class ConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Use the built-in OAuth callback and credential storage."""

    DOMAIN = DOMAIN

    @property
    def logger(self):
        return LOGGER

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_menu(step_id="user", menu_options=["local", "demo", "fleet"])
        return await self.async_step_fleet()

    async def async_step_local(self, user_input=None):
        self._local_login = LocalLogin()
        return self._local_form()

    def _local_form(self, error=None):
        return self.async_show_form(
            step_id="local_callback",
            description_placeholders={"tesla_login_url": self._local_login.url()},
            data_schema=probatio.Schema({
                probatio.Required("callback"): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }),
            errors={"base": error} if error else None,
        )

    async def async_step_local_callback(self, user_input=None):
        if user_input is None:
            return self._local_form()
        attempt = self._local_login
        try:
            code = attempt.code(user_input["callback"])
        except FleetError as err:
            if err.kind == "local_login_expired":
                self._local_login = LocalLogin()
            return self._local_form(err.kind)

        # A valid callback is single-use even if Tesla or the order read fails.
        self._local_login = LocalLogin()
        try:
            token = await LocalAuth(self.hass).exchange(attempt, code)
        except FleetError as err:
            return self._local_form(err.kind)
        self._host = OWNER_HOST
        return await self.async_oauth_create_entry({
            "auth_implementation": LOCAL_IMPLEMENTATION, "token": token,
        })

    async def async_step_demo(self, user_input=None):
        await self.async_set_unique_id("demo")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Tesla Order Tracker · Demo", data={"demo": True})

    async def async_step_fleet(self, user_input=None):
        if user_input is not None:
            self._host = REGIONS[user_input["region"]]
            return await self.async_step_fleet_credentials()
        return self.async_show_form(
            step_id="fleet",
            data_schema=probatio.Schema({
                probatio.Required("region", default="eu"): SelectSelector(
                    SelectSelectorConfig(options=[
                        SelectOptionDict(value="eu", label="Europe / Middle East / Africa"),
                        SelectOptionDict(value="na", label="North America / Asia-Pacific"),
                    ])
                )
            }),
        )

    async def async_step_fleet_credentials(self, user_input=None):
        implementations = await config_entry_oauth2_flow.async_get_implementations(self.hass, DOMAIN)
        choices = {key: item for key, item in implementations.items() if key != LOCAL_IMPLEMENTATION}
        if not choices:
            return self.async_abort(reason="missing_credentials")
        if user_input is not None and user_input["implementation"] in choices:
            self.flow_impl = choices[user_input["implementation"]]
            return await self.async_step_auth()
        if len(choices) == 1:
            self.flow_impl = next(iter(choices.values()))
            return await self.async_step_auth()
        return self.async_show_form(
            step_id="fleet_credentials",
            data_schema=probatio.Schema({
                probatio.Required("implementation"): probatio.In({
                    key: item.name for key, item in choices.items()
                }),
            }),
        )

    async def async_generate_authorize_url(self):
        self.flow_impl.audience = self._host
        return await super().async_generate_authorize_url()

    async def async_step_reauth(self, entry_data):
        if entry_data["auth_implementation"] == LOCAL_IMPLEMENTATION:
            return await self.async_step_local()
        self._host = entry_data["host"]
        return await self.async_step_fleet_credentials(
            {"implementation": entry_data["auth_implementation"]}
        )

    async def async_oauth_create_entry(self, data):
        if not data.get("token", {}).get("refresh_token"):
            return self.async_abort(reason="offline_access_missing")
        token = data["token"]["access_token"]
        try:
            host = self._host
            listing = await orders(self.hass, token, host)
        except FleetError as err:
            return self.async_abort(reason=err.kind)
        self._fleet_data = {**data, "host": host}
        self._choices = {order_reference(row): row for row in listing}
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            if (ref := entry.data["reference"]) not in self._choices:
                return self.async_abort(reason="order_missing")
            await self.async_set_unique_id(self._order_id(ref))
            self._abort_if_unique_id_mismatch(reason="order_missing")
            return self.async_update_reload_and_abort(
                entry, data={**self._fleet_data, "reference": ref}
            )
        if not listing:
            return self.async_abort(reason="no_orders")
        if len(listing) == 1:
            return await self.async_step_order({"reference": next(iter(self._choices))})
        return await self.async_step_order()

    @staticmethod
    def _order_id(ref):
        return hashlib.sha256(ref.encode()).hexdigest()

    async def async_step_order(self, user_input=None):
        if user_input:
            ref = user_input["reference"]
            await self.async_set_unique_id(self._order_id(ref))
            self._abort_if_unique_id_configured()
            model = project(self._choices[ref]).get("model", "Tesla")
            return self.async_create_entry(
                title=f"Tesla Order Tracker · {model}",
                data={**self._fleet_data, "reference": ref},
            )
        return self.async_show_form(
            step_id="order",
            data_schema=probatio.Schema({
                probatio.Required("reference"): SelectSelector(SelectSelectorConfig(
                    options=[SelectOptionDict(
                        value=ref, label=f"{project(row).get('model', 'Tesla')} · {ref}"
                    ) for ref, row in self._choices.items()]
                )),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TrackerOptions()


class TrackerOptions(OptionsFlow):
    """Choose a local Home Assistant companion push destination."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="", data={"notify_service": user_input["notify_service"]}
            )
        services = sorted(
            name for name in self.hass.services.async_services().get("notify", {})
            if name.startswith("mobile_app_")
        )
        current = self.config_entry.options.get("notify_service")
        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema({
                probatio.Required(
                    "notify_service", default=current if current in services else "off"
                ): SelectSelector(SelectSelectorConfig(options=[
                    SelectOptionDict(value="off", label="—"), *[
                        SelectOptionDict(value=name, label=name.removeprefix("mobile_app_").replace("_", " "))
                        for name in services
                    ],
                ])),
            }),
        )
