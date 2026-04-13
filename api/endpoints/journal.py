"""Journal entries and mid-session notes endpoints."""

import datetime
import logging
from typing import Any

from fastapi import APIRouter

from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["journal"])

VALID_NOTE_CATEGORIES = ["observation", "emotional", "setup", "lesson"]


class JournalCreate(BaseModel):
    date: str | None = None  # defaults to today
    emotional_state: str | None = None
    what_worked: str | None = None
    what_didnt: str | None = None
    lessons: str | None = None
    followed_rules: bool | None = None
    rules_broken: list[str] | None = None
    session_grade: str | None = None
    total_trades: int | None = None
    total_pnl: float | None = None
    total_r: float | None = None


class NoteCreate(BaseModel):
    content: str
    ticker: str | None = None
    category: str | None = None  # observation, emotional, setup, lesson
    linked_trade_id: str | None = None


def _infer_category(content: str) -> str:
    """Auto-tag a note by scanning for keywords."""
    lower = content.lower()
    if any(w in lower for w in ["feel", "fear", "fomo", "anxious", "excited", "emotion", "nervous"]):
        return "emotional"
    if any(w in lower for w in ["lesson", "learned", "mistake", "next time", "should have"]):
        return "lesson"
    if any(w in lower for w in ["setup", "entry", "signal", "flag", "ribbon", "squeeze"]):
        return "setup"
    return "observation"


@router.post("/api/journal")
async def create_journal(journal: JournalCreate):
    """Create a journal entry for a trading day."""
    record = {
        "date": journal.date or datetime.date.today().isoformat(),
        "emotional_state": journal.emotional_state,
        "what_worked": journal.what_worked,
        "what_didnt": journal.what_didnt,
        "lessons": journal.lessons,
        "followed_rules": journal.followed_rules,
        "rules_broken": journal.rules_broken,
        "session_grade": journal.session_grade,
        "total_trades": journal.total_trades,
        "total_pnl": journal.total_pnl,
        "total_r": journal.total_r,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("journal").upsert(record, on_conflict="date").execute()
        return {"status": "created", "journal": result.data[0] if result.data else record}
    except RuntimeError:
        logger.warning("Supabase not configured, returning unsaved record")
        return {"status": "not_saved", "journal": record}


@router.get("/api/journal")
async def get_journal(date: str | None = None):
    """Get a journal entry by date (defaults to today)."""
    target_date = date or datetime.date.today().isoformat()

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("journal").select("*").eq("date", target_date).execute()
        return {"journal": result.data[0] if result.data else None, "date": target_date}
    except RuntimeError:
        return {"journal": None, "date": target_date, "error": "Supabase not configured"}


@router.post("/api/notes")
async def create_note(note: NoteCreate):
    """Create a mid-session note, auto-tagged by category if not provided."""
    category = note.category if note.category in VALID_NOTE_CATEGORIES else _infer_category(note.content)

    record = {
        "content": note.content,
        "ticker": note.ticker,
        "category": category,
        "linked_trade_id": note.linked_trade_id,
        "date": datetime.date.today().isoformat(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("notes").insert(record).execute()
        return {"status": "created", "note": result.data[0] if result.data else record}
    except RuntimeError:
        logger.warning("Supabase not configured, returning unsaved record")
        return {"status": "not_saved", "note": record}


@router.get("/api/notes")
async def list_notes(date: str | None = None):
    """List mid-session notes, optionally filtered by date."""
    try:
        from api.integrations.supabase_client import get_supabase
        sb = get_supabase()
        query = sb.table("notes").select("*").order("created_at", desc=True)
        if date:
            query = query.eq("date", date)
        result = query.limit(100).execute()
        return {"notes": result.data}
    except RuntimeError:
        return {"notes": [], "error": "Supabase not configured"}
