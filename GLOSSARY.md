# Software Factory

A personal layer that runs Matt Pocock's skills, unmodified, across one or more repos at once, and shows what every agent is doing.

## Language

**Factory**:
The layer wrapped around Matt Pocock's skills that runs agent work across repos and reports its state; never a fork of those skills.
_Avoid_: Pipeline, harness, framework

**Factory server**:
The single process on the human's local network that every Machine reports to and that serves the dashboard.
_Avoid_: Backend, collector, daemon

**Machine**:
One Claude Code install that reports to the Factory server, named by the human; WSL and Windows on the same PC are two Machines.
_Avoid_: Box, host, computer

**Silent Machine**:
A Machine the Factory server has had no events from for five minutes; it shows as "last seen Nm", and its Working sessions show as Stale.
_Avoid_: Offline, disconnected, down

**Tracked repo**:
A repo the human has turned on for the Factory on a given Machine; repos are off by default.
_Avoid_: Project, registered repo

**Tracked session**:
Any Claude Code session running in a Tracked repo that the human has not hidden.
_Avoid_: Agent, instance

### Work items

**Work item**:
An issue on a tracked repo's tracker that the factory knows how to treat; always one of Map, Decision ticket, Spec or Ticket.
_Avoid_: Task, card

**Map**:
A wayfinder map issue: the index of a planning effort.
_Avoid_: Plan, epic

**Decision ticket**:
A child of a Map whose resolution is a decision, not code.
_Avoid_: Wayfinder ticket, question

**Spec**:
An issue produced by `to-spec` describing a feature to build.
_Avoid_: PRD, design doc

**Ticket**:
A child of a Spec: one implementable vertical slice produced by `to-tickets`.
_Avoid_: Task, story, slice

### Running work

**Job**:
One launched run of a skill against a work item, tracked from launch until its PR is merged or closed, or the human abandons it; it is Done once a non-draft PR exists.
_Avoid_: Run, task, workflow

**Job stage**:
Where a Job is in its life: In progress, PR open, Merged, Closed or Abandoned; separate from its session's state.
_Avoid_: Job status, Phase

**Step**:
One Ticket being worked inside a Job; a Spec's Job has one Step per Ticket, a Ticket Job has one.
_Avoid_: Subtask, stage

**Phase**:
Where a Step is in its work right now, such as Exploring, Red, Green, Refactor, Reviewing, Committed or Merged.
_Avoid_: Job stage, status

### States

**Needs you**:
The state of a Tracked session that cannot continue until the human acts: it asked a question, is in a HITL ticket, is waiting on a permission prompt, has escalated for approval, or stopped without finishing.
_Avoid_: Blocked, waiting, pending

**Done**:
The state of a Tracked session that has finished with nothing blocking it; a Job's session is Done once its non-draft PR exists. The human is told, but no action is required.
_Avoid_: Idle, complete, finished

**Stale**:
The state of a Tracked session that was Working when its Machine went silent, so what it is doing can't be trusted; it says why ("Machine silent") and returns to its real state once the Machine reports again. Needs you and Done are never Stale.
_Avoid_: Dead, lost, offline
