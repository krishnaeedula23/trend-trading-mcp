"""Analytics query endpoints for trading performance tracking."""

import datetime
import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/daily")
async def daily_summary(date: str | None = None):
    """Daily performance summary."""
    target_date = date or datetime.date.today().isoformat()
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        trades = sb.table("trades").select("*").eq("date", target_date).execute()
        journal = sb.table("journal_entries").select("*").eq("date", target_date).execute()

        trade_data = trades.data or []
        wins = [t for t in trade_data if (t.get("pnl") or 0) > 0]
        losses = [t for t in trade_data if (t.get("pnl") or 0) < 0]

        return {
            "date": target_date,
            "total_trades": len(trade_data),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trade_data) if trade_data else 0,
            "total_pnl": sum(t.get("pnl", 0) or 0 for t in trade_data),
            "total_r": sum(t.get("r_multiple", 0) or 0 for t in trade_data),
            "avg_r": (sum(t.get("r_multiple", 0) or 0 for t in trade_data) / len(trade_data)) if trade_data else 0,
            "journal": journal.data[0] if journal.data else None,
            "trades": trade_data,
        }
    except RuntimeError:
        return {"date": target_date, "error": "Supabase not configured", "total_trades": 0}


@router.get("/setup-performance")
async def setup_performance(setup: str | None = None, days: int = 30):
    """Performance breakdown by setup type."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        query = sb.table("trades").select("*").gte("date", since).eq("status", "closed")
        if setup:
            query = query.eq("setup_type", setup)
        result = query.execute()

        trades = result.data or []
        # Group by setup_type
        by_setup: dict[str, list] = {}
        for t in trades:
            st = t.get("setup_type", "unknown")
            by_setup.setdefault(st, []).append(t)

        breakdown = {}
        for st, st_trades in by_setup.items():
            wins = [t for t in st_trades if (t.get("pnl") or 0) > 0]
            breakdown[st] = {
                "total": len(st_trades),
                "wins": len(wins),
                "losses": len(st_trades) - len(wins),
                "win_rate": len(wins) / len(st_trades) if st_trades else 0,
                "total_pnl": sum(t.get("pnl", 0) or 0 for t in st_trades),
                "avg_r": (sum(t.get("r_multiple", 0) or 0 for t in st_trades) / len(st_trades)) if st_trades else 0,
            }

        return {"period_days": days, "since": since, "breakdown": breakdown}
    except RuntimeError:
        return {"error": "Supabase not configured", "breakdown": {}}


@router.get("/win-rates")
async def win_rates():
    """Current win rates per setup type (for self-correcting probabilities)."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("trades").select("setup_type, pnl").eq("status", "closed").execute()

        trades = result.data or []
        by_setup: dict[str, list] = {}
        for t in trades:
            st = t.get("setup_type", "unknown")
            by_setup.setdefault(st, []).append(t)

        rates = {}
        for st, st_trades in by_setup.items():
            wins = sum(1 for t in st_trades if (t.get("pnl") or 0) > 0)
            total = len(st_trades)
            rates[st] = {
                "win_rate": wins / total if total else 0,
                "total_trades": total,
                "sufficient": total >= 30,  # enough for self-correcting probabilities
            }

        return {"win_rates": rates}
    except RuntimeError:
        return {"win_rates": {}, "error": "Supabase not configured"}


@router.get("/weekly")
async def weekly_summary(week: str | None = None):
    """Weekly performance review. Week format: YYYY-Wnn."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()

        if week:
            # Parse YYYY-Wnn format
            year, w = week.split("-W")
            week_start = datetime.date.fromisocalendar(int(year), int(w), 1)
        else:
            today = datetime.date.today()
            week_start = today - datetime.timedelta(days=today.weekday())

        week_end = week_start + datetime.timedelta(days=6)

        # Check for existing review
        existing = sb.table("weekly_reviews").select("*").eq("week_start", week_start.isoformat()).execute()
        if existing.data:
            return {"review": existing.data[0]}

        # Compute from trades
        trades = sb.table("trades").select("*").gte("date", week_start.isoformat()).lte("date", week_end.isoformat()).eq("status", "closed").execute()
        trade_data = trades.data or []
        wins = [t for t in trade_data if (t.get("pnl") or 0) > 0]

        return {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "computed": True,
            "total_trades": len(trade_data),
            "wins": len(wins),
            "losses": len(trade_data) - len(wins),
            "win_rate": len(wins) / len(trade_data) if trade_data else 0,
            "total_pnl": sum(t.get("pnl", 0) or 0 for t in trade_data),
            "total_r": sum(t.get("r_multiple", 0) or 0 for t in trade_data),
        }
    except RuntimeError:
        return {"error": "Supabase not configured"}
