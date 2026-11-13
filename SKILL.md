---
name: only-forge-skills
description: Build, validate, and publish agent skills. Use when creating a new skill, upgrading an existing skill, auditing a skill for bugs or conflicts with installed skills, or preparing a skill for GitHub distribution. Covers scavenging prior art, deciding whether a skill is needed, the lightest-mechanism ladder, OpenCode/Claude/Codex skill format, static validation, conflict scanning, adversarial trial runs with blind executors, token and artifact cost accounting, and a GitHub-ready README. Do not use for one-off tasks or when an existing skill already covers the workflow; extend that skill instead.
license: MIT
compatibility: opencode,claude-code,codex
metadata:
  family: only-forge
  version: 2.0.0
---

# Only Forge Skills

A skill is not done when it reads well. It is done when a blind executor fails to break it.

This is the builder for the `only-forge-*` family. Use it to decide whether a skill should exist, build the lightest version that works, validate it against a hostile test field, and ship it with a GitHub-ready README.

## The loop

1. **Decide** - should this be a skill at all? What is the lightest mechanism?
2. **Write** - SKILL.md plus the minimum resources; list failure modes first.
3. **Validate** - static checks, conflict scan, adversarial trial, baseline comparison.
4. **Ship** - cost report, package, README, desensitize.

Do not skip a gate because the skill "looks simple". Do use the light tier when the skill is genuinely small, and say so in the cost report.

### Validation tiers

| Tier | Work | Use for |
|---|---|---|
| Light | static + conflict + one execution run | small internal skills and small edits |
| Half-strict (default) | static + conflict + planted field + blind executor + baseline + verifier + targeted re-verify | normal skill builds |
| Strict | half-strict + human review | public or high-risk skills |

### Releasing an existing skill

If the user asks to prepare an existing skill for release, and the instructions did not change, skip the necessity gate and the adversarial trial. Run 3a, 3b, 3e, and 4; say "release audit" in the report. If the instructions did change, run the full half-strict tier.

## Step 1: Decide

### 1a. Necessity gate

Do not create a skill if any answer is yes:

- Is this a one-off task? Do it directly; write a note only if it will recur.
- Does an existing skill already cover at least 70%? Extend it or add a reference.
- Is the value lower than the always-on description cost? Use a command or a reference instead.
- Is it several unrelated workflows? Split it or do not build it.
- Is the lightest mechanism enough? See 1b.

If the user explicitly asks for a new skill, record the override and the reason. "The user asked" is a valid reason; "it would be nice" is not.

### 1b. Lightest-mechanism ladder

Choose the lowest rung that achieves the first-principles goal:

1. One sentence in an existing skill.
2. A new reference file in an existing skill.
3. A script in an existing skill.
4. A new skill.
5. A plugin or framework.

Jumping a rung requires a one-line reason. A new skill is justified only when the workflow is repeated, coherent, and not covered elsewhere.

### 1c. Scavenge before building

Search local skills, setup notes, MCPs, and memory first; then GitHub, npm, PyPI, and awesome lists. If a scavenging or reuse-check skill is available, use it. If not, use this checklist:

- What existing skill is closest? Why not extend it?
- What external tool does this? Can it be used or adapted?
- What is the license? Is the dependency acceptable?
- What would break if we built nothing?

Record the search terms, what you found, and why you chose reuse, adapt, or build. "I think there is nothing" is not a search.

### 1d. Failure modes first

Before writing, list at least three ways the skill can fail:

- wrong trigger or missed trigger
- skipped step or wrong order
- unsafe action (writes, deletes, or sends during a read-only phase)
- boundary crash (missing target, broken channel, no receipt, empty input)
- half-finished state ("later", "sent" without a receipt)

Each failure mode must map to a test case and to the README's failure-modes section. Do not invent failure modes after the test; the inventory drives the test field.

## Step 2: Write

### Anatomy

```
skill-name/
  SKILL.md          required: frontmatter + instructions
  scripts/          optional: deterministic checks or actions
  references/       optional: details loaded on demand
  assets/           optional: output templates or fixtures
  README.md         public skills only; never loaded by OpenCode
```

Do not add README, CHANGELOG, or INSTALLATION_GUIDE to internal skills. For public skills, `README.md` at the skill root is allowed and expected.

### Complexity budget

- SKILL.md: target 300 lines or fewer, hard cap 500.
- description: target 150 tokens or fewer, hard cap 1024 characters.
- scripts: at most 3. If they share parsing, use one CLI with subcommands.
- references: at most 3. No duplicated content between SKILL.md and references.
- no dependency that is not already installed and necessary.
- every file must answer: what behavior does it change, or what failure does it prevent? If not, delete it.

### OpenCode rules

