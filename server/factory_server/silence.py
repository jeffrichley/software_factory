"""When a Machine has gone silent, and what that does to its sessions on the dashboard."""

from datetime import datetime, timedelta

# A Machine with no events for this long is silent: "last seen Nm".
SILENT_AFTER = timedelta(minutes=5)
MACHINE_SILENT = "Machine silent"


def is_silent(last_seen: str, now: datetime) -> bool:
    return now - datetime.fromisoformat(last_seen) >= SILENT_AFTER


def as_shown(session: dict, silent_since: str | None) -> dict:
    """A session as the dashboard shows it, given when its Machine went silent (None while it reports).

    Working can't be trusted once the Machine is silent: Stale since its last event, until it reports again.
    Needs you and Done keep their state, since they were already waiting on the human.
    """
    if silent_since is None or session["state"] != "Working":
        return session
    return {**session, "state": "Stale", "state_since": silent_since, "stale_reason": MACHINE_SILENT}
