# Security review

Reviewed: 2026-11-12

## Open findings

| Severity | Location | Finding | Status |
|---|---|---|---|
| High | `app.py:184` | Learners without a `client_id` bypass the tenant comparison and can enrol in and view another client's course. | Open |

Do not treat a missing learner client as global access. Require every learner's
`client_id` to equal the course client, and reserve cross-client access for an
explicit privileged role.