- Discovery: `~/.config/opencode/skills/<id>/SKILL.md`, project `.opencode/skills`, plus `~/.claude/skills` and `~/.agents/skills`.
- The ID is the directory name. The frontmatter `name` must equal the directory name; the validator hard-fails on a mismatch. A build workspace with a fixed folder name is not a reason to degrade the id; rename the folder or return BLOCKED.
- Required: `name`, `description`. Optional: `license`, `compatibility`, `metadata` (string map), `allowed-tools`.
- The description is the trigger. Put both what the skill does and when it should load there, not in the body.
- `metadata.opencode/autoinvoke: false` hides the skill from the model list but keeps it loadable by ID.
- Only `SKILL.md` is loaded into context. Supporting files are read on demand.
- Check the target agent's skill permissions before assuming it can load the skill.

### Writing rules

- Use the imperative form. Explain why, not only MUST.
- Put the procedure in SKILL.md; put long checklists, examples, and templates in references.
- Every branch must end in a terminal state: done, handed off (target exists plus receipt), blocked, or N/A with a reason. No "later" or "sent" without a receipt.
- Allow N/A; forbid padding. "Applicable but empty" means "none".
- A read-only phase must not write. Say "after triage, with permission, do X".
- If the only fix requires a rename or an edit outside the permitted scope, stop and return BLOCKED with the exact change. Do not degrade the skill to fit the workspace.
- Test every command on the target platform. On Windows, `grep -rn` is unavailable and `Select-String -Path .\**\*.py` does not recurse. Use `Get-ChildItem -Recurse -File -Include ... | Where-Object ... | Select-String`, excluding `.git` and `node_modules`.
- No secrets, internal absolute paths, or personal names in a public skill.

## Step 3: Validate

Run the gates in order. Do not skip a failed gate by rewriting the test.

### 3a. Static validation

```bash
python scripts/skill_tool.py validate <skill-dir> [--public] [--strict]
```

Fix every FAIL and read every WARN. Re-run until clean.

### 3b. Conflict scan

```bash
python scripts/skill_tool.py scan <skill-dir>
```

Hard fail on an ID or directory collision. For each similarity at or above 0.35, read the other skill and decide: merge, narrow the description, or record why it is a false positive. The scan is read-only. It checks all OpenCode discovery roots by default (user, project, Claude, and agents). The score is lexical: a paraphrase can pass. If the topic is adjacent, read the other skill even below the threshold. The default scan is advisory; for a release scan use `--strict`, which exits 1 on warnings, including invalid skills. If an unrelated invalid skill blocks the scan, fix it or pass `--ignore-invalid` and record why.

### 3c. Adversarial trial

Read `references/validation-protocol.md` before running this gate. The short version:

1. Build a test field with at least three planted problems. Keep the planted-problems manifest away from the executor.
2. Blind executor: give it the task and the skill only. It does the real work with the skill, saves artifacts, then separately critiques the skill with severity and file:line.
3. Baseline: run the same task without the skill and save the outputs.
4. Independent verifier: use the `verifier` agent (configured read-only); it checks the planted problems, boundary cases, and both outputs. It returns PASS, FAIL, or INCONCLUSIVE.
5. Fix, then run a targeted re-verification with the same critic. Do not rerun the full suite unless the core instructions changed.
6. Copy evidence before resetting the test field.

### 3d. Cost and redundancy

Record the description tokens (always on), body tokens (loaded on trigger), reference bytes, trial tokens (usage delta or an explicit approximation), artifact count and size, and duplicated content. Use the cost-report template in `references/validation-protocol.md`. If the body exceeds 8k tokens, the description exceeds 150 tokens, or the trial exceeds the agreed budget, trim or ask the user before continuing.

### 3e. Publish checks

Desensitize local paths, personal names, internal skill references, and emails. Use `--pii-patterns <file>` for site-specific names; keep that file outside the public skill. If the skill is adapted from MIT code, keep the original copyright, add your modifications, and state the fork in README or NOTICE; do not imply endorsement. Run `validate --public`.

## Step 4: Ship

```bash
python scripts/skill_tool.py package <skill-dir> <dist-dir> [--public] [--pii-patterns <file>]
```

`package` runs the conflict scan by default and blocks on a collision. Use `--skip-scan` only with a recorded reason. Write `README.md` from `references/github-report-template.md` at the skill root for public skills. It must state what the skill does, how to use it, benefits, costs, when to use it and when not, failure modes and fixes, compatibility, install, and license or credits. Keep it under about 150 lines.

Deliver absolute paths: skill directory, README, cost report, trial evidence, and `.skill` package. On Feishu or mobile, send the files, not only paths.

## Anti-patterns

- Creating a skill when a sentence, reference, or script would do.
- A clean demo that only proves the happy path.
- Testing with the author, who fills gaps from memory.
- Putting the same checklist in SKILL.md and references.
- A scan phase that can delete, move, or send.
- "Sent" or "later" without a receipt, owner, or next step.
- Shipping with local paths, personal names, or an unlicensed fork.
- Adding a dependency to avoid writing twenty lines.

## References

- `references/validation-protocol.md` - read before Step 3c.
- `references/github-report-template.md` - read before Step 4 for public skills.

## Scripts

- `scripts/skill_tool.py validate|scan|package` - static checks, conflict scan, and packaging.
