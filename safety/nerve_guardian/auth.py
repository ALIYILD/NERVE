"""Independent owner authentication. Keys and identities are operator pinned."""
from dataclasses import dataclass
import time


class AuthorizationError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant: str
    auth_time: int
    jti: str
    expires_at: int
    verified_mfa: bool = True


class OwnerVerifier:
    def __init__(self, *, issuer, audience, public_keys, owners, mfa_acr=(), freshness_seconds=300):
        import jwt
        if not issuer.startswith('https://') or not audience or not public_keys or not owners:
            raise ValueError('pinned owner identity configuration required')
        if not 1 <= freshness_seconds <= 300:
            raise ValueError('invalid authentication freshness')
        self.jwt = jwt
        self.issuer, self.audience = issuer, audience
        self.keys, self.owners = dict(public_keys), dict(owners)
        self.mfa_acr, self.freshness = frozenset(mfa_acr), freshness_seconds

    def verify(self, token, *, restart=False):
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise ValueError()
            header = self.jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or header.get('kid') not in self.keys:
                raise ValueError()
            claims = self.jwt.decode(token, self.keys[header['kid']], algorithms=['RS256'],
                issuer=self.issuer, audience=self.audience,
                options={'require': ['sub', 'iss', 'aud', 'exp', 'iat', 'nbf', 'auth_time', 'jti']})
            # Pinned subjects must represent separately administered human accounts.
            # Delegation/service claims cannot transform an agent into that owner.
            if any(key in claims for key in ('act', 'may_act', 'actor_token', 'obo')):
                raise ValueError()
            if any(claims.get(key) in ('client_credentials', 'client-credentials', 'service_account', 'agent', 'machine')
                   for key in ('grant_type', 'gty', 'identity_type', 'actor_type', 'principal_type')):
                raise ValueError()
            if claims.get('is_service_account') is True or claims.get('is_agent') is True:
                raise ValueError()
            now = int(time.time())
            if any(type(claims[k]) is not int for k in ('exp', 'iat', 'nbf', 'auth_time')):
                raise ValueError()
            if not (0 < claims['auth_time'] <= claims['iat'] <= now < claims['exp']):
                raise ValueError()
            subject, jti = claims['sub'], claims['jti']
            if not isinstance(subject, str) or subject not in self.owners:
                raise ValueError()
            if not isinstance(jti, str) or not 8 <= len(jti) <= 256:
                raise ValueError()
            amr = claims.get('amr', [])
            if not (isinstance(amr, list) and 'mfa' in amr) and claims.get('acr') not in self.mfa_acr:
                raise ValueError()
            if restart and now - claims['auth_time'] > self.freshness:
                raise ValueError()
            return Principal(subject, self.owners[subject], claims['auth_time'], jti, claims['exp'])
        except (self.jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise AuthorizationError('owner authentication denied') from None
