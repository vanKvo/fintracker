"""Thin REST clients for the Analytics, Ledger and User Profile services.

D4 / tool rule in tools.py's module docstring: the AI assistant reads no database. Data owned
by another service is read via that service's own REST API, never by querying its database
directly or duplicating its SQL here.

Shape follows fintracker-data-pipeline's existing ledger_client.py precedent — typed
result (tools/schemas.py), explicit timeout, raise_for_status(), translated domain exception —
but uses httpx instead of requests because this service is async end-to-end
(async FastAPI); a synchronous requests call here would block
the event loop.

CLAUDE.md Exception Handling / app doc 4.8: never let a raw httpx exception or an upstream response
body reach a tool's return value or propagate outward — log detail server-side and raise a
DependencyError (tools/exceptions.py) with a generic message and the cause chained.

FS-02: every call is SigV4-signed (IAM authentication) over the exact URL sent, query string
included, so a user ID passed between services is trusted only on an IAM-verified call.

XS-CTX-04: calls to Analytics, the Ledger and User Profile carry the caller's verified context —
user ID, timezone and currency — as X-Internal-User-Id / X-User-Timezone / X-User-Currency.

__author__ = "Van Vo"
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TypeVar
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, TypeAdapter

from ..core.observability import logger
from ..core.schemas import PeriodKey, UserContext
from ..core.sigv4 import sign_headers
from ..core.user_context import forwarded_headers
from .exceptions import AnalyticsClientError, LedgerClientError, UserProfileClientError
from .schemas import (
    MAX_TRANSACTION_ROWS,
    CategoryReport,
    LedgerBudget,
    LedgerTransactionRow,
    MonthlyCashFlowReport,
    SavingsGoalProgress,
    SavingsGoalRow,
    SpendingPace,
    ToolTransaction,
)

_ANALYTICS_INTERNAL_API_URL = os.environ.get("ANALYTICS_INTERNAL_API_URL", "")
_LEDGER_API_URL = os.environ.get("LEDGER_API_URL", "")
_USER_PROFILE_API_URL = os.environ.get("USER_PROFILE_API_URL", "")

_TIMEOUT_SECONDS = 10.0

_Model = TypeVar("_Model", bound=BaseModel)
_TRANSACTION_ROWS = TypeAdapter(list[LedgerTransactionRow])
_GOAL_ROWS = TypeAdapter(list[SavingsGoalRow])


def _signed_get_args(
    url: str, headers: dict[str, str], params: Mapping[str, object] | None = None
) -> tuple[str, dict[str, str]]:
    """The full URL and signed headers for a GET; the query string is part of the signature."""
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("Service base URL is not configured.")
    full_url = f"{url}?{urlencode(params)}" if params else url
    return full_url, sign_headers("GET", full_url, headers)


async def _analytics_get(
    path: str, ctx: UserContext, model: type[_Model], params: Mapping[str, object] | None = None,
) -> _Model:
    """GET an Analytics internal route; the user's context travels in headers on a signed call."""
    try:
        url, headers = _signed_get_args(
            f"{_ANALYTICS_INTERNAL_API_URL}/internal/v1/analytics{path}", forwarded_headers(ctx), params
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        return model.model_validate(response.json())
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:  # ValidationError is a ValueError
        logger.error("Analytics internal call failed", path=path, error_type=type(exc).__name__)
        raise AnalyticsClientError("Unable to retrieve data from the Analytics service.") from exc


async def get_spending_pace(ctx: UserContext) -> SpendingPace:
    """Spending so far this month vs. the same days last month — GET /internal/v1/analytics/dashboard/spending-pace.

    Dashboard totals (balance, income, safe to spend) are the Ledger's, not Analytics' (ADR-013).
    """
    return await _analytics_get("/dashboard/spending-pace", ctx, SpendingPace)


async def get_category_report(ctx: UserContext, period: PeriodKey) -> CategoryReport:
    """Spending by category vs. the comparison period — GET /internal/v1/analytics/reports/categories?period=."""
    return await _analytics_get("/reports/categories", ctx, CategoryReport, {"period": period.value})


async def get_monthly_cash_flow(ctx: UserContext) -> MonthlyCashFlowReport:
    """Income, expenses and net for each of the last 12 complete months — GET /internal/v1/analytics/reports/monthly-cash-flow."""
    return await _analytics_get("/reports/monthly-cash-flow", ctx, MonthlyCashFlowReport)


async def list_transactions(
    ctx: UserContext,
    *,
    account_id: str | None = None,
    merchant: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = 0,
    size: int = MAX_TRANSACTION_ROWS,
) -> list[ToolTransaction]:
    """List a user's transactions — GET /api/v1/ledger/transactions.

    At most MAX_TRANSACTION_ROWS rows, with date, merchant, category and amount only (AI-CHAT-05),
    whatever `size` the caller asks for.

    Forwards the caller's verified context as `X-Internal-User-Id` (the header the Ledger's
    UserContextFilter already requires of every caller), `X-User-Timezone` and `X-User-Currency`.
    `ctx` must already be the caller's verified context — never an LLM-supplied value.
    """
    size = max(1, min(size, MAX_TRANSACTION_ROWS))
    params = {
        k: v
        for k, v in {
            "accountId": account_id,
            "merchant": merchant,
            "dateFrom": date_from,
            "dateTo": date_to,
            "category": category,
            "status": status,
            "page": max(0, page),
            "size": size,
        }.items()
        if v is not None
    }

    try:
        url, headers = _signed_get_args(
            f"{_LEDGER_API_URL}/api/v1/ledger/transactions", forwarded_headers(ctx), params
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        rows = _TRANSACTION_ROWS.validate_python(response.json())
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.error("Ledger transactions call failed", error_type=type(exc).__name__)
        raise LedgerClientError("Unable to retrieve transactions from the Ledger service.") from exc

    return [ToolTransaction(date=r.tx_date, merchant=r.merchant, category=r.category, amount=r.amount)
            for r in rows[:size]]


async def get_budget_status(ctx: UserContext, month: str) -> LedgerBudget | None:
    """Return a user's budget for one month — GET /api/v1/ledger/budgets?month=.

    Args:
        ctx: Verified caller context, forwarded as X-Internal-User-Id / X-User-Timezone / X-User-Currency.
        month: ISO date for any day in the target month, e.g. "2026-03-01".

    Returns:
        The budget, or None if the user has no budget for that month.
    """
    try:
        url, headers = _signed_get_args(
            f"{_LEDGER_API_URL}/api/v1/ledger/budgets", forwarded_headers(ctx), {"month": month}
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return LedgerBudget.model_validate(response.json())
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.error("Ledger budget call failed", error_type=type(exc).__name__)
        raise LedgerClientError("Unable to retrieve budget status from the Ledger service.") from exc


async def get_savings_goal_progress(ctx: UserContext) -> list[SavingsGoalProgress]:
    """Return a user's savings goals with progress computed here — GET /profile/internal/goals.

    User Profile's internal goals route (app/goals/handlers.py:internal_goals_handler) checks the
    signature's role against its caller allow-list and reads the user from the forwarded context.
    """
    try:
        url, headers = _signed_get_args(f"{_USER_PROFILE_API_URL}/profile/internal/goals", forwarded_headers(ctx))
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
        rows = _GOAL_ROWS.validate_python(response.json())
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.error("User Profile goals call failed", error_type=type(exc).__name__)
        raise UserProfileClientError("Unable to retrieve savings goals from the User Profile service.") from exc

    return [
        SavingsGoalProgress(
            goal_id=row.goal_id, goal_name=row.goal_name, target_amount=row.target_amount,
            current_amount=row.current_amount, deadline=row.deadline,
            progress_percentage=round(float(row.current_amount / row.target_amount * 100), 2)
            if row.target_amount > 0 else 0.0,
        )
        for row in rows
    ]

