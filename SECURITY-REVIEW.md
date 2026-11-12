# Security review

Reviewed: 2026-11-12

## Open findings

| Severity | Location | Finding | Status |
|---|---|---|---|
| Medium | `app.py:147-149`; `templates/attempts_table.html:1` | Reflected XSS: `sort_link` inserts arbitrary query parameters into HTML marked safe without URL or attribute encoding. | Open |

Use URL encoding or Jinja URL generation rather than constructing safe HTML from untrusted query parameters, and remove the `|safe` boundary.
