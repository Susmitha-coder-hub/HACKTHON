import os
import json
from datetime import datetime, timezone
import re

SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")
DEFAULT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "commands.jsonl")


class CommandAuditor:
    def __init__(self, log_path: str = DEFAULT_LOG_PATH):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_command(
        self,
        sandbox_name: str,
        command: str,
        decision: str,
        execution_target: str = "celesto_sandbox",
        ts: str = None,
    ) -> dict:
        if not SANDBOX_REGEX.match(sandbox_name):
            raise ValueError(f"Invalid sandbox name: {sandbox_name}")
        if not command or not command.strip():
            raise ValueError("Command cannot be empty")
        if decision not in ("allow", "block"):
            raise ValueError(f"Invalid decision: {decision}. Must be 'allow' or 'block'")
        if execution_target != "celesto_sandbox":
            raise ValueError("execution_target must be exactly 'celesto_sandbox'")

        if ts is None:
            ts = datetime.now(timezone.utc).isoformat()

        record = {
            "ts": ts,
            "sandbox_name": sandbox_name,
            "command": command.strip(),
            "decision": decision,
            "execution_target": "celesto_sandbox",
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        return record
