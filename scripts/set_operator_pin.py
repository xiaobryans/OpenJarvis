"""Set JARVIS_OPERATOR_PIN_HASH in cloud-keys.env.

Usage:
    python scripts/set_operator_pin.py

Reads PIN via getpass (no echo, no log, not stored in shell history).
Writes only the SHA-256 hash to ~/.openjarvis/cloud-keys.env.
Raw PIN is never stored, printed, or logged.
"""

from __future__ import annotations

import getpass
import hashlib
import os
import sys
from pathlib import Path

ENV_FILE = Path.home() / ".openjarvis" / "cloud-keys.env"
KEY_NAME = "JARVIS_OPERATOR_PIN_HASH"


def _hash_pin(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _update_env_file(hash_value: str) -> None:
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(KEY_NAME + "="):
                lines.append(f"{KEY_NAME}={hash_value}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{KEY_NAME}={hash_value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    print(f"Setting {KEY_NAME} in {ENV_FILE}")
    print("PIN will not be echoed, stored, or logged — only its SHA-256 hash is saved.\n")

    pin1 = getpass.getpass("Enter operator PIN: ")
    if not pin1.strip():
        print("ERROR: PIN must not be empty.", file=sys.stderr)
        return 1

    pin2 = getpass.getpass("Confirm PIN: ")
    if pin1 != pin2:
        print("ERROR: PINs do not match.", file=sys.stderr)
        return 1

    h = _hash_pin(pin1)
    del pin1, pin2  # clear from memory as soon as possible

    _update_env_file(h)
    print(f"\nSaved {KEY_NAME}={h[:12]}... (truncated) to {ENV_FILE}")
    print("Done. Raw PIN is NOT stored anywhere.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
