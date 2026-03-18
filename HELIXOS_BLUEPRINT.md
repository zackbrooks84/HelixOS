HelixOS
Final Blueprint  —  March 2026
The Semantic Local-First Agent Operating System
Observer-Complete  ·  Fully Self-Contained  ·  100% Code-Ready Today
Project Name	HelixOS
Repo	helixos/helixos
PyPI Package	helixos  (available — confirmed free, March 2026)
License	MIT
Tagline	The local agent OS where every agent instantly understands you, self-corrects in real time, and never hallucinates a handoff.


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


0.1 Critic-Only Skills + Verdict Handling
Critic skills use the exact same folder structure as regular skills but are observer-only.
system_prompt.md defines a specific failure mode + checklist
test_cases/ contains checklist items (no action examples)
No tools.yaml — critics observe only, never act or call tools

Observer Verdict States
The Observer always returns a structured CriticVerdict, enforced by Instructor. Three states:

PASS	Workflow continues silently. No UI interruption.
WARN	Logged to audit trail. Surfaced as console log + Gradio text update (Phase 1). Workflow continues. Rich toast in Phase 2.
HALT	Workflow pauses immediately (LangGraph human-in-loop). User sees recommendation and must click Approve (resume) or Reject (rollback to last checkpoint).

Launch video hook: Semantic Skill Discovery pulled the exact skill → Observer halted on a bug → user approved the fix → continued.

1. Vision & Differentiators
HEADLINE: HEADLINE: Semantic Skill Discovery (with overlap protection)
Observer/Critic loop (parallel, pre-commit, defined verdict UX)
Instructor-enforced structured outputs everywhere
5 polished core agents + 3 community examples at launch

2. High-Level Architecture
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

3. Tech Stack (Fully Split & Honest)
LangGraph
Used deliberately for native checkpoints (time-travel debugger), streaming, and conditional handoffs. Minimal subset imported. 2-page 'Why LangGraph' doc covers it. LangGraph's SQLite checkpoint store owns ALL session state and replay.
Memory (ChromaDB)
Local vector store for semantic vectors only. Stores:
All skill embeddings (for instant SemanticSkillDiscovery retrieval)
Project context (codebase summaries and artifacts) — generated on first project load, updated incrementally after each major session
Queried exclusively by SemanticSkillDiscovery. Zero-config, <100 MB footprint.
Intelligent Router
Fixed defaults. Embedding model is separate (SemanticSkillDiscovery only). Suggested defaults table is community-editable with 'last verified' date.
# ~/.helixos/models/config.yaml
roles:
  coding:   deepseek-coder:14b
  security: qwen2.5-coder:7b
  creative: gemma2:9b
  research: qwen2.5:7b         # generation model, not embedding
Sandbox
Default = RestrictedPython (instant, zero install).
WARNING: RestrictedPython is a development sandbox, not a security guarantee. It prevents accidental bad code, not adversarial code. Enable Docker (opt-in) for full isolation.
Structured Outputs — CriticVerdict (helixos/pydantic_models/critic.py)
from pydantic import BaseModel
from typing import Literal

class CriticVerdict(BaseModel):
    status: Literal['pass', 'warn', 'halt']
    failure_mode: str | None = None
    recommendation: str | None = None
Structured Outputs — HandoffPayload (helixos/pydantic_models/handoff.py)
Every agent-to-agent handoff is enforced through this model. This is what makes hallucinated handoffs impossible.
from pydantic import BaseModel
from typing import Any

class HandoffPayload(BaseModel):
    target_agent: str
    task_summary: str
    context: dict[str, Any]
    artifacts: list[str] = []
    priority: int = 1
Both models run through the same StructuredOutputEnforcer. Zero broken JSON, ever.

4. Agent Definition Schema (v10.0)
Agents are defined as Markdown files with YAML frontmatter. This schema drives the loader, validator, and orchestrator.
---
name: Code Reviewer
description: Expert code reviewer focused on correctness, security, maintainability
version: 1.0
tools: ["mcp:git", "mcp:lint"]
handoffs: ["Frontend Developer"]
skills:
  - semantic_trigger: true
    folder: skills/security_review/
structured_output_schema: "pydantic_models.HandoffPayload"
---

## Identity & Memory
You are an experienced senior software engineer.

## Core Mission
Review code changes for bugs, security issues, and maintainability.

## Workflow Process
1. Analyze the diff
2. Identify issues
3. Suggest improvements with code snippets

## Success Metrics
- All critical issues caught
- Clear, actionable feedback provided
The frontmatter is parsed into a dataclass. The skills field drives SemanticSkillDiscovery. The structured_output_schema field binds the agent to HandoffPayload enforcement via Instructor.

5. Core Components (Phase 1 Order — Locked)
Component	Timeline
A. SemanticSkillDiscovery (helixos/agents/semantic_loader.py)	Day 1
B. Observer/Critic (helixos/agents/observer.py)	Day 1–2
C. StructuredOutputEnforcer (helixos/orchestrator/structured.py)	Day 2–3
D. ResourceMonitor + Intelligent Router + Chroma integration	Day 3–4
E. Polling Canvas (helixos/ui/canvas.py)	Phase 2


6. Two-Phase Roadmap
Phase 1 — Days 1–5 (Ship This First — Already Star-Worthy)
Semantic Skill Discovery + overlap protection (min_distance + diversity penalty)
Observer/Critic loop (with CriticVerdict + pass/warn/halt UX)
Instructor structured outputs (CriticVerdict + HandoffPayload)
Intelligent Router + ResourceMonitor + Chroma integration
5 core agents + 3 community examples
CLI + basic Gradio + 3 recipes with Observer demo

Phase 2 — Days 6–10 (Launch Version)
Polling Canvas (file-watching + Gradio refresh every 2s)
Opt-in Docker sandbox support
Full validation CI
Time-travel debugger
Rich toast notifications for warn verdicts
Launch-ready docs + demo video

v1.1 (after Phase 2 launches): Full live-sync canvas + optional vLLM backend.

7. One-Command Install
pip install helixos
helixos init                  # RestrictedPython default, instant success
helixos init --with-sandbox   # adds Docker isolation

Important for Instructor + Ollama: Ensure Ollama is running with OLLAMA_HOST accessible (default: localhost:11434) and the required model pulled (ollama pull qwen2.5:7b etc.) before running any recipe. This prevents the most common first-run connection error.

Sandbox warning: RestrictedPython stops your agents from running obviously dangerous code. It does not sandbox network access, file system access outside the working directory, or adversarial inputs. If your agents touch real files, real APIs, or user-provided code, enable Docker: helixos init --with-sandbox

ChromaDB: After helixos init completes, it prints the Chroma collection path and confirms it is writable. If that confirmation is missing, your skill embeddings did not index and SemanticSkillDiscovery will not work. Re-run helixos init.

8. Launch Strategy
Video Hook
Weird prompt → Semantic Skill Discovery pulled the exact skill I never named → Observer halted on a bug → user approved the fix → continued. All local, zero hallucinations.
X Post
HelixOS — the local agent OS that actually understands what you mean. Semantic Skill Discovery + built-in Observer = agents that don’t drift. One-click recipes. Video + repo dropping now. #LocalAI #AgentOS

This document is 100% self-contained. Every section stands alone.
Go write semantic_loader.py. The rest follows from it.
