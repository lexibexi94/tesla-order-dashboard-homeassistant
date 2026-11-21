"""Regression tests for the local OAuth handoff and account data boundary."""
import asyncio
import base64
import hashlib
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import AsyncMock

import pytest

from custom_components.tesla_order_tracker import local_auth
from custom_components.tesla_order_tracker.api import FleetError


def callback_for(login, **extra):
    return local_auth.REDIRECT + "?" + urlencode(
        {"state": login.state, "code": "synthetic-code", **extra}
    )


def test_authorize_url_binds_callback_and_pkce():
    login = local_auth.LocalLogin()
    url = urlsplit(login.url())
    params = parse_qs(url.query)
    assert url.hostname == "auth.tesla.com"
    assert params["redirect_uri"] == [local_auth.REDIRECT]
    assert params["code_challenge_method"] == ["S256"]
    digest = hashlib.sha256(login.verifier.encode()).digest()
    assert params["code_challenge"] == [base64.urlsafe_b64encode(digest).decode().rstrip("=")]
    assert login.verifier not in login.url()
    assert login.code(callback_for(login)) == "synthetic-code"


@pytest.mark.parametrize("alter", [
    lambda url: url.replace("tesla://auth/", "https://auth.tesla.com/"),
    lambda url: url.replace("auth/", "auth.evil.invalid/"),
    lambda url: url + "&code=second-code",
    lambda url: url + "&state=other-flow",
    lambda url: url + "&issuer=https://example.invalid",
    lambda url: url + "#fragment",
    lambda url: url + "&error=access_denied",
])
def test_where_callback_came_from_and_which_flow_it_belongs_to(alter):
    login = local_auth.LocalLogin()
    with pytest.raises(FleetError, match="invalid_callback"):
        login.code(alter(callback_for(login)))


def test_old_or_different_sign_in_is_rejected():
    login = local_auth.LocalLogin()
    another = local_auth.LocalLogin()
    with pytest.raises(FleetError, match="invalid_callback"):
        login.code(callback_for(another))
    login.deadline = 0
    with pytest.raises(FleetError, match="local_login_expired"):
        login.code(callback_for(login))


def test_tesla_code_exchange_uses_pkce_without_a_developer_secret(monkeypatch):
    login = local_auth.LocalLogin()
    request = AsyncMock(return_value={"expires_in": 600})
    monkeypatch.setattr(local_auth, "request_token", request)
    saved = asyncio.run(local_auth.LocalAuth(None).exchange(login, "synthetic-code"))
    grant = request.await_args.args[1]
    assert grant == {
        "grant_type": "authorization_code",
        "redirect_uri": local_auth.REDIRECT,
        "code": "synthetic-code",
        "code_verifier": login.verifier,
    }
    assert saved["expires_at"] > 600
