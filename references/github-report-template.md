# GitHub README Template

Use this for public skills. Keep the result under about 150 lines. Put `README.md` at the skill root. OpenCode loads only `SKILL.md`, so the README does not enter the model context; it exists for humans on GitHub.

## Template

```markdown
# <Skill Name>

<One sentence: what changes for the user.>

## What it does

<2-4 sentences. Name the workflow, the output, and the boundary. State what it does not do.>

## Quick start

- Install: copy the skill directory to `~/.config/opencode/skills/`, or install `<name>.skill`.
- Load: mention `@<id>`, or ask a task that matches the description.
- Example:
  > <A realistic user request.>
- Output:
  > <What the user gets, where it is saved, and how to verify it.>

## Why use it

- <Concrete benefit, not a slogan.>
- <Concrete benefit, with a number if you have one.>

## Costs and tradeoffs

- Description: ~<N> tokens, always in context.
- Body: ~<N> tokens, loaded when the skill triggers.
- Runtime: <scripts, dependencies, platform requirements.>
- Maintenance: <what must be updated when an upstream API or path changes.>

## When to use it

- <Situation 1.>
- <Situation 2.>

## When not to use it

- <Near-miss 1; name the better tool or skill.>
- <Near-miss 2.>

## Failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| <What the user sees> | <Why it happens> | <What to change> |
| <What the user sees> | <Why it happens> | <What to change> |
| <What the user sees> | <Why it happens> | <What to change> |

Use at least three rows. They must come from the failure inventory and the trial, not from imagination.

## Compatibility

- Agents: OpenCode, Claude Code, Codex.
- Frontmatter: `name`, `description`, `license`, `compatibility`, `metadata`.
- Platform: <Windows/macOS/Linux notes; list any command that was only tested on one platform.>

## Install

```powershell
# From a clone (Windows PowerShell)
Copy-Item -Recurse skills\<name> "$HOME\.config\opencode\skills\"

# macOS / Linux
# cp -r skills/<name> ~/.config/opencode/skills/

# Or install the package
# <name>.skill
```

## License and credits

- License: <MIT / Apache-2.0 / ...>.
- If adapted: "Based on <project> (<license>). Original copyright <holder>; modifications copyright <holder>. This is a fork and is not endorsed by the original author."
- If no adaptation: "Copyright <year> <holder>."

## Pre-release checklist

- [ ] `python scripts/skill_tool.py validate <skill-dir> --public` passes.
- [ ] `python scripts/skill_tool.py scan <skill-dir>` reports no collisions.
- [ ] No local absolute paths, personal names, internal skill references, or emails.
- [ ] License and credits are correct; MIT derivatives keep the original notice.
- [ ] Every command was tested on the target platform (Windows commands tested on Windows).
- [ ] Failure modes are real and reproducible.
- [ ] Cost numbers are measured, not guessed.
- [ ] `python scripts/skill_tool.py package <skill-dir> <dist-dir> --public` builds.
```

## Notes

- A README is not a second SKILL.md. Keep the procedure in `SKILL.md`; use the README for humans.
- Do not duplicate the full reference tables in the README. Link to the skill files.
- If the skill is internal, do not create a README. The build output is enough.
