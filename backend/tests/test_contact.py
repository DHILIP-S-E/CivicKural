import boto3

from wardwatch import contact
from wardwatch.config import get_settings


def test_contact_is_kms_encrypted_and_recoverable(monkeypatch):
    key = boto3.client("kms", region_name="ap-south-1").create_key()["KeyMetadata"]["KeyId"]
    monkeypatch.setenv("CONTACT_KMS_KEY_ID", key)
    get_settings.cache_clear()
    ciphertext = contact.protect("919000011111", "MDU-CORP")
    assert ciphertext and "919000011111" not in ciphertext
    assert contact.reveal(ciphertext, "MDU-CORP") == "919000011111"
