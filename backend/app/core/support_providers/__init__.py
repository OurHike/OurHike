"""The payment providers OurHike's support record can use (#1876).

One registry, so adding Open Source Collective is a module beside
`stripe.py` and one line here - see base.py for what a module owes.
`settings.support_provider` names the one new choices go to; every provider
listed here keeps receiving its own webhooks, so supporters who chose before
a switch are still recorded while they move.
"""

from app.config import settings
from app.core.support_providers.base import EventKind, ProviderEvent, SupportProvider
from app.core.support_providers.stripe import Stripe

PROVIDERS: dict[str, SupportProvider] = {provider.key: provider for provider in (Stripe(),)}


def provider_for(key: str | None) -> SupportProvider | None:
    return PROVIDERS.get(key or "")


def current_provider() -> SupportProvider | None:
    """Where new choices go, or None when the setting names nothing known."""
    return provider_for(settings.support_provider)


__all__ = ["EventKind", "PROVIDERS", "ProviderEvent", "SupportProvider", "current_provider", "provider_for"]
