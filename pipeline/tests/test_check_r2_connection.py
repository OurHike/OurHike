"""Tests for check_r2_connection.py - a read-only credentials/connectivity
check, kept separate from publish.py so a bad credential shows up before
anything tries to upload. Real network/S3 calls are never allowed in the
suite (see test_publish.py) - moto mocks S3/R2 instead of hitting a real
bucket."""

import boto3
import pytest
from moto import mock_aws

import check_r2_connection

BUCKET = "ourhike-test-bucket"


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_check_succeeds_when_bucket_is_reachable(s3_client):
    ok, message = check_r2_connection.check(s3_client=s3_client, bucket=BUCKET)

    assert ok is True
    assert BUCKET in message


def test_check_fails_when_bucket_does_not_exist(s3_client):
    ok, message = check_r2_connection.check(s3_client=s3_client, bucket="does-not-exist")

    assert ok is False
    assert "does not exist" in message


def test_check_reports_missing_environment_variables(monkeypatch):
    for name in check_r2_connection.REQUIRED_VARS:
        monkeypatch.delenv(name, raising=False)

    ok, message = check_r2_connection.check()

    assert ok is False
    assert "R2_ENDPOINT_URL" in message
