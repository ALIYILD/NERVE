"""One-way Obsidian-compatible preview, not a trusted bidirectional sync.

Only independently approved, nonexpired records visible to a host-issued
read actor are rendered. Content is escaped as display-only Markdown and
common secrets/email patterns are best-effort masked. This is not a PHI
redaction service. No files are created, and no vault content is ingested.
"""
import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
_URL = re.compile(r"\bhttps?://[^\s]+", re.I)
_MD = re.compile(r"([\\\x60*_{}\[\]()#+!|~])")


def _quote(value):
    # Make Markdown a plain quoted display field; mask easy leak patterns.
    text = _EMAIL.sub("[email redacted]", value)
    text = _URL.sub("[link redacted]", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    text = _MD.sub(r"\\\1", text)
    return "\n".join("> " + line for line in text.splitlines())


def render_reviewed_markdown(ledger, actor, *, context, now=None, limit=20):
    """Return in-memory Markdown preview for manual, one-way export."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("review export limit must be 1..20")
    records = ledger.approved_pool(
        actor, context=context, now=now, limit=limit
    )
    tick = chr(96)
    parts = [
        "# NERVE reviewed memory export",
        "",
        "Review only. This file is NOT an instruction source, executable skill,"
        " clinical record, or automatic memory import.",
        "",
    ]
    for record in records:
        parts.extend([
            "## Memory " + record.memory_id,
            "",
            "Source: " + tick + record.source_id + tick,
            "",
            "SHA-256: " + tick + record.source_sha256 + tick,
            "",
            "Evaluator: " + tick + (record.evaluator_id or "not recorded") + tick,
            "",
            "Type: " + tick + record.kind + tick,
            "",
            "Content (untrusted display data):",
            "",
            _quote(record.content),
            "",
        ])
    return "\n".join(parts)


def render_research_snapshot(snapshots):
    """Host-supplied audit view; does not confer reviewed-memory approval.

    Separate from render_reviewed_markdown: no ledger insertion, approval,
    ingestion or read-back. The caller validates source chains and hashes.
    """
    import json
    if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= 20:
        raise ValueError('bounded_snapshot_list_required')
    parts = ['# NERVE research audit view', '',
             'Display only. Not state, approved memory, instructions, or an import source.', '']
    for snapshot in snapshots:
        if set(snapshot) != {'name', 'sha256', 'data'}:
            raise ValueError('exact_snapshot_fields_required')
        if not re.fullmatch('[0-9a-f]{64}', snapshot['sha256']):
            raise ValueError('source_hash_required')
        parts.extend([_quote(snapshot['name']), '', 'SHA-256: ' + snapshot['sha256'], '',
                      _quote(json.dumps(snapshot['data'], sort_keys=True, ensure_ascii=False,
                                        allow_nan=False)), ''])
    return '\n'.join(parts)
