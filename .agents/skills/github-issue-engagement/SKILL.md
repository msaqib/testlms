---
name: github-issue-engagement
description: Fetch, read, react to, and reply to GitHub repository issues and comments using the GitHub CLI.
---

# GitHub Issue Engagement

Use this skill when asked to retrieve issues, read an issue discussion, react to an issue body or comment, or post a reply.

When explicitly invoked without a more specific instruction, complete the full engagement workflow for the most recently updated open issue: fetch it, read its body and comments, add a thumbs-up reaction to the newest comment (or the issue body when there are no comments), and post a relevant reply.

## CRITICAL
In case of ANY ambiguity, please ask the user for clarification.

## Requirements

- Use `gh` for all GitHub operations.
- Identify the repository from the current git remote when the user does not specify one.
- Confirm authentication before write operations with `gh auth status`.
- Do not expose tokens or other credentials.
- An explicit invocation of this skill authorizes its default full engagement workflow, including its reaction and reply. For all other use, never post a reply, reaction, or other write action without an explicit user request.

## Fetch issues

List issues, including closed ones when the user asks for all issues:

```powershell
gh issue list --repo OWNER/REPO --state all --limit 100 --json number,title,state,author,createdAt,updatedAt,url,labels
```

For only open issues, use `--state open`.

## Default full engagement workflow

When the skill is invoked without a requested issue number or action:

1. List open issues ordered by most recently updated:

   ```powershell
   gh issue list --repo OWNER/REPO --state open --limit 1 --search "sort:updated-desc" --json number,title,updatedAt,url
   ```

2. Read that issue and every comment using the command in **Read an issue and comments**.
3. React with `THUMBS_UP` to the final item in `comments`, or to the issue body when there are no comments.
4. Reply to the newest comment. Answer a direct question accurately; for a request that needs current information, consult a reliable source before posting. If no substantive response is appropriate, acknowledge the comment briefly instead.
5. Report the issue, reaction target, and link to the newly created reply.

## Read an issue and comments

Retrieve the issue body and full discussion:

```powershell
gh issue view ISSUE_NUMBER --repo OWNER/REPO --json number,title,body,state,author,createdAt,updatedAt,url,comments
```

Present the issue body and comments faithfully. When acting on the latest comment, use the final item in `comments`; if there are no comments, act on the issue body.

## Add a reaction

Default to a thumbs-up reaction only if the user did not specify a reaction. Reactions require a node ID. Use the latest comment's `id`, or the issue's `id` when the issue has no comments.

```powershell
gh api graphql -f query='mutation($subjectId: ID!, $content: ReactionContent!) { addReaction(input: {subjectId: $subjectId, content: $content}) { reaction { content } } }' -f subjectId='NODE_ID' -f content='THUMBS_UP'
```

Use GraphQL reaction values such as `THUMBS_UP`, `THUMBS_DOWN`, `LAUGH`, `HOORAY`, `CONFUSED`, `HEART`, `ROCKET`, and `EYES`. Report permission failures plainly, including that the token needs repository **Issues: Read and write** permission.

## Reply to an issue

Read the latest comment before drafting a response. Reply as a new issue comment:

```powershell
gh issue comment ISSUE_NUMBER --repo OWNER/REPO --body "REPLY_TEXT"
```

For requests that require current external information, fetch a reliable source first and include the relevant value and time zone in the reply. Keep responses concise, accurate, and directly responsive to the latest comment.

## Application Change Completion

When handling a user-visible application change or feature request, use
`capturing-ui-evidence` before reporting completion. After the implementation,
tests, evidence commit, and push have succeeded:

1. Identify the most recently updated open issue using the command in
   **Default full engagement workflow**.
2. Build immutable links using the pushed commit SHA:
   - Commit: `https://github.com/OWNER/REPOSITORY/commit/SHA`
   - Screenshot:
     `https://raw.githubusercontent.com/OWNER/REPOSITORY/SHA/docs/evidence/CHANGE-SLUG/SCREENSHOT.png`
3. Post one issue comment in this exact structure:

   ```markdown
   ## Implementation report

   **Changes:** <concise summary>
   **Passed:** <each validation command and outcome, or `None`>
   **Failed:** <each failed validation command and outcome, or `None`>
   **Commit:** <immutable commit URL>

   **Snapshot:**
   ![<description>](<immutable raw screenshot URL>)
   ```

Do not post the report before the push succeeds. Report every failed test
plainly; never label the work complete when a required validation has failed.

## Completion

After a successful write operation, report the action taken and link to the created comment when applicable.
