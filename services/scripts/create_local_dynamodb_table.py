"""
create_local_dynamodb_table.py — provisions the FinTracker_UserProfile table
against a local DynamoDB (docker-compose's dynamodb-local service).

No CDK/Terraform in this repo defines the User Profile Service's DynamoDB
table yet, and dynamodb-local starts empty on every fresh volume — so this
script exists to stand up the single-table schema that
app/identity/repository.py, app/goals/repository.py, and
app/websocket/repository.py all expect:

    PK (String) + SK (String) composite primary key, no GSIs, on-demand
    billing, TTL enabled on the "ttl" attribute (used by websocket
    connection items).

Idempotent — safe to re-run; does nothing if the table already exists.

Usage:
    docker compose up -d dynamodb-local
    export DYNAMODB_ENDPOINT_URL=http://localhost:8000
    python scripts/create_local_dynamodb_table.py
"""
from __future__ import annotations

import os
import sys

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "FinTracker_UserProfile")
ENDPOINT_URL = os.environ.get("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")


def main() -> None:
    client = boto3.client(
        "dynamodb",
        endpoint_url=ENDPOINT_URL,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )

    try:
        client.describe_table(TableName=TABLE_NAME)
        print(f"Table '{TABLE_NAME}' already exists at {ENDPOINT_URL}. Nothing to do.")
        return
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    client.create_table(
        TableName=TABLE_NAME,
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    client.get_waiter("table_exists").wait(TableName=TABLE_NAME)

    client.update_time_to_live(
        TableName=TABLE_NAME,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
    )

    print(f"✓ Created table '{TABLE_NAME}' at {ENDPOINT_URL} (TTL enabled on 'ttl')")


if __name__ == "__main__":
    main()
