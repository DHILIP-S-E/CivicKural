from __future__ import annotations

import os

import boto3
import pytest

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ["WARDWATCH_TABLE"] = "wardwatch-test"
os.environ["WARDWATCH_BUCKET"] = "wardwatch-test-bucket"
os.environ["WHATSAPP_TOKEN"] = ""
os.environ["JWT_SECRET"] = "test-secret"

from moto import mock_aws  # noqa: E402

from wardwatch import geocode, transcribe  # noqa: E402
from wardwatch.config import get_settings  # noqa: E402
from wardwatch.llm import set_text_hook, set_vision_hook  # noqa: E402
from wardwatch import notify  # noqa: E402
from wardwatch.notify import FakeWhatsApp, set_messenger  # noqa: E402


def _create_table(client, name):
    client.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
            {"AttributeName": "gsi2pk", "AttributeType": "S"},
            {"AttributeName": "gsi2sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "gsi1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "gsi2",
                "KeySchema": [
                    {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    get_settings.cache_clear()
    with mock_aws():
        s = get_settings()
        ddb = boto3.client("dynamodb", region_name=s.aws_region)
        _create_table(ddb, s.wardwatch_table)
        boto3.client("s3", region_name=s.aws_region).create_bucket(
            Bucket=s.wardwatch_bucket,
            CreateBucketConfiguration={"LocationConstraint": s.aws_region},
        )
        yield


@pytest.fixture(autouse=True)
def fakes():
    fake = FakeWhatsApp()
    set_messenger(fake)
    transcribe.set_transcribe_hook(lambda audio: "there is a big pothole near the bus stand")
    geocode.set_geocode_hook(lambda ward, text: (9.9252, 78.1198))
    set_vision_hook(
        lambda **kw: {
            "category": "pothole",
            "severity": "medium",
            "description": "Large pothole blocking one lane near the bus stand.",
            "needs_clarification": False,
            "clarification_question": None,
        }
    )
    set_text_hook(lambda sp, ut: "Likely subgrade failure — recommend infrastructure review.")
    yield fake
    notify._messenger = None
    transcribe.set_transcribe_hook(None)
    geocode.set_geocode_hook(None)
    set_vision_hook(None)
    set_text_hook(None)
