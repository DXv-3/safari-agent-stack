"""safari_brain_publisher.py  —  WIRE-01

Brain bus integration for safari-agent-stack.

Publishes structured learn events to harmony-engine-protocol brain bus
after every agent task completes.  The brain_sink process picks these up
and writes them to brain.db, making iPad agent activity visible in:
  - conductor pre-route queries (model/gate failure history)
  - the-brain dashboard (subsystem heartbeat)
  - self-improving-system-builder audit trail

USAGE
-----
At the end of any agent task completion handler:

    from safari_brain_publisher import publish_agent_result
    publish_agent_result(
        task_id  = task.id,
        task_type= "scrape" | "fill_form" | "extract" | "navigate" | ...,
        outcome  = "pass" | "fail" | "blocked",
        detail   = short_summary_string,   # max 200 chars used
        model    = "grok-3",               # model used for this task
        url      = page.url,               # page URL (truncated to 150 chars)
    )

For heartbeat pings (call from main loop or watchdog):

    from safari_brain_publisher import publish_agent_ping
    publish_agent_ping(status="running")   # or "idle", "error"

GRACEFUL DEGRADATION
--------------------
If harmony-engine-protocol is not importable (e.g. running on a device
that only has safari-agent-stack), all publish_* calls return False
silently.  The agent continues running regardless.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Resolve harmony-engine-protocol path
# ---------------------------------------------------------------------------
# Convention: repos are sibling directories under the same parent.
# Supports both ~/dev/safari-agent-stack and ~/safari-agent-stack layouts.

_HERE = Path(__file__).resolve().parent
_CANDIDATE_PATHS = [
    _HERE.parent / "harmony-engine-protocol",    # sibling repo (standard)
    _HERE.parent.parent / "harmony-engine-protocol",  # nested workspace
    Path.home() / "harmony-engine-protocol",      # home dir fallback
]

_bus_pub = None
_AVAILABLE = False

for _candidate in _CANDIDATE_PATHS:
    if _candidate.exists():
        _path_str = str(_candidate)
        if _path_str not in sys.path:
            sys.path.insert(0, _path_str)
        try:
            from brain_bus import BrainBusPublisher  # type: ignore
            _bus_pub = BrainBusPublisher(source_repo="safari-agent-stack")
            _AVAILABLE = True
        except Exception:
            pass
        break


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def publish_agent_result(
    task_id:   str,
    task_type: str,
    outcome:   str,            # "pass" | "fail" | "blocked"
    detail:    str = "",
    model:     str = "",
    url:       str = "",
) -> bool:
    """
    Publish a task completion event to the brain bus.

    Returns True if published successfully, False otherwise.
    Never raises.
    """
    if not _AVAILABLE or _bus_pub is None:
        return False

    event_type = "GATE_PASSED" if outcome == "pass" else "GATE_FAILED"
    _detail = (
        f"type={task_type} "
        f"model={model or 'unknown'} "
        f"url={url[:150] if url else ''} "
        f"{detail[:200]}"
    ).strip()

    try:
        return _bus_pub.publish_learn(
            run_id=str(task_id),
            source="safari-agent-stack",
            category="agent_task",
            event_type=event_type,
            detail=_detail,
            outcome=outcome,
        )
    except Exception:
        return False


def publish_agent_ping(status: str = "running") -> bool:
    """
    Publish a heartbeat ping from the safari agent to the brain bus.
    Call this from the main agent loop to indicate liveness.

    Returns True if published, False otherwise. Never raises.
    """
    if not _AVAILABLE or _bus_pub is None:
        return False
    try:
        return _bus_pub.publish_ping(
            subsystem_name="safari-agent-stack",
            status=status,
        )
    except Exception:
        return False


def publish_kg_link(
    target_repo: str,
    relation:    str = "FEEDS",
    weight:      float = 1.0,
) -> bool:
    """
    Publish a KG edge from safari-agent-stack to another repo.
    Use this to register new discovered tool connections into the brain KG.
    """
    if not _AVAILABLE or _bus_pub is None:
        return False
    try:
        return _bus_pub.publish_kg_edge(
            source="safari-agent-stack",
            target=target_repo,
            relation=relation,
            weight=weight,
        )
    except Exception:
        return False


def bus_available() -> bool:
    """Check if brain bus is reachable from this process."""
    return _AVAILABLE
