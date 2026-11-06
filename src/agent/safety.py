import re
from typing import Tuple

BLOCKED_PATTERNS = [
    # Fork bomb
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"), "Fork bomb pattern detected"),
    # Root filesystem destruction
    (re.compile(r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|--force\s+--recursive)\s+/(?:\s+|$)"), "Destructive rm -rf on root filesystem detected"),
    # Exfiltration of secrets/canary tokens
    (re.compile(r"(curl|wget|nc|ncat|bash\s+-i).*(\$(API_KEY|CANARY_TOKEN|SECRET|AWS_ACCESS_KEY)|evil-c2|pastebin)"), "Secret exfiltration attempt detected"),
    # Raw device overwrite
    (re.compile(r"dd\s+if=/dev/zero\s+of=/dev/[s|v]da"), "Raw device overwrite detected"),
]


class SafetyHook:
    def __init__(self, mode: str = "enforce"):
        self.mode = mode

    def inspect_command(self, command: str) -> Tuple[bool, str]:
        """
        Inspects a command string before passing it into the Celesto guest microVM.
        Returns:
            (allowed: bool, reason: str)
        """
        for pattern, reason in BLOCKED_PATTERNS:
            if pattern.search(command):
                return False, reason

        return True, "Command passed safety inspection"
