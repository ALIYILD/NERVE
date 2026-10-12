"""Small reference client; accepts externally obtained bearer credentials."""
import json
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer credential through redirects.


class MemoryClient:
    def __init__(self, base_url, token, *, allow_loopback_http=False, timeout=5):
        parsed = urlsplit(base_url)
        if (parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/') or not parsed.hostname
                or (parsed.scheme != 'https' and not (allow_loopback_http
                    and parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')))):
            raise ValueError('HTTPS origin or explicitly enabled loopback HTTP required')
        if type(token) is not str or not token or '\r' in token or '\n' in token:
            raise ValueError('bearer token required')
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise ValueError('bounded timeout required')
        self.base_url, self._token, self.timeout = base_url.rstrip('/'), token, timeout
        self._opener = build_opener(_NoRedirect())

    def request(self, method, path, body=None):
        from .service import MemoryService
        if (method, path) not in MemoryService.ROUTES and not (
                method == 'DELETE' and path.startswith('/v1/memory/records/')
                and path[len('/v1/memory/records/'):].isalnum()):
            raise ValueError('allowlisted memory endpoint required')
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = Request(self.base_url + path, data=data, method=method,
                          headers={'Authorization': 'Bearer ' + self._token,
                                   'Content-Type': 'application/json'})
        with self._opener.open(request, timeout=self.timeout) as response:
            raw = response.read(262145)
            if len(raw) > 262144:
                raise ValueError('response size limit')
            return json.loads(raw)

    def query(self, *, clinic_id, patient_id, query, limit=5):
        return self.request('POST', '/v1/memory/query', dict(
            clinic_id=clinic_id, patient_id=patient_id, query=query, limit=limit))
