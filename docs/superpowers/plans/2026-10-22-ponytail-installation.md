# Ponytail Repository-Local Skill Installation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install all six Ponytail skills as copied, repository-local GitHub Copilot skills.

**Architecture:** Ponytail is not an application dependency. Its supported skills CLI fetches the six upstream skills and copies them to the repository's Copilot skill location, alongside the existing `.agents\skills` content. A PowerShell assertion confirms each expected `SKILL.md` exists before the installation is committed.

**Tech Stack:** GitHub Copilot CLI, Node.js, npx, skills CLI, PowerShell, Git.

**Spec:** `docs/superpowers/specs/2026-10-22-ponytail-design.md`

## Global Constraints

- Install all six Ponytail skills: `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, and `ponytail-help`.
- Use the Ponytail-supported skills CLI in project-local mode.
- Copy skill files; do not create symlinks.
- Do not install the Copilot CLI plugin, lifecycle hooks, package manifests, or global configuration.
- Do not modify existing project skills.

---

### Task 1: Install and verify Ponytail skills

**Files:**
- Create: `.agents/skills/ponytail/SKILL.md`
- Create: `.agents/skills/ponytail-review/SKILL.md`
- Create: `.agents/skills/ponytail-audit/SKILL.md`
- Create: `.agents/skills/ponytail-debt/SKILL.md`
- Create: `.agents/skills/ponytail-gain/SKILL.md`
- Create: `.agents/skills/ponytail-help/SKILL.md`
- Create: `skills-lock.json` if the skills CLI writes its project lockfile
- Modify: No existing project files
- Test: PowerShell presence assertion for the six required `SKILL.md` files

**Interfaces:**
- Consumes: `DietrichGebert/ponytail`, the upstream Ponytail skills package.
- Produces: Six repository-local Ponytail skill directories discoverable by GitHub Copilot CLI.

- [ ] **Step 1: Confirm the upstream package exposes the requested skills**

Run:

```powershell
npx --yes skills add DietrichGebert/ponytail --list
```

Expected: the output lists `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, and `ponytail-help`.

- [ ] **Step 2: Install all Ponytail skills into the Copilot project skill location**

Run:

```powershell
npx --yes skills add DietrichGebert/ponytail --skill '*' --agent github-copilot --copy --yes
```

Expected: all six skills are copied into the repository-local GitHub Copilot skills location. If the CLI selects a different destination than `.agents/skills`, stop; do not relocate the existing skill layout without a revised design.

- [ ] **Step 3: Verify every requested skill has its required entry file**

Run:

```powershell
$skills = 'ponytail', 'ponytail-review', 'ponytail-audit', 'ponytail-debt', 'ponytail-gain', 'ponytail-help'
$missing = $skills | Where-Object { -not (Test-Path ".agents\skills\$_\SKILL.md") }
if ($missing) {
  throw "Missing Ponytail skill entry files: $($missing -join ', ')"
}
```

Expected: the command exits successfully without output.

- [ ] **Step 4: Inspect the installation diff and whitespace**

Run:

```powershell
git --no-pager diff --check
git status --short
```

Expected: no whitespace errors; only Ponytail skill files and directly related installer metadata are uncommitted.

- [ ] **Step 5: Commit the installation**

Run:

```powershell
git add -- .agents/skills/ponytail .agents/skills/ponytail-review .agents/skills/ponytail-audit .agents/skills/ponytail-debt .agents/skills/ponytail-gain .agents/skills/ponytail-help
if (Test-Path skills-lock.json) { git add -- skills-lock.json }
git commit -m "chore: add Ponytail skills" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: the repository contains a commit that adds Ponytail's complete project-local skill set.
