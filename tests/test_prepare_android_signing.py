"""Credential restoration behavior; only synthetic bytes and a private temporary directory."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

_SPEC = importlib.util.spec_from_file_location("prepare_signing",
    Path(__file__).resolve().parents[1] / "scripts/prepare_android_signing.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class TestPrepareAndroidSigning(unittest.TestCase):
    def bundle(self, **changes):
        data = dict(keystore_base64=base64.b64encode(b"synthetic" * 100).decode(),
                    store_password="synthetic-password", key_alias="synthetic-alias",
                    key_password="synthetic-key-password")
        data.update(changes)
        return json.dumps(data)

    def test_missing_malformed_and_multiline_credentials_never_create_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for data in ("", "{bad", "[]", self.bundle(keystore_base64="invalid"),
                         self.bundle(store_password="x\nWMS_STORE_FILE=evil"),
                         self.bundle(key_alias=""), self.bundle(key_password=None)):
                with self.subTest(data=data):
                    with self.assertRaises(ValueError):
                        _MODULE._restore(data, root)
                    self.assertFalse(list(root.iterdir()))

    def test_valid_certificate_keeps_key_private_and_password_out_of_command(self):
        def verify(args, **kwargs):
            self.assertNotIn("synthetic-password", args)
            self.assertIn("-storepass:env", args)
            self.assertEqual("synthetic-password", kwargs["env"]["WMS_SIGNING_STORE_PASSWORD"])
            return types.SimpleNamespace(returncode=0, stdout=b"synthetic-cert")
        import hashlib
        with tempfile.TemporaryDirectory() as tmp, patch.object(_MODULE, "_CERTIFICATE",
                hashlib.sha256(b"synthetic-cert").hexdigest()):
            values = _MODULE._restore(self.bundle(), Path(tmp), verify)
            self.assertEqual(b"synthetic" * 100, Path(values["WMS_STORE_FILE"]).read_bytes())
            self.assertEqual("synthetic-key-password", values["WMS_KEY_PASSWORD"])

    def test_changed_certificate_and_bad_password_delete_restored_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            for code in (0, 1):
                with self.assertRaisesRegex(ValueError, "certificate mismatch"):
                    _MODULE._restore(self.bundle(), Path(tmp), lambda *a, **k:
                        types.SimpleNamespace(returncode=code, stdout=b"wrong-cert"))
                self.assertFalse(list(Path(tmp).iterdir()))


if __name__ == "__main__":
    unittest.main()
