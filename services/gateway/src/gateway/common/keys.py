"""Gateway's RS256 signing keypair (SPEC.md §6.3, ADR 0002 §1, ADR 0005).

Gateway is the only signer in the system — its private key never leaves this
process. Generated once and cached on disk so restarts reuse the same key
(kitchen's JWKS cache and any live tokens survive a `docker compose restart
gateway`); a fresh clone or a wiped `gateway-keys` volume just generates a new
one, which is fine for a project that is never hosted (CLAUDE.md preamble) —
there is no production key to protect or rotate.
"""

import os
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

# services/gateway/ — anchored to this file rather than left as a bare
# relative path, so `uv run pytest` from the repo root, from this service
# directory, or from anywhere else all agree on one location instead of each
# scattering its own `keys/` wherever the process happened to be launched
# from. Docker overrides both env vars to an absolute `/app/keys/...` path
# (compose.yaml's `gateway-keys` volume) regardless.
_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_PRIVATE_KEY_PATH = Path(
    os.environ.get("JWT_PRIVATE_KEY_PATH", str(_SERVICE_ROOT / "keys" / "jwt_private.pem"))
)
_PUBLIC_KEY_PATH = Path(
    os.environ.get("JWT_PUBLIC_KEY_PATH", str(_SERVICE_ROOT / "keys" / "jwt_public.pem"))
)


def _generate_and_persist() -> RSAPrivateKey:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    _PUBLIC_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PUBLIC_KEY_PATH.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return private_key


@lru_cache(maxsize=1)
def get_private_key() -> RSAPrivateKey:
    if _PRIVATE_KEY_PATH.is_file():
        key = serialization.load_pem_private_key(_PRIVATE_KEY_PATH.read_bytes(), password=None)
        assert isinstance(key, RSAPrivateKey)
        return key
    return _generate_and_persist()


def get_public_key() -> RSAPublicKey:
    return get_private_key().public_key()


def get_private_key_pem() -> str:
    return get_private_key().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def get_public_key_pem() -> str:
    return get_public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


@lru_cache(maxsize=1)
def get_kid() -> str:
    """A stable id for the current key, derived from the public key itself —
    so it changes if and only if the key does, with no separate version to
    keep in sync by hand."""
    fingerprint = get_public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashes.Hash(hashes.SHA256())
    digest.update(fingerprint)
    return digest.finalize().hex()[:16]
