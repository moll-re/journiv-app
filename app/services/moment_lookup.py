"""
Shared moment ownership lookup helpers.
"""
import uuid
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.entry import Entry
from app.models.moment import Moment
from app.services.journal_access import JournalAccessDeniedError, JournalAccessService


class MomentNotFoundError(Exception):
    """Raised when a moment is not found for the user."""


def get_owned_moment(
    session: Session,
    user_id: uuid.UUID,
    moment_id: uuid.UUID,
    *,
    options: Optional[list[Any]] = None,
) -> Moment:
    """Fetch a user-owned moment with optional ORM loading options."""
    statement = select(Moment).where(Moment.id == moment_id, Moment.user_id == user_id)
    if options:
        statement = statement.options(*options)
    moment = session.exec(statement).first()
    if not moment:
        raise MomentNotFoundError("Moment not found")
    return moment


def get_accessible_moment(
    session: Session,
    user_id: uuid.UUID,
    moment_id: uuid.UUID,
    *,
    edit: bool = False,
    options: Optional[list[Any]] = None,
) -> Moment:
    """Fetch a private Moment or a journal-backed Moment the actor can access."""
    statement = select(Moment).where(Moment.id == moment_id)
    if options:
        statement = statement.options(*options)
    moment = session.exec(statement).first()
    if not moment:
        raise MomentNotFoundError("Moment not found")
    entry = session.exec(select(Entry).where(Entry.moment_id == moment_id)).first()
    if entry is None:
        # Standalone quick logs never become shared just because another journal is shared.
        if moment.user_id != user_id:
            raise MomentNotFoundError("Moment not found")
        return moment
    if entry.is_draft and moment.user_id != user_id:
        # Drafts stay with their author until they are published into the shared timeline.
        raise MomentNotFoundError("Moment not found")
    try:
        JournalAccessService(session).require(entry.journal_id, user_id, edit=edit)
    except JournalAccessDeniedError:
        raise MomentNotFoundError("Moment not found") from None
    return moment
