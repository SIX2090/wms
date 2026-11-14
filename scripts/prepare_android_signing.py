"""Restore approved mobile signing on an ephemeral CI runner; never imports WMS."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

_CERTIFICATE = "2f50f0d7552be34d83316ee5d1e88b328a5914b1a08c552f5d0d0f2dd5619e4c"


def _restore(bundle, directory, verify=subprocess.run):
    """Validate credentials and certificate before returning any Gradle environment."""
    if not bundle or len(bundle) > 64 * 1024:
        raise ValueError("missing or oversized WMS_MOBILE_SIGNING_BUNDLE")
    try:
        data = json.loads(bundle)
        keys = ("keystore_base64", "store_password", "key_alias", "key_password")
        if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or
                not data[k] or any(c in data[k] for c in "\r\n\x00") for k in keys):
            raise ValueError
        raw = base64.b64decode(data["keystore_base64"], validate=True)
        if not 100 <= len(raw) <= 32 * 1024:
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ValueError("invalid mobile signing bundle") from None
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="wms-mobile-", suffix=".p12", dir=directory)
    key = Path(path)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        env = dict(os.environ, WMS_SIGNING_STORE_PASSWORD=data["store_password"])
        result = verify(["keytool", "-exportcert", "-keystore", str(key),
            "-alias", data["key_alias"], "-storepass:env", "WMS_SIGNING_STORE_PASSWORD"],
            env=env, capture_output=True, check=False)
        if result.returncode != 0 or hashlib.sha256(result.stdout).hexdigest() != _CERTIFICATE:
            raise ValueError("mobile signing certificate mismatch or invalid keystore")
        return dict(WMS_STORE_FILE=str(key), WMS_STORE_PASSWORD=data["store_password"],
                    WMS_KEY_ALIAS=data["key_alias"], WMS_KEY_PASSWORD=data["key_password"])
    except BaseException:
        key.unlink(missing_ok=True)
        raise


def _main():
    try:
        values = _restore(os.environ.get("WMS_MOBILE_SIGNING_BUNDLE", ""),
                          Path(os.environ["RUNNER_TEMP"]))
        # GitHub masks whole JSON secrets, not necessarily their individual substrings.
        for name in ("WMS_STORE_PASSWORD", "WMS_KEY_PASSWORD", "WMS_KEY_ALIAS"):
            safe = values[name].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print("::add-mask::" + safe)
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8") as stream:
            for name, value in values.items():
                stream.write(f"{name}={value}\n")
        print("Fixed mobile signing certificate verified; release credentials prepared.")
    except Exception:
        # Do not print input, keytool stderr or an exception containing credential material.
        raise SystemExit("::error::Fixed mobile signing unavailable; refusing an ephemeral release signer") from None


if __name__ == "__main__":
    _main()
