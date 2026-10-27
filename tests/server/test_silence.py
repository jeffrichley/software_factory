"""What a silent Machine does to its sessions' state on the dashboard."""

from datetime import UTC, datetime

import pytest

from factory_server.silence import as_shown

SILENT_SINCE = "2026-10-26T12:00:00Z"
NOW = datetime(2026, 10, 26, 12, 5, tzinfo=UTC)


def session(state: str) -> dict:
    return {"id": "1", "machine": "wsl", "repo": "jeff/widgets", "state": state, "state_since": "2026-10-26T11:58:00Z",
            "quiet_since": None}


def test_a_working_session_on_a_silent_machine_is_stale_since_its_last_event():
    assert as_shown(session("Working"), SILENT_SINCE, NOW) == {
        **session("Working"), "state": "Stale", "state_since": SILENT_SINCE, "stale_reason": "Machine silent",
    }


@pytest.mark.parametrize("state", ["Needs you", "Done"])
def test_needs_you_and_done_keep_their_state_on_a_silent_machine(state):
    assert as_shown(session(state), SILENT_SINCE, NOW) == session(state)


def test_a_session_on_a_machine_that_is_reporting_is_shown_as_it_is():
    assert as_shown(session("Working"), None, NOW) == session("Working")
