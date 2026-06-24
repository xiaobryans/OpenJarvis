"""B1 Google OAuth vault migration — one-time script.

Reads the refresh_token from local ~/.openjarvis/connectors/gmail.json
(or the first available connector file) and stores it in AWS Secrets Manager
under the existing OpenJarvis secret as GOOGLE_OAUTH_REFRESH_TOKEN.

Safety rules:
- Never prints token values.
- Never prints client_id or client_secret values.
- Outputs only presence/status information.
- Idempotent: safe to run multiple times.

Usage:
    python3 scripts/migrate_google_tokens_to_vault.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SECRET_ID = "omnix-workbench-071179620006-ap-southeast-1-secrets"
REGION = "ap-southeast-1"
TARGET_KEY = "GOOGLE_OAUTH_REFRESH_TOKEN"

CONNECTOR_FILES = [
    "gmail.json",
    "gcalendar.json",
    "gdrive.json",
    "gcontacts.json",
    "google_tasks.json",
]
CONNECTORS_DIR = Path.home() / ".openjarvis" / "connectors"


def _find_refresh_token() -> str:
    """Read refresh_token from the first available connector file (no printing)."""
    for filename in CONNECTOR_FILES:
        path = CONNECTORS_DIR / filename
        if not path.exists():
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            rt = data.get("refresh_token", "").strip()
            if rt:
                print(f"  Source file: {filename} — refresh_token PRESENT, len={len(rt)}")
                return rt
        except Exception as e:
            print(f"  WARNING: could not read {filename}: {e}")
    return ""


def main() -> int:
    print("=== B1 Google OAuth → AWS Secrets Manager migration ===")
    print()

    # Step 1: Find local refresh token
    print("Step 1: Locate refresh_token in local connector files...")
    refresh_token = _find_refresh_token()
    if not refresh_token:
        print("ERROR: No refresh_token found in any connector file.")
        print(
            "  Checked:", ", ".join(str(CONNECTORS_DIR / f) for f in CONNECTOR_FILES)
        )
        print("  Re-run the Google OAuth flow first: jarvis connect google")
        return 1
    print("  refresh_token: FOUND (not printed)")
    print()

    # Step 2: Get current secret from Secrets Manager (keys only check)
    print("Step 2: Read current Secrets Manager secret keys...")
    try:
        import boto3  # type: ignore
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        return 1

    client = boto3.client("secretsmanager", region_name=REGION)
    try:
        resp = client.get_secret_value(SecretId=SECRET_ID)
        current = json.loads(resp["SecretString"])
    except Exception as e:
        print(f"ERROR: Could not read Secrets Manager secret: {type(e).__name__}: {e}")
        return 1

    existing_keys = list(current.keys())
    print(f"  Current key count: {len(existing_keys)}")
    print(f"  Keys: {existing_keys}")
    print()

    # Step 3: Check idempotency
    if TARGET_KEY in current:
        existing_len = len(current[TARGET_KEY])
        print(
            f"Step 3: {TARGET_KEY} already present in secret (len={existing_len}). Checking..."
        )
        if current[TARGET_KEY] == refresh_token:
            print("  Token matches local value. Migration already complete. Exiting.")
            return 0
        else:
            print(
                "  WARNING: Existing value differs from local refresh_token. Updating."
            )
    else:
        print(f"Step 3: {TARGET_KEY} NOT present — will add it.")
    print()

    # Step 4: Add GOOGLE_OAUTH_REFRESH_TOKEN and write back
    print(f"Step 4: Adding {TARGET_KEY} to secret...")
    current[TARGET_KEY] = refresh_token
    try:
        client.put_secret_value(
            SecretId=SECRET_ID,
            SecretString=json.dumps(current),
        )
    except Exception as e:
        print(
            f"ERROR: Could not update Secrets Manager secret: {type(e).__name__}: {e}"
        )
        return 1
    print(f"  {TARGET_KEY}: WRITTEN to Secrets Manager (value not printed)")
    print()

    # Step 5: Verify (keys only)
    print("Step 5: Verifying write...")
    resp2 = client.get_secret_value(SecretId=SECRET_ID)
    verified = json.loads(resp2["SecretString"])
    if TARGET_KEY in verified and verified[TARGET_KEY] == refresh_token:
        print(f"  VERIFIED: {TARGET_KEY} present in Secrets Manager, len={len(verified[TARGET_KEY])}")
        print(f"  Total keys now: {len(verified)}")
    else:
        print("  ERROR: Verification failed — token not found after write.")
        return 1
    print()

    print("=== MIGRATION COMPLETE ===")
    print(f"  {TARGET_KEY}: ADDED to {SECRET_ID}")
    print("  No token values were printed.")
    print("  Next step: deploy task def rev 20 with GOOGLE_OAUTH_REFRESH_TOKEN reference.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
