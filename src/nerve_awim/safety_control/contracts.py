"""Bounded, JSON-only contracts for the independently administered controller."""
import hashlib
import hmac
import json
import re


class SafetyDenied(PermissionError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def bounded(value, name, maximum=256):
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid ' + name)
    return value


def model_identity(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('model identity must be a lowercase SHA-256 digest')
    return value


def sign_owner_request(secret, action, payload, nonce, timestamp):
    message = canonical({'action': action, 'payload': payload, 'nonce': nonce, 'timestamp': timestamp})
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
