"""Sound rules: when the dashboard plays the Needs you sound or the softer Done sound.

Each sound belongs to one transition of a session's shown state, so it plays at most once.
Done sounds at once.
"""

from datetime import datetime

from .store import Store

NEEDS_YOU = "needs_you"
DONE = "done"


def schedule(store: Store, session_id: int, event: dict, now: datetime) -> None:
    """After an event has settled the session's state: schedule the sound its transition calls for."""
    session = store.session(session_id)
    if session["state"] == "Done":
        store.schedule_sound(session_id, session["transitions"], DONE, now)
