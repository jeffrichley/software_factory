# Software Factory

A personal layer that runs Matt Pocock's skills, unmodified, across one or more repos at once, and shows what every agent is doing.

## Language

**Factory**:
The layer wrapped around Matt Pocock's skills that runs agent work across repos and reports its state; never a fork of those skills.
_Avoid_: Pipeline, harness, framework

**Tracked repo**:
A repo explicitly opted into the factory, carrying its hooks and issue-tracker setup.
_Avoid_: Project, registered repo

**Tracked session**:
A Claude Code session the human has opted onto the dashboard.
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
One launched run of a skill against a work item, tracked from launch until it is Done.
_Avoid_: Run, task, workflow

**Step**:
One piece of a Job that the dashboard shows on its own, such as one Ticket being implemented inside a Spec's Job.
_Avoid_: Subtask, stage, phase

### States

**Needs you**:
The state of an agent that cannot continue until the human acts: it asked a question, is in a HITL ticket, is waiting on a permission prompt, or has escalated for approval.
_Avoid_: Blocked, waiting, pending

**Done**:
The state of an agent that has finished its turn or job with nothing blocking it; the human is told, but no action is required.
_Avoid_: Idle, complete, finished
