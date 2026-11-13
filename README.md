# Only Forge Skills

Build agent skills that survive a hostile test field, then ship them with a GitHub-ready README.

`only-forge-skills` is the builder for the `only-forge-*` family. It decides whether a skill should exist, chooses the lightest mechanism that works, validates the result with planted problems and a blind executor, compares it against a no-skill baseline, and packages it for distribution.

## What it does

- Runs a necessity gate before anything is built: one-off task, existing coverage, token cost, scope, and the lightest-mechanism ladder.
- Writes or upgrades a `SKILL.md` with the minimum scripts and references.
- Runs static validation and a read-only conflict scan against installed skills.
- Runs a half-strict trial: adversarial fixture, blind executor, without-skill baseline, independent verifier, targeted re-verification.
- Records description/body/trial token costs and redundant artifacts.
- Produces a `.skill` package and a GitHub README with failure modes, costs, compatibility, and license notes.

It does not run a full benchmark suite, upload to GitHub, or replace a project's own review process.

## Quick start

- Install: copy this directory to `~/.config/opencode/skills/only-forge-skills/`, or install `only-forge-skills.skill`.
- Load: mention `@only-forge-skills`, or ask to create, upgrade, audit, or publish a skill.
- Example:
  > "I want a skill that turns a folder of lecture PDFs into a weekly study plan. Does it need to be a skill, or can we extend something we already have?"
- Output:
  > A decision record, the skill files, validation evidence, a cost report, a `.skill` package, and a README.

## Why use it

- Catches the most expensive mistake early: building a skill that should have been a sentence, a reference, or a script.
- Tests with planted problems instead of a clean demo, so boundary failures surface before users find them.
- Compares with-skill and without-skill runs, so "it works" has a baseline.
- Keeps the skill directory lean: one CLI, at most three references, no duplicated checklists.

## Costs and tradeoffs

- Description: about 130 tokens, always in context.
- Body: about 2,300 tokens, loaded when the skill triggers.
- Trial: default budgets are 60k tokens for light, 300k for half-strict, 500k for strict. The half-strict run includes the adversarial fixture, blind executor, baseline, verifier, and re-verification. Use the light tier for small internal skills.
- Runtime: Python 3.10+ and PyYAML (or the built-in fallback parser). No network access, no npm dependencies.
- Maintenance: update the OpenCode discovery and frontmatter rules when the host changes; re-run the trial when the validation protocol changes.

## When to use it

- Creating a new skill from a repeated workflow.
- Upgrading a skill that has grown too long, too vague, or too broad.
- Auditing an existing skill for broken links, overlapping triggers, or unsafe scan phases.
- Preparing a skill for GitHub or another public distribution.

## When not to use it

- A one-off task. Do it directly.
- A workflow that an existing skill already covers. Extend that skill.
- A simple preference or style rule. Put it in `AGENTS.md` or a skill reference, not a new skill.
- A full evaluation benchmark. This skill is deliberately lighter than an eval framework.

## Failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| The skill never triggers | Description describes the topic but not the user's situation | Add concrete trigger phrases and a "do not use for" boundary; rerun the positive/negative probes |
| The skill triggers for adjacent tasks | Description is too broad or has no negative boundary | Narrow the scope; name the competing skill; rerun the conflict scan |
| A validation step passes on a clean sample but fails in real use | No planted problems or boundary cases | Add at least three adversarial fixtures; rerun the blind executor and verifier |
| The skill writes or deletes during a read-only scan | The procedure mixes scan and execution | Split the phases; add "after triage, with permission, do X" and test it |
| The skill ends in "sent" or "later" | No terminal-state rule | Require done, handed off with a receipt, blocked, or N/A with a reason |
| The package contains local paths or personal names | No publish check | Run `validate --public`; replace paths with placeholders; rerun the checklist |
| The skill body keeps growing | Details live in `SKILL.md` instead of references | Move checklists and examples to `references/`; keep `SKILL.md` as the index |

## Compatibility

- Agents: OpenCode, Claude Code, Codex.
- Frontmatter: `name`, `description`, `license`, `compatibility`, `metadata`.
- Platform: the commands in the protocol are written for Windows PowerShell; the Python tool is cross-platform. Test every command on the target platform before publishing.

## Install

```powershell
# From a clone (Windows PowerShell)
Copy-Item -Recurse skills\only-forge-skills "$HOME\.config\opencode\skills\"

# macOS / Linux
# cp -r skills/only-forge-skills ~/.config/opencode/skills/

# Or install the package
# only-forge-skills.skill
```

## License and credits

MIT. The static-validation and packaging ideas are adapted from Anthropic's `skill-creator` (MIT); the validation protocol incorporates lessons from a separate internal audit project. This is an independent fork and is not endorsed by the original authors.

## Pre-release checklist

- [x] `python scripts/skill_tool.py validate <skill-dir> --public` passes.
- [x] `python scripts/skill_tool.py scan <skill-dir> --strict` is the release scan; the default scan is advisory and warns on invalid skills. Use `--ignore-invalid` for an unrelated broken skill and record why.
- [x] No local absolute paths, personal names, internal skill references, or emails.
- [x] License and credits are correct.
- [x] Windows commands were tested on Windows.
- [x] Failure modes are based on the failure inventory and trial.
- [x] Half-strict trial: with-skill + baseline; builder critique targeted re-verification PASS-WITH-NOTES. The independent verifier report is in the release evidence.
- [x] Cost numbers are measured or explicitly marked approximate.
- [x] `python scripts/skill_tool.py package <skill-dir> <dist-dir> --public` builds.
