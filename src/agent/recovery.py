import os
import json
from datetime import datetime, timezone
from typing import Dict, Any

DEFAULT_TRACE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "failure_trace.jsonl"
)


class FailureRecoveryManager:
    def __init__(self, trace_path: str = DEFAULT_TRACE_PATH):
        self.trace_path = trace_path
        os.makedirs(os.path.dirname(self.trace_path), exist_ok=True)

    def append_trace_event(self, event_data: Dict[str, Any]):
        if "ts" not in event_data:
            event_data["ts"] = datetime.now(timezone.utc).isoformat()
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data) + "\n")

    def execute_recovery_scenario(
        self,
        sandbox_name: str,
        failed_step: int = 7,
        total_steps: int = 10,
        policy: str = "rollback",
    ):
        """
        Simulates the execution of a 10-step agent autograder task where step 7 fails,
        triggering the specified recovery policy (rollback to step 6 snapshot).
        """
        # Steps 1 to 6
        for step in range(1, failed_step):
            self.append_trace_event({
                "sandbox_name": sandbox_name,
                "step": step,
                "total_steps": total_steps,
                "event": "step_completed",
                "status": "success",
                "details": f"Completed test suite setup step {step}",
            })
            if step == 6:
                # Take checkpoint snapshot before step 7
                self.append_trace_event({
                    "sandbox_name": sandbox_name,
                    "step": 6,
                    "event": "snapshot_created",
                    "snapshot_id": f"snap-{sandbox_name}-step06",
                    "details": "Checkpoint snapshot taken prior to untrusted dependency injection step",
                })

        # Step 7 fails
        self.append_trace_event({
            "sandbox_name": sandbox_name,
            "step": failed_step,
            "total_steps": total_steps,
            "event": "step_failed",
            "status": "failed",
            "error": "DependencyConflictError: Untrusted package injected corrupted symbols",
        })

        # Policy applied
        self.append_trace_event({
            "sandbox_name": sandbox_name,
            "step": failed_step,
            "total_steps": total_steps,
            "event": "policy_applied",
            "policy": policy,
            "target_snapshot": f"snap-{sandbox_name}-step06",
            "details": f"Applied {policy} policy: restored microVM state from checkpoint snapshot snap-{sandbox_name}-step06",
        })

        # State restored and resume
        self.append_trace_event({
            "sandbox_name": sandbox_name,
            "step": 6,
            "event": "snapshot_restored",
            "snapshot_id": f"snap-{sandbox_name}-step06",
            "status": "restored",
            "details": "MicroVM restored to pristine step 6 state",
        })

        # Safe completion of subsequent steps
        for step in range(8, total_steps + 1):
            self.append_trace_event({
                "sandbox_name": sandbox_name,
                "step": step,
                "total_steps": total_steps,
                "event": "step_completed",
                "status": "success",
                "details": f"Completed test verification step {step} in clean recovered guest",
            })

        # Cleanup
        self.append_trace_event({
            "sandbox_name": sandbox_name,
            "event": "sandbox_cleaned_up",
            "status": "deleted",
            "details": "Lifecycle cleanup on task completion finished successfully",
        })
