# Claude pilot, 11 October 2026

User authorized one ten-iteration nonclinical experiment, maximum USD 10 total,
using GitHub repository secret `claude_git`. The secret is passed only to the
pilot step as ANTHROPIC_API_KEY; it is not retrieved or displayed in chat.

The workflow runs only on a main push changing research/claude-pilot-launch.txt
with the exact dedicated launch message, and only on run_attempt 1. There is no
schedule or manual dispatch. Do not reuse the launch message/file for another
paid experiment. Reruns are disabled because runner-local budget storage is not
a cross-run account budget. Other workflows and other account usage are outside
this pilot's spending scope.

The fixed model is claude-sonnet-4-6. Global standard prices checked on
2026-10-11: USD 3 per million input tokens and USD 15 per million output tokens.
Each call reserves USD 3.01536 (the full one-million-token supported input context
plus 1024 maximum output tokens). Confirmed usage settles the reservation at
those rates. Uncertain/failed requests retain their reservation and abort. No
retries, tools, caching, images, extended thinking or generated-code execution
are enabled. At most 120 paid calls; at most USD 10 reserved/settled combined.
The ledger is exclusive-create SQLite and records no key, prompt or response.
Budget calculations assume the documented pricing remains valid; reported cost
is token-based accounting, not a fetched invoice. HTTP requests have a 60-second
socket timeout and the workflow a 25-minute overall limit.

Tasks are synthetic Python source extraction, independently judged with ast.parse,
not executed. Three training, five selection and five final tasks have distinct
names/sources generated from the run ID. They share a narrow template, so this
is a connectivity/learning-mechanics pilot, not evidence of broad adaptation.
Baseline and candidate use the same model and output budget; the baseline already
gets a complete task specification. Ten proposals use only training examples and
selection summaries; exact duplicate lessons skip selection calls. Final data is
opened only if a candidate improves selection without observed regressions.
No gain is a valid outcome. Nothing approves memory or deploys a model.

Sources:
- https://platform.claude.com/docs/en/about-claude/pricing
- https://platform.claude.com/docs/en/models/sonnet-4-6/overview
- https://platform.claude.com/docs/en/api/http/messages
