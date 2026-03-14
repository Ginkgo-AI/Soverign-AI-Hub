"""Agent identity service — cryptographic signing and verification of agent actions."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentDefinition
from app.models.agent_identity import AgentAction

logger = logging.getLogger(__name__)

# In-memory cache of private keys (agent_id -> private_key)
# In production, these would be stored in a secure enclave or HSM
_private_keys: dict[str, Ed25519PrivateKey] = {}


def generate_keypair() -> tuple[str, str, str]:
    """Generate an ed25519 keypair.

    Returns:
        (public_key_pem, private_key_pem, signing_key_hash)
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

    # Hash of the private key for identification (not the key itself)
    key_hash = hashlib.sha256(priv_pem.encode()).hexdigest()

    return pub_pem, priv_pem, key_hash


async def assign_identity(
    db: AsyncSession,
    agent_id: uuid.UUID,
) -> dict[str, str]:
    """Generate and assign a cryptographic identity to an agent."""
    result = await db.execute(
        select(AgentDefinition).where(AgentDefinition.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise ValueError("Agent not found")

    pub_pem, priv_pem, key_hash = generate_keypair()

    agent.public_key = pub_pem
    agent.signing_key_hash = key_hash

    # Cache private key in memory
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    _private_keys[str(agent_id)] = load_pem_private_key(priv_pem.encode(), password=None)

    await db.flush()
    logger.info("Assigned cryptographic identity to agent %s", agent_id)

    return {"public_key": pub_pem, "signing_key_hash": key_hash}


def sign_action(
    agent_id: uuid.UUID,
    payload: dict[str, Any],
) -> tuple[str, str]:
    """Sign an action payload.

    Returns:
        (action_hash, signature_b64)
    """
    private_key = _private_keys.get(str(agent_id))
    if private_key is None:
        raise ValueError(f"No signing key loaded for agent {agent_id}")

    # Canonical JSON for consistent hashing
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    action_hash = hashlib.sha256(canonical.encode()).hexdigest()

    signature = private_key.sign(canonical.encode())
    signature_b64 = base64.b64encode(signature).decode()

    return action_hash, signature_b64


def verify_action(
    public_key_pem: str,
    payload: dict[str, Any],
    signature_b64: str,
) -> bool:
    """Verify an action signature."""
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        public_key = load_pem_public_key(public_key_pem.encode())
        if not isinstance(public_key, Ed25519PublicKey):
            return False

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, canonical.encode())
        return True
    except Exception:
        return False


async def record_signed_action(
    db: AsyncSession,
    agent_id: uuid.UUID,
    execution_id: uuid.UUID,
    action_type: str,
    payload: dict[str, Any],
) -> AgentAction | None:
    """Sign and record an agent action. Returns None if agent has no identity."""
    if str(agent_id) not in _private_keys:
        return None

    try:
        action_hash, signature = sign_action(agent_id, payload)
    except ValueError:
        return None

    action = AgentAction(
        agent_id=agent_id,
        execution_id=execution_id,
        action_type=action_type,
        action_hash=action_hash,
        signature=signature,
        payload_summary=json.dumps(payload)[:500],
    )
    db.add(action)
    await db.flush()
    return action
