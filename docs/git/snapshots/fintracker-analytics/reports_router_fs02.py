"""FastAPI routes for the Reports feature.

Read-only, hitting the Aurora PostgreSQL Read Replica.
Auth (FS-02): user ID from the Lambda authorizer context only (src/core/identity.py).

__author__ = "Van Vo"
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..core.database import get_session
from ..core.identity import get_user_id
from .models import SpendingReport
from .repository import get_monthly_trend, get_spending_report

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/reports/spending", response_model=SpendingReport)
async def spending_report(
    user_id: str = Depends(get_user_id),
    date_from: str = Query(..., description="ISO date YYYY-MM-DD"),
    date_to: str = Query(..., description="ISO date YYYY-MM-DD"),
) -> SpendingReport:
    """Return category spending breakdown for pie chart and period summary.

    Args:
        user_id: From the Lambda authorizer context (FS-02).
        date_from: Report start date.
        date_to: Report end date.

    Returns:
        SpendingReport with per-category breakdowns and totals.
    """
    async with get_session() as session:
        return await get_spending_report(session, user_id, date_from, date_to)


@router.get("/reports/trend")
async def cash_flow_trend(
    user_id: str = Depends(get_user_id),
    months: int = Query(default=12, ge=1, le=24),
) -> JSONResponse:
    """Return month-over-month cash flow trend for line graph visualization.

    Args:
        user_id: From the Lambda authorizer context (FS-02).
        months: Number of months to look back (1-24).

    Returns:
        List of monthly income/expense/budget data points.
    """
    async with get_session() as session:
        trend = await get_monthly_trend(session, user_id, months)
    return JSONResponse(content=[t.model_dump(mode="json") for t in trend])
