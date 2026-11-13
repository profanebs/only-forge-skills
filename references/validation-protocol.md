# Validation Protocol (Half-Strict)

Read this before Step 3c of `SKILL.md`. The goal is to break the skill, not to prove it works.

## 0. Inputs and output locations

- Skill installed at `~/.config/opencode/skills/<id>/SKILL.md` or a project `.opencode/skills/<id>/SKILL.md`.
- Build workspace: `skill-builds/<skill>/<YYYY-MM-DD>/` (outside the skill directory).
- Subfolders: `fixture/`, `verifier/`, `trial-with/`, `trial-baseline/`, `critique/`, `evidence/`, `cost-report.md`, `comparison.md`.
- The scan and inventory phases are read-only. Do not write outside the build workspace.

## 1. Failure inventory

Before the fixture, list at least three failure modes from the design. Map each one to a test case in `failure-modes.md`. The inventory drives the fixture, the trial prompts, and the README's failure-modes table. Do not invent failure modes after the test.

## 2. Build the test field

Do not use a clean sample. Plant at least three real problems that are relevant to the skill. Generic examples:

- a promise stated but not done
- a false "12/12 tests passed"
- duplicate artifacts
- a stale README command
- a stale TO-DO marker
- a dirty git worktree
- a fake session ID
- a secret-looking log
- a missing target, a broken channel, or no receipt
- a half-finished state ("sent" without a receipt)

For a skill-building task, plant:

- a script with a syntax error
- a description that overlaps an existing skill
- a reference link to a missing file
- a half-finished state ("sent" without a receipt)

Write `verifier/planted-problems.md` with id, what, where, expected detection, and severity. Do not show this file to the executor.

## 3. Blind executor (with skill)

Dispatch a fresh subagent. Give it only:

- the skill ID and path
- the task
- input files
- output directory
- this instruction: "Do the task first. Save all artifacts. Then, in a separate section, critique the skill: bugs, ambiguities, contradictions, redundancy, missing steps, and boundary failures. Give severity (high/medium/low) and `file:line`. Do not assume the skill is correct."

Do not mention the planted problems. Record commands, errors, artifacts, and token/duration data if available.

## 4. Baseline (without skill)

Run the same task with the same inputs in a fresh subagent that does not load the skill. Save outputs to `trial-baseline/`. Record token/duration data. If the task cannot run without the skill, say so and mark the comparison INCONCLUSIVE.

## 5. Independent verifier

Dispatch the `verifier` agent in read-only mode. Give it:

- the skill directory
- the fixture directory
- `verifier/planted-problems.md`
- `trial-with/` and `trial-baseline/`
- the success criteria

Ask it to:

1. Check each planted problem: caught or not caught, with evidence.
2. Test boundaries: missing target, broken channel, no receipt, audit-only must not modify files, N/A ledger, lightweight exit.
3. Compare with-skill and baseline on quality, time, tokens, and failure modes.
4. Return PASS, FAIL, or INCONCLUSIVE per criterion, with `file:line` evidence.

The verifier must not edit files. If it cannot verify something, it returns INCONCLUSIVE and names what is missing.

## 6. Fix and targeted re-verification

Fix only what failed. Send the same critic or verifier the previous issue list and ask it to mark each item resolved, partial, or unresolved with `file:line`. Do not rerun the full suite unless the core instructions changed. If the core changed, rerun all scenarios.

## 7. Evidence before reset

Copy HANDOFF files, reports, packages, code, and trial outputs to `evidence/` before resetting or cleaning the test field. Otherwise the re-verification has no baseline.

## 7b. Permission point

The scan is read-only. After triage, the builder records "triage complete, may edit" in the build workspace. The verifier never edits. The executor may edit only inside its work directory. If the only fix requires a rename or an edit outside that boundary, return BLOCKED with the exact change instead of degrading the skill.

## 8. Cost ledger

Fill `cost-report.md`. Template:

