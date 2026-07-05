"""Ledger client — talks to the DocRegistry smart contract via JSON-RPC.

Uses raw urllib + Ethereum ABI encoding (no web3.py / eth-abi needed).
All calls go to a local Hardhat node (or any EVM JSON-RPC endpoint).

Test account: Hardhat default account #0 — well-known key used only for
local development. Never use in production.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("docverify_backend.ledger")

# ── Configuration ──────────────────────────────────────────────────────────────

def _resolve_ledger_url() -> str:
    url = os.getenv("LEDGER_RPC_URL")
    if url:
        return url
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in {"1", "true", "yes"}:
        return "http://ledger:8545"
    return "http://127.0.0.1:8545"

LEDGER_RPC_URL     = _resolve_ledger_url()
CONTRACT_ADDRESS   = os.getenv("LEDGER_CONTRACT_ADDRESS", "")

# Hardhat default account #0 — pre-funded test account, well-known key.
# Override via env vars for non-Hardhat networks.
SIGNER_ADDRESS     = os.getenv("LEDGER_SIGNER_ADDRESS", "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
SIGNER_PRIVATE_KEY = os.getenv("LEDGER_SIGNER_KEY",    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")

# ── Precomputed function selectors ─────────────────────────────────────────────
# keccak256(signature)[:4], verified with ethers.js:
#   keccak256(toUtf8Bytes("documentExists(bytes32)"))          → 0xcbfe6d41
#   keccak256(toUtf8Bytes("getDocument(bytes32)"))             → 0xb10d6b41
#   keccak256(toUtf8Bytes("recordDocument(bytes32,uint8,...")) → 0xa23509eb

_SEL_DOCUMENT_EXISTS = "0xcbfe6d41"
_SEL_GET_DOCUMENT    = "0xb10d6b41"
_SEL_RECORD_DOCUMENT = "0xa23509eb"

# ── ABI encoding ───────────────────────────────────────────────────────────────

def _encode_bytes32(hex_str: str) -> str:
    """Left-pad a hex string to exactly 32 bytes (64 hex chars)."""
    return hex_str.replace("0x", "").zfill(64)


def _encode_uint8(value: int) -> str:
    """ABI-encode a uint8 as a 32-byte word."""
    return format(value, "064x")


def _encode_one_string(s: str) -> str:
    """
    ABI-encode a single dynamic string:
      [32 bytes: byte length][N bytes: UTF-8 data, right-padded to 32-byte boundary]
    Returns hex string (no 0x prefix).
    """
    raw: bytes = s.encode("utf-8")
    byte_len = len(raw)
    # length word
    length_word = format(byte_len, "064x")
    # data, padded to the next 32-byte boundary
    data_hex = raw.hex()
    pad_chars = (64 - len(data_hex) % 64) % 64   # extra '0' chars
    return length_word + data_hex + ("0" * pad_chars)


def _encode_strings_with_offsets(base_offset_bytes: int, *strings: str) -> str:
    """
    Build the offset-table + data for N dynamic string arguments.

    base_offset_bytes: byte offset to where the first string's data begins,
                       relative to the start of the *whole* calldata payload
                       (after selector). Equals (number of static 32-byte words) * 32.

    Layout produced:
      [offset_0][offset_1]...[offset_n-1][string_0_data][string_1_data]...
    """
    encoded: list[str] = [_encode_one_string(s) for s in strings]

    offsets: list[str] = []
    current = base_offset_bytes
    for enc in encoded:
        offsets.append(format(current, "064x"))
        current += len(enc) // 2   # enc is hex chars; divide by 2 → bytes

    return "".join(offsets) + "".join(encoded)


# ── JSON-RPC transport ─────────────────────────────────────────────────────────

def _rpc_call(method: str, params: list[Any] | None = None) -> Any:
    """POST a JSON-RPC request to the Hardhat node."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method":  method,
        "params":  params or [],
        "id":      1,
    }).encode("utf-8")

    req = urllib.request.Request(
        LEDGER_RPC_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if "error" in body:
                raise RuntimeError(f"RPC error: {body['error']}")
            return body.get("result")
    except urllib.error.URLError as exc:
        logger.warning(f"Ledger RPC unavailable at {LEDGER_RPC_URL}: {exc}")
        raise


def _eth_call(to: str, data: str) -> str:
    """Read-only eth_call."""
    return _rpc_call("eth_call", [{"to": to, "data": data}, "latest"])


def _eth_send_transaction(to: str, data: str) -> str:
    """State-changing transaction. Hardhat auto-signs from SIGNER_ADDRESS."""
    return _rpc_call("eth_sendTransaction", [{
        "from": SIGNER_ADDRESS,
        "to":   to,
        "data": data,
        "gas":  "0x1000000",   # 16 M gas — generous for local node
    }])


# ── ABI decoding ───────────────────────────────────────────────────────────────

def _decode_return_string(data_hex: str, word_index: int) -> str | None:
    """
    Decode the string at `word_index` from an ABI-encoded tuple return value.

    The ABI return layout for getDocument() is:
      word 0  : fraudScore  (uint8,  static)
      word 1  : offset to riskBand   (dynamic)
      word 2  : offset to caseId     (dynamic)
      word 3  : offset to resultJson (dynamic)
      word 4  : analyzedAt (uint256, static)
      word 5  : analyzedBy (address, static)

    For a dynamic word the value stored is the *byte* offset from the start
    of the return data to where the string's length prefix lives.
    """
    try:
        data = data_hex[2:] if data_hex.startswith("0x") else data_hex

        # Read the offset stored at word_index (each word = 64 hex chars)
        slot_start = word_index * 64
        byte_offset = int(data[slot_start : slot_start + 64], 16)
        hex_offset  = byte_offset * 2          # convert byte offset → hex char index

        # Length word at that offset
        str_byte_len = int(data[hex_offset : hex_offset + 64], 16)

        # String bytes immediately follow
        str_hex = data[hex_offset + 64 : hex_offset + 64 + str_byte_len * 2]
        return bytes.fromhex(str_hex).decode("utf-8")

    except Exception as exc:
        logger.warning(f"Failed to decode string at word {word_index}: {exc}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def file_sha256_hex(payload: bytes) -> str:
    """Return the SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(payload).hexdigest()


def check_document(file_hash_hex: str) -> dict[str, Any] | None:
    """
    Check the on-chain registry for a previously analysed document.

    Returns the cached CaseResult dict (with ledger_cached=True) if found,
    or None if not recorded or the ledger is unreachable (fail-open).
    """
    if not CONTRACT_ADDRESS:
        logger.debug("LEDGER_CONTRACT_ADDRESS not set — skipping ledger check")
        return None

    try:
        # ── Step 1: documentExists(bytes32) ──
        calldata = _SEL_DOCUMENT_EXISTS + _encode_bytes32(file_hash_hex)
        result   = _eth_call(CONTRACT_ADDRESS, calldata)

        exists = bool(int(result, 16))
        if not exists:
            logger.debug(f"Ledger miss for {file_hash_hex[:12]}…")
            return None

        # ── Step 2: getDocument(bytes32) ──
        calldata = _SEL_GET_DOCUMENT + _encode_bytes32(file_hash_hex)
        result   = _eth_call(CONTRACT_ADDRESS, calldata)

        # resultJson is the 4th return value → offset word at index 3
        result_json_str = _decode_return_string(result, word_index=3)
        if not result_json_str:
            return None

        cached = json.loads(result_json_str)
        cached["ledger_cached"] = True
        logger.info(f"Ledger cache HIT for {file_hash_hex[:12]}…")
        return cached

    except Exception as exc:
        logger.warning(f"Ledger check failed, falling back to pipeline: {exc}")
        return None


def record_document(file_hash_hex: str, fraud_score: int, risk_band: str,
                    case_id: str, result_json: str) -> bool:
    """
    Write a new analysis result to the on-chain registry.

    Solidity signature:
      recordDocument(bytes32 fileHash, uint8 fraudScore,
                     string riskBand, string caseId, string resultJson)

    ABI layout (all offsets relative to start of calldata, after selector):
      word 0: fileHash     (bytes32, static)
      word 1: fraudScore   (uint8,   static)
      word 2: offset to riskBand   (dynamic)
      word 3: offset to caseId     (dynamic)
      word 4: offset to resultJson (dynamic)
      [string data follows]

    Static head = 5 words = 160 bytes. The first dynamic arg (riskBand)
    starts at byte 160.
    """
    if not CONTRACT_ADDRESS:
        logger.debug("LEDGER_CONTRACT_ADDRESS not set — skipping ledger record")
        return False

    try:
        static_head_bytes = 5 * 32   # 5 words × 32 bytes

        hash_word  = _encode_bytes32(file_hash_hex)
        score_word = _encode_uint8(fraud_score)
        dynamic    = _encode_strings_with_offsets(
            static_head_bytes,
            risk_band, case_id, result_json,
        )

        calldata = _SEL_RECORD_DOCUMENT + hash_word + score_word + dynamic

        tx_hash = _eth_send_transaction(CONTRACT_ADDRESS, calldata)
        logger.info(f"Ledger record OK — hash {file_hash_hex[:12]}… tx {tx_hash}")
        return True

    except Exception as exc:
        logger.warning(f"Ledger record failed (non-fatal): {exc}")
        return False
