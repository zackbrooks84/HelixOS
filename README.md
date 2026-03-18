# HelixOS
The local agent OS where every agent instantly understands you, self-corrects in real time, and never hallucinates a handoff.

## What Makes HelixOS Different
HelixOS is designed around Semantic Skill Discovery and the Observer loop: each agent can retrieve the most relevant skill folders for the current sub-task using local embeddings and overlap protection, while the Observer runs in parallel before commits or handoffs to issue a structured `pass`, `warn`, or `halt` verdict. Together, those two loops let agents stay narrowly grounded in the right instructions, self-correct before damage is done, and keep the user in control when a risky workflow needs approval.

## Skills Folder Format
This section is copied from Section 0 of `HELIXOS_BLUEPRINT.md` verbatim because it is the single most important contract in the repository.

```text
0. Skills Folder Format — The Headline Feature
This is the most important part of the entire repo. Every agent folder contains a skills/ subfolder. Each skill is a self-contained directory with this exact structure, enforced by the validation script.
Required Folder Structure
skills/
├── security_review/                  # folder name = skill ID
│   ├── system_prompt.md              # REQUIRED
│   │   # Example: "You are now in security-review mode.
│   │   # Focus on OWASP Top 10, supply-chain risks,
│   │   # and static analysis. No code changes without CVE ref."
│   ├── examples/                     # OPTIONAL
│   │   ├── example_1.json            # Structured I/O for Instructor
│   │   └── example_2.md              # Free-form conversation example
│   ├── tools.yaml                    # OPTIONAL: extra MCP tools
│   ├── test_cases/                   # REQUIRED for core skills
│   │   └── basic_test.yaml
│   └── metadata.yaml                 # OPTIONAL: priority: 0.8
How SemanticSkillDiscovery Uses It
Embed the current sub-task context with nomic-embed-text
Retrieve top-3 candidates from Chroma
Apply min_distance=0.25 + diversity_penalty=0.15 (configurable in ~/.helixos/config.yaml)
Inject only the top-2 that pass the filter — prevents overlap noise (e.g. security review AND code review both firing)

Contributor Rules (CONTRIBUTING.md)
One skill = one focused capability
Must include system_prompt.md + test_cases/
Run: helixos validate skill ./skills/my-skill before PR
Skills are loaded only when needed — no context bloat
```

In practice, that means every skill should be small, sharply scoped, and testable. Keep the `system_prompt.md` narrowly focused on one capability, add enough `test_cases/` coverage to prove the trigger and expected behavior, and use `examples/` only when they improve retrieval or downstream structured output quality. The validator should be run before every PR so the repository stays consistent as the community skill library grows.

## Install
Install HelixOS from PyPI:

```bash
pip install helixos
```

Install Ollama from `ollama.ai`, then pull the required models:

```bash
ollama pull qwen2.5:7b
ollama pull deepseek-coder:14b
ollama pull nomic-embed-text
```

Then initialize HelixOS locally:

```bash
helixos init
```

**SANDBOX WARNING:** RestrictedPython is the default sandbox. It prevents accidental bad code but does **not** protect against network access, file system access, or adversarial inputs. If your agents touch real files or real APIs, use the sandbox-enabled init flow:

```bash
helixos init --with-sandbox
```

After `helixos init`, make sure the Chroma collection path is printed and marked writable. If that confirmation is missing, skill embeddings did not index correctly and Semantic Skill Discovery will not work until initialization succeeds.

## Run Your First Recipe
Use the built-in repo auditor first, then launch the UI:

```bash
helixos run repo_auditor
helixos ui
```

The recipe runner gives you a minimal local entry point for validating agent orchestration, while the UI exposes observer verdicts and approval controls in a simpler interactive workflow.

## Creating a New Skill
Create a new skill scaffold, edit the prompt, and validate the folder before you share it:

```bash
helixos new-skill my_skill_name
```

Then edit:

```text
skills/my_skill_name/system_prompt.md
```

Then validate the skill folder:

```bash
helixos validate ./skills/my_skill_name
```

A strong skill prompt should define exactly what mode the agent is entering, what checks or actions it performs, what outputs it is allowed to produce, and any hard constraints that keep it from overlapping with adjacent skills.

## How the Observer Works
The Observer always returns a structured `CriticVerdict` with one of three states:

- **pass**: the workflow continues silently because the critic found no blocking issue. Example: a code review recipe completes, all required artifacts are present, and the handoff payload validates correctly.
- **warn**: the workflow continues, but the issue is logged and surfaced in the audit trail. Example: an agent proposes a reasonable fix but forgets to attach one of the optional artifacts, so the system records the warning without interrupting progress.
- **halt**: the workflow pauses immediately because the critic found a serious issue. Example: a recipe tries to produce an invalid handoff target, or a generated code change looks unsafe relative to the active skill checklist.

In the UI, a `HALT` updates the observer verdict panel and exposes **Approve** and **Reject** buttons. **Approve** resumes the workflow from the halted state, while **Reject** rolls the session back to the last checkpoint so the user can redirect or retry the task with corrected instructions.

## Architecture
The architecture below is copied from Section 2 of the blueprint.

```text
User (CLI + Gradio with Polling Canvas)
     ↓
ResourceMonitor (queue + Ollama auto prefix cache)
     ↓
Orchestrator (LangGraph + Instructor structured outputs)
     ├── Agent Loader (YAML + Semantic Skill Discovery — headline)
     ├── MCP Client (dynamic tool discovery)
     ├── Intelligent Router (role → best local model)
     ├── Memory (Chroma + semantic vectors)
     ├── Tool Registry (MCP-first)
     └── Parallel Sandbox Executor (deferred trust — opt-in Docker)
          ↓
Observer/Critic Loop (parallel, pre-commit → CriticVerdict)
     ↓
Handoff Engine (Instructor schemas only)
     ↓
Polling Canvas + Checkpoints + Audit Log
```

This flow keeps orchestration local-first and structured from end to end: routing picks the right model for the role, semantic retrieval injects only the highest-signal skills, critics validate risky steps before they land, and handoffs are schema-enforced so agent transitions stay explicit.

## Contributing a Skill
To contribute a skill, create a skill folder under the appropriate agent skill tree and include the required files at minimum:

- `system_prompt.md`
- `test_cases/` with at least one concrete validation case

Optional files such as `examples/`, `tools.yaml`, and `metadata.yaml` should only be included when they materially improve the skill. Before opening a PR, run the validator on the skill directory, confirm the folder matches the blueprint structure, and make sure the skill stays tightly focused on a single capability. Community-ready skills should then be proposed through a pull request against the shared skills area, with a short summary of the use case, retrieval intent, and evidence that the validator passed.

## Roadmap
### Phase 1 (current)
- Semantic Skill Discovery with overlap protection using `min_distance` and `diversity_penalty`
- Observer/Critic loop with `CriticVerdict` and pass/warn/halt behavior
- Instructor-enforced structured outputs for verdicts and handoffs
- Intelligent Router, ResourceMonitor, and Chroma integration
- Five core agents, three community examples, CLI, basic Gradio, and observer demo recipes

### Phase 2
- Polling Canvas with file watching and periodic Gradio refresh
- Opt-in Docker sandbox support
- Full validation CI
- Time-travel debugger
- Rich toast notifications for warn verdicts
- Launch-ready docs and demo video

After Phase 2, the blueprint targets a v1.1 follow-up with a full live-sync canvas and an optional vLLM backend.
