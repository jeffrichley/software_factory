"""State rules: when a Tracked session is Working, Needs you (and why) or Done.

A session Needs you while any prompt waits on the human: a permission prompt, an
AskUserQuestion question, a plan approval or an MCP elicitation, from the main session or
any of its subagents (subagent events carry the parent's session_id and their own agent_id).
Each prompt clears on its own resolution: the PostToolUse/PostToolUseFailure with its
tool_use_id, or ElicitationResult. Backstops: typing into the session clears every prompt; the
end of a turn (Stop, SubagentStop) clears that turn's; later tool activity clears a prompt only
when no open call holds it, since parallel calls run beside a waiting one. With no prompt
waiting, the session shows its base state: Working, Done after Stop, or Needs you after StopFailure.
"""

from datetime import datetime

from .store import MAIN, Store

# Tools whose call is itself a prompt for the human.
ASK_TOOLS = {"AskUserQuestion", "ExitPlanMode"}


def permission_reason(event: dict) -> dict:
    tool, args = event.get("tool_name", ""), event.get("tool_input") or {}
    command = args.get("command") or args.get("file_path") or args.get("url") or ", ".join(f"{k}: {v}" for k, v in args.items())
    return {"kind": "permission", "tool": tool, "command": str(command)}


def ask_reason(event: dict) -> dict:
    args = event.get("tool_input") or {}
    if event["tool_name"] == "ExitPlanMode":
        return {"kind": "question", "text": "Approve the plan?"}
    texts = [q.get("question", "") for q in args.get("questions") or [] if isinstance(q, dict)]
    return {"kind": "question", "text": " · ".join(t for t in texts if t) or "Question"}


def elicitation_key(event: dict) -> str:
    return f"elicitation:{event.get('elicitation_id') or event.get('mcp_server_name', '')}"


def running_background_tasks(event: dict) -> bool:
    return any(t.get("status") == "running" for t in event.get("background_tasks") or [] if isinstance(t, dict))


def apply(store: Store, session_id: int, event: dict, now: datetime) -> None:
    """Apply one hook event's effect on the session's state."""
    subagent = event.get("agent_id") or MAIN
    tool_use_id = event.get("tool_use_id")
    match event.get("hook_event_name"):
        case "PreToolUse":
            if tool_use_id:
                store.open_tool_use(session_id, subagent, tool_use_id, event.get("tool_name", ""), event.get("tool_input") or {})
            store.clear_loose_prompts(session_id, subagent)
            if event.get("tool_name") in ASK_TOOLS:
                store.add_prompt(session_id, subagent, tool_use_id, ask_reason(event), now)
            store.set_base(session_id, "Working")
        case "PermissionRequest":
            # No tool_use_id on this event: tie it to the open call it asks about. A question or plan
            # approval asking permission stays the question it already is.
            key = store.find_tool_use(session_id, subagent, event.get("tool_name", ""), event.get("tool_input") or {})
            store.add_prompt(session_id, subagent, key, permission_reason(event), now)
        case "PostToolUse" | "PostToolUseFailure":
            if tool_use_id:
                store.close_tool_use(session_id, tool_use_id)
                store.clear_prompts(session_id, key=tool_use_id)
            store.clear_loose_prompts(session_id, subagent)
            store.set_base(session_id, "Working")
        case "Elicitation":
            store.add_prompt(session_id, subagent, elicitation_key(event), {"kind": "question", "text": event.get("message", "")}, now)
        case "ElicitationResult":
            store.clear_prompts(session_id, key=elicitation_key(event))
        case "UserPromptSubmit":
            # The human typed into the session: whatever it asked is answered, and Done is seen.
            store.clear_prompts(session_id)
            store.mark_seen(session_id)
            store.set_base(session_id, "Working")
        case "SessionStart" | "SubagentStart" | "UserPromptExpansion":
            store.set_base(session_id, "Working")
        case "Stop":
            # The main turn ended, so its own prompts are over; a subagent still running may yet ask.
            if running_background_tasks(event):
                store.end_turn(session_id, MAIN)
                store.set_base(session_id, "Working")
            else:
                store.end_turn(session_id)
                store.set_base(session_id, "Done")
        case "SubagentStop":
            # Never Done: only the subagent finished. Its prompts are over.
            store.end_turn(session_id, subagent)
        case "StopFailure":
            store.set_base(session_id, "Needs you", {"kind": "error", "type": event.get("error") or "unknown"})
    store.settle(session_id, now)
