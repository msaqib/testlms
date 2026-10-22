---
name: capturing-ui-evidence
description: Use when an implementation changes a user-visible application interface or behavior and the work will be committed.
---

# Capturing UI Evidence

For every user-visible application change, preserve a browser screenshot that demonstrates the implemented result. The evidence is part of the change, not a substitute for functional tests.

## Required Workflow

1. Start the application and exercise the changed behavior in a browser.
2. Capture a screenshot with Chrome DevTools after the result is visible.
3. Save it under `docs/evidence/<change-slug>/` with a descriptive ASCII filename such as `completed-counter.png`.
4. Commit the implementation, relevant tests, and evidence together.
5. Push the commit to its configured upstream. If the push fails, report the failure; do not claim the work is complete.

Use a fresh, focused screenshot: it must visibly demonstrate the changed state without unrelated browser windows or developer tools obscuring it. Keep existing evidence immutable; create a new change-specific directory rather than overwriting prior evidence.

## Exclusions

Do not capture evidence for changes with no user-visible application effect, such as internal refactors, build configuration, or documentation-only changes.

## Common Mistakes

| Mistake | Required behavior |
|---|---|
| Browser smoke test only | Save and commit the screenshot produced during validation. |
| “The change is trivial” | The requirement still applies to every user-visible change. |
| Screenshot outside the repository | Save it in `docs/evidence/<change-slug>/` before committing. |
| Commit without push | Push the commit and surface push failures. |
