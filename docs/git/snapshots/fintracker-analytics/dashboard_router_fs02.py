"""FastAPI routes for the Dashboard feature.

Read-only, hitting the Aurora PostgreSQL Read Replica.
Auth (FS-02): user ID from the Lambda authorizer context only (src/core/identity.py).

__author__ = "Van Vo"
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from ..core.database import get_session
from ..core.identity import get_user_id
from .models import FinancialOverview
from .repository import get_dashboard_overview, get_safe_to_spend

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=FinancialOverview)
async def dashboard_overview(user_id: str = Depends(get_user_id)) -> FinancialOverview:
    """Return the 3-second Dashboard financial overview.

    Args:
        user_id: From the Lambda authorizer context (FS-02).

    Returns:
        FinancialOverview with balance, income, expenses, net savings, and Safe to Spend.

    Raises:
        HTTPException 500: On database or calculation error.
    """
    async with get_session() as session:
        overview = await get_dashboard_overview(session, user_id)
        # Savings goals total is fetched from User Profile Service (caller passes it as query param)
        safe_to_spend = await get_safe_to_spend(session, user_id, Decimal("0"))

    return FinancialOverview(
        **overview,
        safe_to_spend=safe_to_spend,
    )
