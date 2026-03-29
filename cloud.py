#!/usr/bin/env python3
"""R2/S3 cloud storage for zen-sync. No external dependencies."""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def sign_aws_v4(method, url, headers, payload, region, service, access_key, secret_key):
    """AWS Signature V4 signing."""
    from urllib.parse import urlparse, quote

    parsed = urlparse(url)
    host = parsed.hostname
    path = quote(parsed.path or "/", safe="/")
    query = parsed.query or ""

    now = datetime.now(timezone.utc)
    datestamp = now.strftime("%Y%m%d")
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")

    headers["host"] = host
    headers["x-amz-date"] = amzdate
    headers["x-amz-content-sha256"] = hashlib.sha256(payload).hexdigest()

    signed_headers = sorted(headers.keys())
    signed_headers_str = ";".join(signed_headers)

    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in signed_headers)
    canonical_request = "\n".join([
        method, path, query, canonical_headers,
        signed_headers_str, hashlib.sha256(payload).hexdigest()
    ])

    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256", amzdate, credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest()
    ])

    def hmac_sha256(key, msg):
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    signing_key = hmac_sha256(
        hmac_sha256(
            hmac_sha256(
                hmac_sha256(f"AWS4{secret_key}".encode(), datestamp),
                region
            ),
            service
        ),
        "aws4_request"
    )

    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, Signature={signature}"
    )

    return headers


def r2_request(method, key, data, config):
    """Make a signed request to R2."""
    account_id = config["account_id"]
    bucket = config["bucket"]
    access_key = config["access_key"]
    secret_key = config["secret_key"]

    url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket}/{key}"
    headers = {"content-type": "application/octet-stream"} if data else {}

    signed = sign_aws_v4(
        method, url, headers, data or b"",
        "auto", "s3", access_key, secret_key
    )

    req = Request(url, data=data if method == "PUT" else None, method=method)
    for k, v in signed.items():
        req.add_header(k, v)

    try:
        resp = urlopen(req, timeout=60)
        return resp.read() if method == "GET" else True
    except HTTPError as e:
        if e.code == 404 and method == "GET":
            return None
        raise


def encrypt_age(data, config):
    """Encrypt data with age."""
    age_mode = config.get("age_mode", "keyfile")

    if age_mode == "passphrase":
        passphrase_path = os.path.join(config.get("config_dir", os.path.expanduser("~/.config/zen-sync")), "passphrase")
        passphrase_path = os.path.expanduser(passphrase_path)
        with open(passphrase_path) as f:
            passphrase = f.read().strip()
        proc = subprocess.run(
            ["age", "-p"],
            input=data, capture_output=True,
            env={**os.environ, "AGE_PASSPHRASE": passphrase}
        )
    else:
        key_path = os.path.expanduser(config["age_key_path"])
        # Get public key from secret key
        result = subprocess.run(
            ["age-keygen", "-y", key_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            with open(key_path) as f:
                for line in f:
                    if line.startswith("# public key:"):
                        recipient = line.split(":", 1)[1].strip()
                        break
                else:
                    raise RuntimeError("age-keygen not found. Install age.")
        else:
            recipient = result.stdout.strip()

        proc = subprocess.run(
            ["age", "-r", recipient],
            input=data, capture_output=True
        )

    if proc.returncode != 0:
        raise RuntimeError(f"age encrypt failed: {proc.stderr.decode()}")
    return proc.stdout


def decrypt_age(data, config):
    """Decrypt data with age."""
    age_mode = config.get("age_mode", "keyfile")

    if age_mode == "passphrase":
        passphrase_path = os.path.join(config.get("config_dir", os.path.expanduser("~/.config/zen-sync")), "passphrase")
        passphrase_path = os.path.expanduser(passphrase_path)
        with open(passphrase_path) as f:
            passphrase = f.read().strip()
        proc = subprocess.run(
            ["age", "-d"],
            input=data, capture_output=True,
            env={**os.environ, "AGE_PASSPHRASE": passphrase}
        )
    else:
        key_path = os.path.expanduser(config["age_key_path"])
        proc = subprocess.run(
            ["age", "-d", "-i", key_path],
            input=data, capture_output=True
        )

    if proc.returncode != 0:
        raise RuntimeError(f"age decrypt failed: {proc.stderr.decode()}")
    return proc.stdout


def pack_files(profile_path, files):
    """Pack session files into a tar.gz archive."""
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in files:
            full = os.path.join(profile_path, f)
            if os.path.exists(full):
                tar.add(full, arcname=f)
    return buf.getvalue()


def unpack_files(data, profile_path):
    """Unpack tar.gz archive into profile directory."""
    buf = BytesIO(data)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        # Security: only extract expected paths
        for member in tar.getmembers():
            if member.name.startswith("/") or ".." in member.name:
                continue
            tar.extract(member, profile_path)


def cmd_push(config, profile_path, files):
    """Pack, encrypt, upload session files to R2."""
    archive = pack_files(profile_path, files)
    encrypted = encrypt_age(archive, config)
    r2_request("PUT", "session.tar.gz.age", encrypted, config)

    # Also upload a metadata file
    meta = json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": os.uname().nodename,
        "files": files,
        "size": len(archive),
    }).encode()
    encrypted_meta = encrypt_age(meta, config["age_key_path"])
    r2_request("PUT", "meta.json.age", encrypted_meta, config)

    return len(archive), len(encrypted)


def cmd_pull(config, profile_path, files):
    """Download, decrypt, unpack session files from R2."""
    encrypted = r2_request("GET", "session.tar.gz.age", None, config)
    if encrypted is None:
        return None
    archive = decrypt_age(encrypted, config["age_key_path"])
    unpack_files(archive, profile_path)
    return len(archive)


def cmd_status(config):
    """Get metadata about the remote session."""
    encrypted = r2_request("GET", "meta.json.age", None, config)
    if encrypted is None:
        return None
    meta = decrypt_age(encrypted, config["age_key_path"])
    return json.loads(meta)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <push|pull|status> <config_json>")
        sys.exit(1)

    cmd = sys.argv[1]
    config = json.loads(sys.argv[2])

    files = [
        "zen-sessions.jsonlz4",
        "zen-sessions-backup/clean.jsonlz4",
        "sessionstore-backups/recovery.jsonlz4",
        "sessionstore-backups/recovery.baklz4",
        "sessionstore-backups/previous.jsonlz4",
        "prefs.js",
        "containers.json",
    ]

    if cmd == "test":
        try:
            account_id = config["account_id"]
            bucket = config["bucket"]
            url = f"https://{account_id}.r2.cloudflarestorage.com/{bucket}?list-type=2&max-keys=1"
            headers = {"content-type": "application/xml"}
            signed = sign_aws_v4(
                "GET", url, headers, b"",
                "auto", "s3", config["access_key"], config["secret_key"]
            )
            req = Request(url, method="GET")
            for k, v in signed.items():
                req.add_header(k, v)
            urlopen(req, timeout=10)
            print("ok")
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
    elif cmd == "push":
        raw, enc = cmd_push(config, config["profile"], files)
        print(json.dumps({"raw_size": raw, "encrypted_size": enc}))
    elif cmd == "pull":
        size = cmd_pull(config, config["profile"], files)
        if size is None:
            print(json.dumps({"error": "no remote session found"}))
        else:
            print(json.dumps({"size": size}))
    elif cmd == "status":
        meta = cmd_status(config)
        if meta is None:
            print(json.dumps({"error": "no remote session found"}))
        else:
            print(json.dumps(meta))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
