"""Sound rules: when the dashboard plays the Needs you sound or the softer Done sound.

Each sound belongs to one transition of a session's shown state, so it plays at most once.
Done sounds at once. A permission prompt sounds when Claude Code itself notifies it
(Notification permission_prompt, a few seconds in), not on PermissionRequest, so a quick
approval at the terminal is silent. Any other Needs you (a question, a HITL stop, an
escalation, an error) sounds after a grace, and not at all if the session moves on first.
"""

import json
from datetime import datetime, timedelta

from .store import Store

NEEDS_YOU = "needs_you"
DONE = "done"
GRACE = timedelta(seconds=10)


def schedule(store: Store, session_id: int, event: dict, now: datetime) -> None:
    """After an event has settled the session's state: schedule the sound its transition calls for."""
    session = store.session(session_id)
    transition = session["transitions"]
    if session["state"] == "Done":
        store.schedule_sound(session_id, transition, DONE, now)
    elif session["state"] == "Needs you":
        reason = json.loads(session["reason"] or "{}")
        if event.get("hook_event_name") == "Notification" and event.get("notification_type") == "permission_prompt":
            store.schedule_sound(session_id, transition, NEEDS_YOU, now)
        elif reason.get("kind") != "permission":
            store.schedule_sound(session_id, transition, NEEDS_YOU, now + GRACE)
