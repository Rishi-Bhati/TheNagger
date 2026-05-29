"""
lib/telegram_auth.py — Secure authentication & session management.
Provides verification of Telegram Login Widget data and secure,
HMAC-signed & obfuscated session tokens.
"""
import hashlib
import hmac
import json
import time
import base64

def verify_telegram_login(params: dict, bot_token: str) -> dict:
    """
    Verify Telegram Login Widget data cryptographically.
    Returns user dict on success, or None on failure.
    """
    if "hash" not in params:
        return None

    check_hash = params.pop("hash")
    
    # Data string: sorted key=value pairs joined by \n
    data_check = "\n".join(
        f"{k}={params[k]}" for k in sorted(params.keys())
    )
    
    # Secret = SHA256(bot_token)
    secret = hashlib.sha256(bot_token.encode()).digest()
    
    # HMAC-SHA256
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(computed, check_hash):
        return None
    
    # Prevent replay attacks: check auth_date is within last 24 hours
    try:
        auth_date = int(params.get("auth_date", 0))
        if time.time() - auth_date > 86400:
            return None
    except ValueError:
        return None
    
    return {
        "telegram_id": int(params["id"]),
        "first_name": params.get("first_name", ""),
        "last_name": params.get("last_name", ""),
        "username": params.get("username", ""),
        "photo_url": params.get("photo_url", ""),
    }

def _obfuscate(data: bytes, key: bytes) -> bytes:
    """Simple XOR obfuscation for additional privacy of the payload."""
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def create_session_token(telegram_id: int, secret: str) -> str:
    """
    Create a highly secure session token.
    Payload is obfuscated to hide user ID, base64 encoded, 
    and cryptographically signed using HMAC-SHA256 to prevent tampering.
    """
    payload = json.dumps({"tid": telegram_id, "iat": int(time.time())}).encode()
    secret_bytes = secret.encode()
    
    # Obfuscate to prevent plain-text exposure of user ID (Privacy)
    obfuscated = _obfuscate(payload, secret_bytes)
    payload_b64 = base64.urlsafe_b64encode(obfuscated).decode().rstrip("=")
    
    # Sign cryptographically (Integrity & Authenticity)
    sig = hmac.new(secret_bytes, payload_b64.encode(), hashlib.sha256).hexdigest()
    
    return f"{payload_b64}.{sig}"

def verify_session_token(token: str, secret: str, max_age: int = 604800) -> int:
    """
    Verify token authenticity and integrity, then return telegram_id.
    Prevents forged tokens and expired sessions (Default max_age: 7 days).
    Returns telegram_id or None.
    """
    if not token or "." not in token:
        return None
        
    parts = token.split(".")
    if len(parts) != 2:
        return None
        
    payload_b64, sig = parts
    secret_bytes = secret.encode()
    
    # Verify signature first (prevents tampering)
    expected_sig = hmac.new(secret_bytes, payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
        
    try:
        # Re-add padding if necessary
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        obfuscated = base64.urlsafe_b64decode(payload_b64 + padding)
        
        # De-obfuscate
        payload_bytes = _obfuscate(obfuscated, secret_bytes)
        payload = json.loads(payload_bytes.decode())
        
        # Check expiration
        if time.time() - payload.get("iat", 0) > max_age:
            return None
            
        return payload.get("tid")
    except Exception:
        return None
