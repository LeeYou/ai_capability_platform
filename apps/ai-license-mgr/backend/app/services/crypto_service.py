from __future__ import annotations

from base64 import b64decode, b64encode
import hashlib
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def generate_key_pair_files(key_pairs_root: Path, key_name: str) -> tuple[Path, Path]:
    key_dir = (key_pairs_root / key_name).resolve()
    if not (key_dir == key_pairs_root or key_pairs_root in key_dir.parents):
        raise ValueError("密钥目录非法。")
    key_dir.mkdir(parents=True, exist_ok=True)

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_key_path = key_dir / "private_key.pem"
    public_key_path = key_dir / "public_key.pem"

    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_key_path.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    os.chmod(private_key_path, 0o600)
    os.chmod(public_key_path, 0o644)
    return private_key_path.resolve(), public_key_path.resolve()


def sign_payload(private_key_path: Path, payload: dict[str, object]) -> str:
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("仅支持 ed25519 私钥。")
    signature = private_key.sign(_canonical_json_bytes(payload))
    return b64encode(signature).decode("ascii")


def verify_signature(public_key_path: Path, payload: dict[str, object], signature_base64: str) -> bool:
    public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        raise ValueError("仅支持 ed25519 公钥。")
    try:
        public_key.verify(b64decode(signature_base64), _canonical_json_bytes(payload))
        return True
    except InvalidSignature:
        return False


def generate_hardware_fingerprint(features: dict[str, str]) -> str:
    normalized = "|".join(f"{key.strip().lower()}={value.strip()}" for key, value in sorted(features.items()))
    if not normalized:
        raise ValueError("至少需要一个硬件特征。")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
