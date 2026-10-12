"""Non-generating credential diagnosis; never prints credentials or raw errors."""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from nerve_awim.claude_pilot import NoRedirect, error_category


def check(key):
    result = {'present': bool(key), 'api_key_format': key.startswith('sk-ant-api'),
              'oauth_token_format': key.startswith('sk-ant-oat'),
              'surrounding_whitespace': key != key.strip(),
              'contains_whitespace': any(c.isspace() for c in key),
              'wrapped_in_quotes': key.startswith(('"', "'")),
              'generation_calls': 0}
    if not key or result['contains_whitespace'] or result['wrapped_in_quotes']:
        result['status'] = 'local_format_issue'
        return result
    try:
        request = urllib.request.Request('https://api.anthropic.com/v1/models?limit=1',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01'})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            result['http_status'] = response.status
            response.read(65536)
        result['status'] = 'models_endpoint_accepted'
    except urllib.error.HTTPError as error:
        result['http_status'] = error.code
        result['category'] = error_category(error.read(8192))
        result['status'] = 'models_endpoint_rejected'
    except Exception:
        result['status'] = 'request_failed'
    return result


if __name__ == '__main__':
    report = json.dumps(check(os.environ.get('ANTHROPIC_API_KEY', '')), indent=2)
    Path('claude-pilot-report.json').write_text(report)
    print(report)
