"""
Vault Decryptor — decrypt OpenClaw .vault/*.enc files (version 7).
Also provides fallback: load credentials from environment or config.

Encryption format (version 7):
  - KDF: PBKDF2-SHA512 with 500,000 iterations
  - Cipher: AES-256-CBC
  - Key derived from machine-id
  - Fields: ct (ciphertext hex), iv (hex), nonce (salt hex), auth (HMAC-SHA512 hex)
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

VAULT_DIR = "/data/.openclaw/workspace/.vault"


def _get_machine_id() -> str:
    """Read /etc/machine-id."""
    with open("/etc/machine-id", "r") as f:
        return f.read().strip()


def decrypt_vault_file(filepath: str) -> Optional[str]:
    """
    Attempt to decrypt a .vault/*.enc JSON file (version 7).
    Returns plaintext string or None if decryption fails.
    """
    try:
        with open(filepath, "r") as f:
            vault = json.load(f)

        if vault.get("version") != 7:
            logger.warning(f"Unsupported vault version: {vault.get('version')}")
            return None

        ct = bytes.fromhex(vault["ct"])
        iv = bytes.fromhex(vault["iv"])
        salt = bytes.fromhex(vault["nonce"])
        auth_expected = vault["auth"]
        machine_id = _get_machine_id()

        # Try multiple key derivation strategies
        passwords = [
            machine_id.encode(),
            f"{machine_id}:polymarket".encode(),
            f"polymarket:{machine_id}".encode(),
        ]

        for pw in passwords:
            for dklen in [32, 64]:
                key_material = hashlib.pbkdf2_hmac("sha512", pw, salt, 500_000, dklen=dklen)
                aes_key = key_material[:32]
                hmac_key = key_material[32:] if dklen == 64 else key_material

                # Try different HMAC constructions
                for payload in [iv + ct, ct + iv, ct]:
                    computed = hmac.new(hmac_key, payload, hashlib.sha512).hexdigest()
                    if hmac.compare_digest(computed, auth_expected):
                        # HMAC matches — decrypt
                        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                        from cryptography.hazmat.primitives import padding
                        decryptor = Cipher(algorithms.AES(aes_key), modes.CBC(iv)).decryptor()
                        padded = decryptor.update(ct) + decryptor.finalize()
                        unpadder = padding.PKCS7(128).unpadder()
                        plaintext = unpadder.update(padded) + unpadder.finalize()
                        return plaintext.decode("utf-8")

        logger.warning(f"Could not decrypt {filepath} — HMAC mismatch with all key strategies")
        return None

    except FileNotFoundError:
        logger.error(f"Vault file not found: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Vault decryption error for {filepath}: {e}")
        return None


def get_polymarket_private_key() -> Optional[str]:
    """
    Get Polymarket wallet private key.
    Priority: 1) vault decrypt 2) POLYMARKET_PRIVATE_KEY env 3) PRIVATE_KEY env
    """
    # Try vault
    filepath = os.path.join(VAULT_DIR, "polymarket.enc")
    if os.path.exists(filepath):
        plaintext = decrypt_vault_file(filepath)
        if plaintext:
            # Might be JSON with a 'key' or 'private_key' field, or raw hex
            try:
                data = json.loads(plaintext)
                return data.get("private_key") or data.get("key") or data.get("seed")
            except json.JSONDecodeError:
                return plaintext.strip()

    # Fallback to env
    return os.getenv("POLYMARKET_PRIVATE_KEY") or os.getenv("PRIVATE_KEY") or None


def get_polymarket_clob_creds() -> Optional[dict]:
    """
    Get CLOB API credentials.
    Priority: 1) vault decrypt 2) environment variables 3) hardcoded (from task)
    """
    # Try vault
    filepath = os.path.join(VAULT_DIR, "polymarket-clob.enc")
    if os.path.exists(filepath):
        plaintext = decrypt_vault_file(filepath)
        if plaintext:
            try:
                return json.loads(plaintext)
            except json.JSONDecodeError:
                pass

    # Fallback to env
    api_key = os.getenv("CLOB_API_KEY")
    api_secret = os.getenv("CLOB_API_SECRET")
    api_passphrase = os.getenv("CLOB_PASSPHRASE")

    if api_key and api_secret and api_passphrase:
        return {
            "api_key": api_key,
            "api_secret": api_secret,
            "api_passphrase": api_passphrase,
        }

    return None
