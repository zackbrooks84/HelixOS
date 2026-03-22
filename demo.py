"""HelixOS demo — runs without requiring Ollama to be active.

Usage:
    python demo.py

Everything that can be exercised locally is tested and reported.  Components
that need a live Ollama server are shown with the status they would have once
Ollama is running.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ``helixos`` and ``recipes`` are
# importable when running directly (not via an installed package).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(label: str) -> None:
    print(f"  \u2713 {label}")


def _fail(label: str) -> None:
    print(f"  \u2717 {label}")


def _info(label: str) -> None:
    print(f"    \u2192 {label}")


# ---------------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------------

def demo_agents() -> int:
    """Load all agents and return the count."""
    print("\n[1] Agent Loading")
    from helixos.agents.loader import load_all_agents

    agents_dir = str(PROJECT_ROOT / "agents" / "core")
    try:
        agents = load_all_agents(agents_dir)
        _ok(f"Agents loaded: {len(agents)} agent(s) found")
        for a in agents:
            _info(f"{a.name} v{a.version} — {a.description[:60]}")
        return len(agents)
    except FileNotFoundError as exc:
        _fail(f"Could not load agents: {exc}")
        return 0


def demo_router() -> None:
    """Show model selection for representative task keywords."""
    print("\n[2] IntelligentRouter — model selection")
    from helixos.orchestrator.router import IntelligentRouter
    from helixos.agents.loader import AgentDefinition

    try:
        router = IntelligentRouter()

        samples: list[tuple[str, str]] = [
            ("Code Reviewer", "Expert code reviewer focused on correctness"),
            ("Security Auditor", "security vulnerability audit"),
            ("Research Analyst", "research and reporting analyst"),
            ("Frontend Builder", "frontend UI CSS component builder"),
            ("General Assistant", "general purpose task assistant"),
        ]

        for name, desc in samples:
            stub = AgentDefinition(
                name=name,
                description=desc,
                version="1.0",
            )
            model = router.get_model(stub)
            _ok(f"{name!r} task  ->  {model}")
    except Exception as exc:
        _fail(f"Router failed: {exc}")


def demo_resource_monitor() -> None:
    """Report available RAM and GPU state."""
    print("\n[3] ResourceMonitor")
    from helixos.resources.monitor import ResourceMonitor

    try:
        monitor = ResourceMonitor()
        ram = monitor.get_available_ram_gb()
        gpu_label = "GPU detected" if monitor.has_gpu else "no GPU"
        _ok(f"{ram:.1f} GB RAM available, {gpu_label}")

        # Show model feasibility for the default role models.
        for model in ("qwen2.5:7b", "deepseek-coder:14b", "qwen2.5:70b"):
            feasible = monitor.can_run(model)
            status = "can run" if feasible else "insufficient RAM"
            _info(f"{model}: {status}")
    except Exception as exc:
        _fail(f"ResourceMonitor failed: {exc}")


def demo_ollama_health() -> bool:
    """Probe Ollama and return True if reachable."""
    print("\n[4] Ollama Connectivity")
    import httpx

    url = "http://localhost:11434/api/tags"
    try:
        resp = httpx.get(url, timeout=3.0)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            _ok(f"Ollama reachable at localhost:11434")
            if models:
                for m in models:
                    _info(f"model available: {m}")
            else:
                _info("no models pulled yet  (run: ollama pull qwen2.5:7b)")
            return True
        else:
            _fail(f"Ollama returned HTTP {resp.status_code}")
            return False
    except Exception:
        _fail("Ollama: not reachable at localhost:11434  (run: ollama serve)")
        _info("Skills indexing would use nomic-embed-text")
        _info("Recipes ready: " + ", ".join(["repo_auditor", "frontend_builder", "research_report"]))
        return False


def demo_skill_validation() -> None:
    """Validate the bundled skill folders using HelixOS.validate_skill."""
    print("\n[5] Skill Folder Validation")
    from helixos import HelixOS

    helix = HelixOS(agents_dir=str(PROJECT_ROOT / "agents" / "core"))

    skill_dirs: list[Path] = [
        PROJECT_ROOT / "agents" / "core" / "critics" / "reliability_check",
        PROJECT_ROOT / "agents" / "core" / "code_review",
        PROJECT_ROOT / "agents" / "core" / "security_review",
        PROJECT_ROOT / "agents" / "core" / "critics" / "__nonexistent__",
    ]

    for skill_dir in skill_dirs:
        result = helix.validate_skill(str(skill_dir))
        label = skill_dir.name
        if result["valid"]:
            _ok(f"Skill '{label}': valid")
        else:
            _fail(f"Skill '{label}': {'; '.join(result['errors'])}")


def demo_semantic_discovery_init() -> None:
    """Try to initialise SemanticSkillDiscovery; handle Ollama absence cleanly."""
    print("\n[6] SemanticSkillDiscovery (graceful degradation)")
    from helixos.agents.semantic_loader import SemanticSkillDiscovery

    skills_dir = str(PROJECT_ROOT / "agents" / "core")
    try:
        SemanticSkillDiscovery(skills_dir)
        _ok("SemanticSkillDiscovery initialised and skills indexed")
    except Exception as exc:
        exc_text = str(exc)
        if "connect" in exc_text.lower() or "connection" in exc_text.lower():
            _fail("SemanticSkillDiscovery: Ollama not reachable (expected without server)")
            _info("Would embed skill prompts with nomic-embed-text once Ollama is running")
        else:
            _fail(f"SemanticSkillDiscovery: {exc}")


def demo_critic_verdict_model() -> None:
    """Instantiate CriticVerdict directly to confirm Pydantic model is healthy."""
    print("\n[7] CriticVerdict Pydantic Model")
    from helixos.pydantic_models.critic import CriticVerdict

    try:
        pass_verdict = CriticVerdict(status="pass")
        warn_verdict = CriticVerdict(
            status="warn",
            failure_mode="output too short",
            recommendation="expand the analysis section",
        )
        halt_verdict = CriticVerdict(
            status="halt",
            failure_mode="SQL injection risk detected",
            recommendation="reject handoff and re-run security agent",
        )
        _ok(f"pass verdict:  status={pass_verdict.status}")
        _ok(f"warn verdict:  failure_mode={warn_verdict.failure_mode!r}")
        _ok(f"halt verdict:  failure_mode={halt_verdict.failure_mode!r}")
    except Exception as exc:
        _fail(f"CriticVerdict validation failed: {exc}")


def demo_facade_list_agents() -> None:
    """Show HelixOS.list_agents() output."""
    print("\n[8] HelixOS Facade — list_agents()")
    from helixos import HelixOS

    helix = HelixOS(agents_dir=str(PROJECT_ROOT / "agents" / "core"))
    agents = helix.list_agents()
    if agents:
        _ok(f"list_agents() returned {len(agents)} agent(s)")
        for a in agents:
            _info(f"{a['name']} ({a['version']})")
    else:
        _fail("list_agents() returned nothing — check agents_dir")


def demo_facade_list_recipes() -> None:
    """Show HelixOS.list_recipes() output."""
    print("\n[9] HelixOS Facade — list_recipes()")
    from helixos import HelixOS

    helix = HelixOS()
    recipes = helix.list_recipes()
    _ok("Recipes: " + ", ".join(recipes))


def demo_facade_health() -> None:
    """Show HelixOS.check_health() output."""
    print("\n[10] HelixOS Facade — check_health()")
    from helixos import HelixOS

    helix = HelixOS(agents_dir=str(PROJECT_ROOT / "agents" / "core"))
    health = helix.check_health()
    ollama_label = "reachable" if health["ollama"] else "not reachable"
    gpu_label = "GPU detected" if health["gpu"] else "no GPU"
    _ok(f"ollama={ollama_label}, ram={health['ram_gb']} GB, {gpu_label}")
    if health["models"]:
        for m in health["models"]:
            _info(f"model: {m}")
    else:
        _info("No Ollama models available")


# ---------------------------------------------------------------------------
# Usage footer
# ---------------------------------------------------------------------------

def print_usage_footer(ollama_available: bool) -> None:
    print("\n" + "=" * 50)
    print("To run a full recipe (requires Ollama):")
    print('  helixos run repo_auditor')
    print('  or: python -c "from helixos import HelixOS; '
          "print(HelixOS().run('repo_auditor', 'audit this repo'))\"")
    if not ollama_available:
        print("\nOllama is not running. Start it with:")
        print("  ollama serve")
        print("Then pull a model:")
        print("  ollama pull qwen2.5:7b")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("HelixOS Demo")
    print("============")

    demo_agents()
    demo_router()
    demo_resource_monitor()
    ollama_ok = demo_ollama_health()
    demo_skill_validation()
    demo_semantic_discovery_init()
    demo_critic_verdict_model()
    demo_facade_list_agents()
    demo_facade_list_recipes()
    demo_facade_health()
    print_usage_footer(ollama_ok)


if __name__ == "__main__":
    main()
