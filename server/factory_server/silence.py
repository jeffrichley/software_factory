"""When a Machine has gone silent, and what that does to its sessions on the dashboard; when a session has gone quiet."""

from datetime import datetime, timedelta

# A Machine with no events for this long is silent: "last seen Nm".
SILENT_AFTER = timedelta(minutes=5)
MACHINE_SILENT = "Machine silent"
# A Working session with no events of its own for this long is quiet: "Working · quiet Nm" (as the Step struggle silence rule).
QUIET_AFTER = timedelta(minutes=10)


def is_silent(last_seen: str, now: datetime) -> bool:
    return now - datetime.fromisoformat(last_seen) >= SILENT_AFTER


def as_shown(session: dict, silent_since: str | None, now: datetime, quiet_after: timedelta = QUIET_AFTER) -> dict:
    """A session as the dashboard shows it, given when its Machine went silent (None while it reports).

    Working can't be trusted once the Machine is silent: Stale since its last event, until it reports again.
    Needs you and Done keep their state, since they were already waiting on the human.
    A Working session whose Machine still reports, but which has had no events itself for `quiet_after`, stays
    Working (a long tool call is silent too) and says since when it has been quiet: `quiet_since`, else None.
    """
    session = dict(session)
    last_event = session.pop("last_event_at", None)
    session["quiet_since"] = None
    if session["state"] != "Working":
        return session
    if silent_since is not None:
        return {**session, "state": "Stale", "state_since": silent_since, "stale_reason": MACHINE_SILENT}
    if last_event is not None and now - datetime.fromisoformat(last_event) >= quiet_after:
        session["quiet_since"] = last_event
    return session
