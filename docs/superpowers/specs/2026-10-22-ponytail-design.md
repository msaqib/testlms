# Ponytail repository-local skill installation

## Goal

Install the complete Ponytail skill set in this repository so GitHub Copilot
CLI discovers the skills from the existing project-local `.agents\skills`
directory. The installation must not alter the user's global Copilot plugin
configuration.

## Scope

The repository will contain the six skills supplied by
`DietrichGebert/ponytail`:

- `ponytail`
- `ponytail-review`
- `ponytail-audit`
- `ponytail-debt`
- `ponytail-gain`
- `ponytail-help`

The files will be installed using Ponytail's supported `skills` CLI in
project-local mode and placed alongside the existing project skills.

## Non-goals

- Do not install the Copilot CLI plugin or its lifecycle hooks.
- Do not add a project package manifest or application dependency.
- Do not modify existing skills or global user configuration.

## Installation and validation

Run the supported installer for all Ponytail skills, targeting the Copilot
project-skill location. Confirm that each expected skill directory has a
`SKILL.md` file and inspect the Git diff to verify only the new Ponytail files
and directly related installer metadata, if any, were created.

## Failure handling

If the installer does not support the repository's `.agents\skills` layout,
stop without relocating existing skills. Report its output and use a source
checkout only after a separate design decision.