```markdown
# Cost report

- Description: <chars> chars, about <tokens> tokens (always on)
- Body: <lines> lines, about <tokens> tokens (on trigger)
- References: <count> files, <bytes> bytes
- Trial: <count> runs; <tokens> tokens (measured or approximate); <duration>
- Artifacts: <count> files, <bytes>; duplicates: <none / list>
- Verdict: within budget / trimmed / asked the user
```

Fields:

- description tokens (always on), body tokens (loaded on trigger), reference bytes
- trial runs: count, tokens (usage delta or an explicit approximation), duration
- artifacts: count, total size, duplicated content
- verdict: within budget, trim, or ask the user

Default trial budgets: light 60k tokens, half-strict 300k, strict 500k. If the harness does not expose a usage delta, estimate from the transcripts and mark it approximate. Body over 8k tokens, description over 150 tokens, or a trial over budget means trim or ask before continuing.

## 9. Platform and safety checks

- Run every command on the target platform. On Windows, `grep -rn` is unavailable and `Select-String -Path .\**\*.py` does not recurse. Use `Get-ChildItem -Recurse -File -Include ... | Where-Object ... | Select-String`, excluding `.git` and `node_modules`.
- The scan phase must be read-only. A trial fails if the skill moves, deletes, or sends anything during the scan.
- Apply the terminal-state rule from `SKILL.md`: done, handed off (target exists plus receipt), blocked, or N/A with a reason. "Later" or "sent" without a receipt is not a terminal state.
- Allow N/A; forbid padding, per `SKILL.md`.

## 10. Pass criteria

- Static: no FAIL; every WARN is explained or fixed.
- Conflict: no collision; every similarity is resolved or recorded as a false positive.
- Trial: all criteria PASS; the with-skill/baseline comparison is included.
- Cost: within the agreed budget.
- Publish: desensitized, license and credits correct, `validate --public` passes.
- Package: `.skill` builds and contains the expected files.

## Appendix: validator codes

| Code | Level | Meaning |
|---|---|---|
| `frontmatter` | FAIL | Missing or invalid YAML |
| `name.missing` / `name.format` / `name.length` / `name.directory` | FAIL | Name missing, not kebab-case, too long, or not equal to the directory |
| `description.missing` / `description.length` / `description.angle` | FAIL | Description missing, over 1024 chars, or contains angle brackets |
| `description.short` / `description.trigger` / `description.negative` / `description.tokens` | WARN | Description is weak or too long; add trigger and boundary cues |
| `body.empty` / `body.lines` | FAIL | Body empty or over 500 lines |
| `body.lines_warn` / `body.tokens` | WARN | Body over 300 lines or 8k tokens |
| `link.broken` / `path.broken` | FAIL | Local markdown link or backticked path does not resolve |
| `script.syntax` / `script.empty` / `script.read` | FAIL | Python script does not parse, is empty, or cannot be read |
| `code.non_ascii` | WARN | Code or config file contains non-ASCII bytes |
| `file.public_readme` | FAIL | Public skill has no README.md |
| `file.readme_internal` / `file.extra_doc` / `file.cache` / `file.modules` / `file.git` | WARN | Extraneous files or build artifacts |
| `file.env` / `file.secrets` | FAIL | Forbidden secret paths |
| `content.duplicate` / `content.duplicate_ref` | WARN | Repeated line within SKILL.md or between SKILL.md and a reference |
| `content.placeholder` | WARN | A dev placeholder marker or `[place-holder]` |
| `secret.private_key` / `secret.token` | FAIL | Private key or token-like string |
| `secret.assignment` | WARN | Possible credential assignment |
| `path.windows` / `path.profile` / `path.macos` / `pii.email` / `pii.custom` | FAIL in `--public`, WARN otherwise | Local path, email, or custom site-specific identifier |
| `frontmatter.fallback` | WARN | PyYAML is absent; the fallback parser may behave differently |
| `compatibility.format` | WARN | Compatibility should be a short string |
| `budget.scripts` / `budget.references` | WARN | More than three scripts or references |
| `license.missing` | WARN | No license field |
