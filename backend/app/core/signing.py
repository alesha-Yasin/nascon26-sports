import hmac
import hashlib
import json

from app.core.config import settings


def canonical_json(obj) -> str:
    """Recursively sort keys, no whitespace, non-ASCII not escaped."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_payload(id_: str, payload_obj: dict) -> str:
    """
    HMAC-SHA256 signature per Section 5.3.
    Key = DAY1_SALT as UTF-8 bytes.
    Message = id + "|" + canonical_json(payload_obj) as UTF-8 bytes.
    Output = lowercase hex, 64 chars.
    """
    salt = settings.DAY1_SALT.encode("utf-8")
    message = (id_ + "|" + canonical_json(payload_obj)).encode("utf-8")
    return hmac.new(salt, message, hashlib.sha256).hexdigest()


def lots_key(seed: int, league_id: str, team_id: str) -> str:
    """Draw-lots hash per Section 5.10."""
    return hashlib.sha256(
        f"{seed}|{league_id}|{team_id}".encode("utf-8")
    ).hexdigest()
