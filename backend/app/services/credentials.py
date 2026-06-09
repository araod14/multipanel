"""CSPRNG generation of per-instance Freqtrade api_server credentials."""

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class InstanceCredentials:
    """Freshly generated secrets for one Freqtrade instance's REST API.

    These are injected into the container as ``FREQTRADE__API_SERVER__*`` env vars
    and stored encrypted on the :class:`BotInstance` row.
    """

    api_username: str
    api_password: str
    jwt_secret: str
    ws_token: str


def generate_instance_credentials(username: str) -> InstanceCredentials:
    """Generate strong random api_server credentials for a user's instance.

    :param username: used only to derive a readable api username prefix.
    """
    return InstanceCredentials(
        api_username=f"cp_{username}",
        api_password=secrets.token_urlsafe(24),
        jwt_secret=secrets.token_hex(32),
        ws_token=secrets.token_urlsafe(24),
    )
