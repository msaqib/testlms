---
name: save-session
description: Use when a scheduled prompt says "run the github issue engagement loop".
---

# Scheduled Issue Engagement Loop

Use this for each scheduled run of "run the github issue engagement loop". It builds on `github-issue-engagement`, which holds the detailed rules.

## Each run

1. Find the most recently updated open issue and read its last comment.
2. If nothing changed since our last comment, take no action.
3. If the reporter answered a clarifying question, react with THUMBS_UP and post the plan. Do not implement yet.
4. If the reporter approved the plan, implement, test, run a focused security review, report credible findings on the issue when public reporting is authorized, then create and push a branch and open a PR. Post the PR URL and wait for manual human approval; never merge it.
5. If a tracked PR was manually merged, verify the merge and post the final issue report. Otherwise, report that approval or merge is still pending.

## Notes

- Do not post duplicate comments on repeated runs.
- Never self-approve, merge, enable auto-merge, or bypass missing checks.
- Before reporting an implementation as delivered, follow the snapshot rules in `github-issue-engagement`.
