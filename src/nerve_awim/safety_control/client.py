"""Bounded local IPC. Runtime clients carry no owner or observer credentials."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

MAX_BYTES = 65536


class SafetyUnavailable(PermissionError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class RuntimeClient:
    def __init__(self, endpoint, credential, *, timeout=3):
        parsed = urlsplit(endpoint)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or
                parsed.username or parsed.password or parsed.path not in ('', '/') or
                parsed.query or parsed.fragment or not parsed.port):
            raise ValueError('explicit IPv4 loopback controller endpoint required')
        if not isinstance(credential, str) or not credential or '\n' in credential or '\r' in credential:
            raise ValueError('runtime credential required')
        if not 0 < timeout <= 30:
            raise ValueError('bounded timeout required')
        self.endpoint = endpoint.rstrip('/')
        self._credential = credential
        self.timeout = timeout

    def dispatch(self, scope, tool, model_digest, arguments):
        payload = json.dumps(dict(scope=scope, tool=tool, model_digest=model_digest,
                                  arguments=arguments), allow_nan=False).encode()
        if len(payload) > MAX_BYTES:
            raise ValueError('controller request too large')
        request = Request(self.endpoint + '/dispatch', data=payload, method='POST',
                          headers={'Content-Type': 'application/json',
                                   'Authorization': 'Bearer ' + self._credential})
        try:
            opener = build_opener(ProxyHandler({}), _NoRedirect())
            with opener.open(request, timeout=self.timeout) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise SafetyUnavailable('controller response too large')
                result = json.loads(body)
                if type(result) is not dict or set(result) != {'value'}:
                    raise SafetyUnavailable('invalid controller response')
                return result['value']
        except (HTTPError, URLError, OSError, ValueError) as exc:
            raise SafetyUnavailable('independent controller denied or unavailable') from None
