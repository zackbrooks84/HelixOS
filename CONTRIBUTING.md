# Contributing to HelixOS

HelixOS contributions should follow `HELIXOS_BLUEPRINT.md` exactly. The most important contribution type is a skill folder that can be discovered semantically without bloating agent context.

## Create a Skill
Start from the built-in scaffold generator:

```bash
helixos new-skill my_skill_name
```

This creates a new folder under `skills/my_skill_name/` with the standard structure so you can fill in the prompt, examples, tests, and metadata without inventing a new layout.

## Required Files
Every skill contribution must include these files before review:

- `system_prompt.md`
- `test_cases/`

Optional files are allowed when useful:

- `examples/`
- `tools.yaml`
- `metadata.yaml`

Keep each skill focused on one capability. Do not combine unrelated review, planning, and execution behaviors into a single skill.

## Validate Your Skill
After editing the scaffold, validate the directory before opening a pull request:

```bash
helixos validate ./skills/my_skill_name
```

If your local workflow or team documentation refers to validating a single skill folder explicitly, use the same command against that folder path, for example `./your-skill`.

## Open a Pull Request
Community skills should be submitted as a pull request to `agents/community/` with:

1. The full skill folder.
2. A short explanation of the skill's focused purpose.
3. Evidence that the validation command passed.
4. Any notes on when the skill should or should not trigger semantically.

Reviewers will check that the skill follows the blueprint folder format, stays narrow in scope, and does not duplicate an existing capability.
