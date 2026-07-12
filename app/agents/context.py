"""Fetch pre-call context for inbound agents from the Karigaar backend."""

from __future__ import annotations

import httpx
from loguru import logger

from app.agents.customer_inbound import CallerContext
from app.core.config import settings


def _normalize_contact_number(raw: str | None) -> str:
    """Strip to digits for the caller-context API (Exotel often prefixes 0)."""
    if not raw:
        return ""
    digits = "".join(c for c in raw if c.isdigit())
    # Drop leading 0 from Indian local formats like 09325617129
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


async def fetch_caller_context(
    contact_number: str | None,
    *,
    agent_id: str | None = None,
) -> CallerContext:
    """GET /caller-context?contact_number=&agent_id= with bearer auth.

    On any failure, fall back to new_customer so the call can still proceed.
    """
    agent = (agent_id or settings.customer_inbound_agent_id).strip()
    number = _normalize_contact_number(contact_number)
    if not number:
        logger.warning("caller-context: empty contact_number; defaulting to new_customer")
        return CallerContext(scenario="new_customer")

    url = settings.caller_context_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.caller_context_token}"}
    params = {"contact_number": number, "agent_id": agent}

    logger.info(f"caller-context fetch: url={url} contact_number={number!r} agent_id={agent!r}")
    try:
        async with httpx.AsyncClient(timeout=settings.caller_context_timeout_secs) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 — call must continue even if context fails
        logger.exception(f"caller-context fetch failed ({exc}); defaulting to new_customer")
        return CallerContext(scenario="new_customer")

    if not isinstance(payload, dict):
        logger.error(f"caller-context unexpected payload type={type(payload)!r}")
        return CallerContext(scenario="new_customer")

    ctx = CallerContext.from_api(payload)
    logger.info(
        f"caller-context resolved: scenario={ctx.scenario!r} "
        f"customer_name={ctx.customer_name!r} service_type={ctx.service_type!r} "
        f"worker_name={ctx.worker_name!r}"
    )
    return ctx
