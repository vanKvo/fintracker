"""
dev_setup_user.py — DynamoDB identity bootstrap for local development.

Simulates the Cognito Post-Confirmation Lambda trigger for a real Cognito user
so the user-profile service can resolve their sub to the devUserId.

Required only if you want to test user-profile endpoints locally
(GET /profile, savings goals, etc.). Not needed for ledger-only testing.

Usage (against real AWS):
    export AWS_DEFAULT_REGION=us-east-1
    export DYNAMODB_TABLE_NAME=FinTracker_UserProfile
    python scripts/dev_setup_user.py --sub <cognito_sub> --email <email>

Usage (against local DynamoDB — no AWS account/table needed):
    docker compose up -d dynamodb-local
    export DYNAMODB_ENDPOINT_URL=http://localhost:8000
    python scripts/create_local_dynamodb_table.py
    python scripts/dev_setup_user.py --sub <cognito_sub> --email <email>

The Cognito sub is found in:
    AWS Console → Cognito → User Pool → Users tab → click your test user → sub attribute

Multiple local users:
    By default every sub maps to the same shared DEV_USER_ID (so existing seeded
    ledger/Postgres data keeps working for the original dev user). To create a
    second, isolated user backed by its own internal UUID:
        python scripts/dev_setup_user.py --sub <second_sub> --email <second_email> --generate-user-id
    or pin a specific UUID with --user-id <uuid>. Note the printed/generated
    user_id and seed matching Postgres data (accounts/transactions/budgets) for
    it separately — this script only writes the DynamoDB identity/profile rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from uuid import UUID

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

DEV_USER_ID  = "e2b86a8a-b851-460d-8ea9-a1b66df8ae8e"
TABLE_NAME   = os.environ.get("DYNAMODB_TABLE_NAME", "FinTracker_UserProfile")
# Set to http://localhost:8000 (dynamodb-local via docker-compose) to run against a
# local table instead of real AWS. Unset by default so production behavior is unchanged.
ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap DynamoDB identity for a dev Cognito user")
    parser.add_argument("--sub",   required=True, help="Cognito sub (UUID string from User Pool)")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--first-name", default="Dev",  dest="first_name")
    parser.add_argument("--last-name",  default="User", dest="last_name")
    parser.add_argument(
        "--user-id",
        dest="user_id",
        default=None,
        help=(
            "Internal UUID to map the Cognito sub to. Defaults to the shared "
            f"DEV_USER_ID ({DEV_USER_ID}) so existing seeded ledger/Postgres data "
            "keeps working. Pass a distinct UUID (or omit and let one be generated "
            "with --generate-user-id) to create a second, isolated user."
        ),
    )
    parser.add_argument(
        "--generate-user-id",
        action="store_true",
        help="Generate a fresh random UUID for --user-id instead of specifying one.",
    )
    args = parser.parse_args()

    if args.generate_user_id and args.user_id:
        parser.error("--user-id and --generate-user-id are mutually exclusive")

    # Initialize the low-level client directly. When ENDPOINT_URL is set (local
    # DynamoDB), it doesn't validate credentials but boto3 still requires some
    # value to be present, so throwaway "local" credentials are supplied.
    client_kwargs = {}
    if ENDPOINT_URL:
        client_kwargs = dict(
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    client = boto3.client("dynamodb", **client_kwargs)
    serializer = TypeSerializer()
    
    if args.generate_user_id:
        user_id_str = str(uuid.uuid4())
    elif args.user_id:
        user_id_str = str(UUID(args.user_id))
    else:
        user_id_str = DEV_USER_ID
    now = datetime.now(tz=timezone.utc).isoformat()

    # Define your raw Python items cleanly
    identity_mapping_item = {
        "PK": f"IDENTITY#{args.sub}",
        "SK": "MAPPING",
        "internal_user_id": user_id_str,
    }

    profile_item = {
        "PK": f"USER#{user_id_str}",
        "SK": "PROFILE",
        "email": args.email,
        "first_name": args.first_name,
        "last_name": args.last_name,
        "phone_number": None,  # Will automatically map to {'NULL': True}
        "subscription_tier": "FREE",
        "created_at": now,
    }

    settings_item = {
        "PK": f"USER#{user_id_str}",
        "SK": "SETTINGS",
        "currency": "USD",
        "timezone": "America/New_York",
        "notification_prefs": json.dumps({
            "channel": "EMAIL",
            "budget_alerts": True,
            "statement_processed": True,
        }),
    }

    # Helper lambda to convert standard dicts to DynamoDB attributes mapping
    serialize_item = lambda item: {k: serializer.serialize(v) for k, v in item.items()}

    try:
        # Fixed parameter to TransactItems and wrapped Items with the serializer
        client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": TABLE_NAME,
                        "Item": serialize_item(identity_mapping_item),
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
                {
                    "Put": {
                        "TableName": TABLE_NAME,
                        "Item": serialize_item(profile_item),
                    }
                },
                {
                    "Put": {
                        "TableName": TABLE_NAME,
                        "Item": serialize_item(settings_item),
                    }
                },
            ]
        )
        print(f"✓ Created identity mapping: IDENTITY#{args.sub} → {user_id_str}")
        print(f"✓ Created PROFILE and SETTINGS for user_id={user_id_str}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "TransactionCanceledException":
            print(f"User already exists for sub={args.sub}. Nothing changed.")
        elif code == "ResourceNotFoundException":
            target = ENDPOINT_URL or "real AWS (no DYNAMODB_ENDPOINT_URL set in this shell)"
            print(
                f"Error: table '{TABLE_NAME}' not found at {target}.\n"
                "  - Testing against local DynamoDB? DYNAMODB_ENDPOINT_URL must be exported "
                "in *this* shell — it doesn't carry over from other terminals/tabs.\n"
                "  - Local table missing/wiped? dynamodb-local runs in-memory, so a container "
                "restart clears it — re-run scripts/create_local_dynamodb_table.py.\n"
                "  - Targeting real AWS on purpose? Confirm the table exists: "
                f"aws dynamodb describe-table --table-name {TABLE_NAME}",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
