"""Local Tesla browser sign-in with a manually returned authorization code."""
import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from aiohttp import ClientError, ClientTimeout
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation
from homeassistant.helpers.oauth2 import raise_mapped_token_error

from .api import FleetError
from .const import AUTHORIZE, DOMAIN

LOCAL_IMPLEMENTATION = "tesla_order_tracker_local"
OWNER_TOKEN = "https://auth.tesla.com/oauth2/v3/token"
REDIRECT = "tesla://auth/callback"
CLIENT = "ownerapi"
LOGIN_WINDOW = 600


class LocalLogin:
    """Create a unique PKCE challenge scoped to one configuration attempt."""

    def __init__(self):
        self.verifier = secrets.token_urlsafe(48)
        self.state = secrets.token_urlsafe(24)
        self.deadline = time.monotonic() + LOGIN_WINDOW

    def url(self):
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        params = {
            "client_id": CLIENT,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": "openid email offline_access",
            "state": self.state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTHORIZE}?{urlencode(params)}"

    def code(self, callback):
        if time.monotonic() > self.deadline:
            raise FleetError("local_login_expired")
        if not callback or len(callback) > 8192:
            raise FleetError("invalid_callback")
        try:
            url = urlsplit(callback.strip())
            if (url.scheme, url.netloc, url.path, url.fragment) != ("tesla", "auth", "/callback", ""):
                raise ValueError
            data = parse_qs(url.query, strict_parsing=True, keep_blank_values=True, max_num_fields=12)
            received_state, = data["state"]
            code, = data["code"]
            issuer, = data.get("issuer", ["https://auth.tesla.com"])
            if (
                not received_state.isascii() or not hmac.compare_digest(received_state, self.state)
                or not re.fullmatch(r"[\x21-\x7e]{1,2048}", code)
                or "error" in data
            ):
                raise ValueError
            server = urlsplit(issuer)
            if server.scheme != "https" or server.netloc != "auth.tesla.com":
                raise ValueError
        except (KeyError, ValueError):
            raise FleetError("invalid_callback") from None
        return code


async def request_token(hass, grant):
    """Call Tesla directly over verified HTTPS, without logging the response."""
    session = async_get_clientsession(hass)
    async with session.post(
        OWNER_TOKEN,
        data={**grant, "client_id": CLIENT},
        timeout=ClientTimeout(total=20),
        allow_redirects=False,
    ) as response:
        if 300 <= response.status < 400:
            raise OAuth2TokenRequestConnectionError(domain=DOMAIN)
        response.raise_for_status()
        try:
            reply = await response.json()
            if not isinstance(reply, dict):
                raise ValueError
            access, refresh = reply["access_token"], reply["refresh_token"]
            expiry = int(reply["expires_in"])
            if (
                not isinstance(access, str) or not access
                or not isinstance(refresh, str) or not refresh
                or not 1 <= expiry <= 86400
                or str(reply.get("token_type", "Bearer")).lower() != "bearer"
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError):
            raise OAuth2TokenRequestConnectionError(domain=DOMAIN) from None
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": expiry,
        }


class LocalAuth(AbstractOAuth2Implementation):
    """Expose local Tesla refresh to HA's normal OAuth session lifecycle."""

    domain = LOCAL_IMPLEMENTATION
    name = "Tesla sign-in (local)"
    service_domain = DOMAIN

    def __init__(self, hass):
        self.hass = hass

    async def async_generate_authorize_url(self, flow_id):
        raise NotImplementedError("The configuration flow owns local browser sign-in")

    async def async_resolve_external_data(self, external_data):
        raise NotImplementedError("The configuration flow owns the pasted callback")

    async def exchange(self, login, code):
        try:
            token = await request_token(self.hass, {
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT,
                "code": code,
                "code_verifier": login.verifier,
            })
        except TimeoutError:
            raise FleetError("connection_error") from None
        except ClientError as err:
            status = getattr(err, "status", None)
            if status in (400, 401, 422):
                raise FleetError("auth_required") from None
            if status == 403:
                raise FleetError("access_denied") from None
            if status == 429:
                raise FleetError("rate_limited") from None
            raise FleetError("connection_error") from None
        return {**token, "expires_at": time.time() + token["expires_in"]}

    async def _async_refresh_token(self, token):
        try:
            updated = await request_token(self.hass, {
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            })
        except TimeoutError:
            raise OAuth2TokenRequestConnectionError(domain=DOMAIN) from None
        except ClientError as err:
            raise_mapped_token_error(err, DOMAIN)
        return {**token, **updated}
