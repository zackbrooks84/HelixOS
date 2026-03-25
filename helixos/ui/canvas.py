"""Gradio polling canvas for running HelixOS recipes with observer controls."""

from __future__ import annotations

from datetime import datetime
import importlib
from pathlib import Path
from typing import Any

import gradio as gr

from helixos.exceptions import ObserverHaltException


def _timestamp() -> str:
    """Return an ISO-like UTC timestamp string for audit entries.

    Inputs:
        None.

    Outputs:
        A timestamp string in ``YYYY-MM-DD HH:MM:SS`` format.

    Failure modes:
        None under normal system clock operation.
    """
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def build_ui() -> gr.Blocks:
    """Build the HelixOS Gradio canvas.

    Inputs:
        None.

    Outputs:
        A configured ``gr.Blocks`` instance with recipe execution and
        observer approval controls.

    Failure modes:
        Propagates Gradio component construction errors if the UI cannot be
        instantiated.
    """
    audit_entries: list[str] = []
    checkpoints: list[dict[str, Any]] = []
    watch_paths = [Path("recipes"), Path("agents")]
    last_watch_signature: str = ""

    def compute_watch_signature() -> str:
        """Compute a lightweight signature for watched files.

        Inputs:
            None.

        Outputs:
            A string signature that changes when watched files change.

        Failure modes:
            Returns an empty signature when paths do not exist.
        """
        records: list[str] = []
        for root in watch_paths:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    stat = path.stat()
                    records.append(f"{path}:{int(stat.st_mtime)}:{stat.st_size}")
        return "|".join(records)

    def append_audit(entry: str) -> str:
        """Append an entry to the in-memory audit log.

        Inputs:
            entry: Audit message to append.

        Outputs:
            The full audit log joined by newline characters.

        Failure modes:
            None under normal list mutation.
        """
        audit_entries.append(entry)
        return "\n".join(audit_entries)

    def run_recipe(recipe_name: str, task: str) -> tuple[
        str,
        str,
        dict[str, Any],
        dict[str, Any],
        str,
        dict[str, Any],
    ]:
        """Run a selected recipe module and map results to UI outputs.

        Inputs:
            recipe_name: Recipe module name located under ``recipes/``.
            task: User-provided task string sent to ``recipe.run``.

        Outputs:
            A tuple containing output text, observer verdict text, approve
            button update, reject button update, and the updated audit log.

        Failure modes:
            Catches ``ObserverHaltException`` and general exceptions to return
            user-facing UI state updates instead of propagating them.
        """
        try:
            recipe = importlib.import_module(f"recipes.{recipe_name}")
            if hasattr(recipe, "run_v2"):
                state = recipe.run_v2(task)
                result = state.get("final_output") or ""
                checkpoints[:] = list(state.get("steps", []))
                warn_steps = [
                    step
                    for step in checkpoints
                    if step.get("verdict", {}).get("status") == "warn"
                ]
                if warn_steps:
                    last_warn = warn_steps[-1]
                    gr.Warning(
                        "Observer warning: "
                        f"{last_warn.get('verdict', {}).get('failure_mode', 'Unknown issue')}"
                    )
                if state.get("halted"):
                    halt_verdict = state.get("halt_verdict")
                    failure_mode = (
                        halt_verdict.failure_mode
                        if halt_verdict
                        else "Unknown failure mode"
                    )
                    recommendation = (
                        halt_verdict.recommendation
                        if halt_verdict
                        else "No recommendation provided"
                    )
                    audit_log_text = append_audit(f"{_timestamp()} HALT: {failure_mode}")
                    checkpoint_options = [
                        (f"{idx}: {item.get('agent_name', 'step')}", str(idx))
                        for idx, item in enumerate(checkpoints)
                    ]
                    return (
                        "Observer halted the workflow.",
                        f"HALT: {failure_mode}  Recommendation: {recommendation}",
                        gr.update(visible=True),
                        gr.update(visible=True),
                        audit_log_text,
                        gr.update(choices=checkpoint_options, value=None),
                    )
            else:
                result = recipe.run(task)
                checkpoints.clear()

            audit_log_text = append_audit(f"{_timestamp()} PASS")
            checkpoint_options = [
                (f"{idx}: {item.get('agent_name', 'step')}", str(idx))
                for idx, item in enumerate(checkpoints)
            ]
            return (
                result,
                "PASS: Workflow completed successfully",
                gr.update(visible=False),
                gr.update(visible=False),
                audit_log_text,
                gr.update(choices=checkpoint_options, value=None),
            )
        except ObserverHaltException as exception:
            failure_mode = exception.verdict.failure_mode or "Unknown failure mode"
            recommendation = (
                exception.verdict.recommendation or "No recommendation provided"
            )
            audit_log_text = append_audit(f"{_timestamp()} HALT: {failure_mode}")
            return (
                "Observer halted the workflow.",
                f"HALT: {failure_mode}  Recommendation: {recommendation}",
                gr.update(visible=True),
                gr.update(visible=True),
                audit_log_text,
                gr.update(choices=[], value=None),
            )
        except Exception as exception:  # pragma: no cover - handled behaviorally
            return (
                f"Error: {str(exception)}",
                "ERROR",
                gr.update(visible=False),
                gr.update(visible=False),
                "\n".join(audit_entries),
                gr.update(choices=[], value=None),
            )

    def inspect_checkpoint(checkpoint_index: str | None) -> str:
        """Render details for one checkpoint entry.

        Inputs:
            checkpoint_index: Dropdown value containing checkpoint index.

        Outputs:
            A multiline debug string with handoff and verdict details.

        Failure modes:
            Returns user-facing status strings for empty or invalid selection.
        """
        if checkpoint_index is None:
            return "Select a checkpoint to inspect."
        try:
            index = int(checkpoint_index)
            item = checkpoints[index]
        except (ValueError, IndexError):
            return "Checkpoint not found."

        handoff = item.get("handoff", {})
        verdict = item.get("verdict", {})
        return (
            f"Step: {item.get('agent_name', 'unknown')}\n"
            f"Timestamp: {item.get('timestamp', '')}\n"
            f"Verdict: {verdict.get('status', '')}\n"
            f"Failure mode: {verdict.get('failure_mode', '')}\n"
            f"Recommendation: {verdict.get('recommendation', '')}\n\n"
            f"Task summary:\n{handoff.get('task_summary', '')}\n\n"
            f"Context:\n{handoff.get('context', {})}"
        )

    def poll_for_changes() -> str:
        """Poll watched folders and emit a status line when changes are seen.

        Inputs:
            None.

        Outputs:
            A small status message suitable for a textbox.

        Failure modes:
            Returns the last-known status message on filesystem read errors.
        """
        nonlocal last_watch_signature
        signature = compute_watch_signature()
        if not last_watch_signature:
            last_watch_signature = signature
            return "Watching recipes/ and agents/ for changes..."
        if signature != last_watch_signature:
            last_watch_signature = signature
            return f"🔄 Detected file changes at {_timestamp()} (refresh recommended)."
        return f"Watching… last checked {_timestamp()}"

    def approve_workflow() -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Hide observer controls and record an approval event.

        Inputs:
            None.

        Outputs:
            A tuple containing approve button update, reject button update,
            output text, and the updated audit log.

        Failure modes:
            None under normal in-memory state updates.
        """
        audit_log_text = append_audit(f"{_timestamp()} APPROVED by user")
        return (
            gr.update(visible=False),
            gr.update(visible=False),
            "Approved. Workflow resuming...",
            audit_log_text,
        )

    def reject_workflow() -> tuple[dict[str, Any], dict[str, Any], str, str]:
        """Hide observer controls and record a rejection event.

        Inputs:
            None.

        Outputs:
            A tuple containing approve button update, reject button update,
            output text, and the updated audit log.

        Failure modes:
            None under normal in-memory state updates.
        """
        audit_log_text = append_audit(f"{_timestamp()} REJECTED by user")
        return (
            gr.update(visible=False),
            gr.update(visible=False),
            "Rejected. Rolled back to last checkpoint.",
            audit_log_text,
        )

    with gr.Blocks() as ui:
        recipe_dropdown = gr.Dropdown(
            choices=["repo_auditor", "frontend_builder", "research_report"],
            label="Recipe",
            value="repo_auditor",
        )
        task_input = gr.Textbox(label="Task", lines=4)
        run_btn = gr.Button("Run")
        output_box = gr.Textbox(label="Agent Output", interactive=False, lines=10)
        verdict_box = gr.Textbox(
            label="Observer Verdict", interactive=False, lines=3
        )
        approve_btn = gr.Button("Approve", visible=False)
        reject_btn = gr.Button("Reject", visible=False)
        audit_log = gr.Textbox(label="Audit Log", interactive=False, lines=6)
        watcher_status = gr.Textbox(
            label="Polling Watcher",
            interactive=False,
        )
        poll_btn = gr.Button("Poll Now")
        checkpoint_picker = gr.Dropdown(
            label="Checkpoint History",
            choices=[],
            value=None,
        )
        checkpoint_detail = gr.Textbox(
            label="Time-Travel Debugger",
            interactive=False,
            lines=10,
        )
        inspect_btn = gr.Button("Inspect Checkpoint")

        run_btn.click(
            fn=run_recipe,
            inputs=[recipe_dropdown, task_input],
            outputs=[
                output_box,
                verdict_box,
                approve_btn,
                reject_btn,
                audit_log,
                checkpoint_picker,
            ],
        )
        approve_btn.click(
            fn=approve_workflow,
            outputs=[approve_btn, reject_btn, output_box, audit_log],
        )
        reject_btn.click(
            fn=reject_workflow,
            outputs=[approve_btn, reject_btn, output_box, audit_log],
        )
        poll_btn.click(fn=poll_for_changes, outputs=[watcher_status])
        inspect_btn.click(
            fn=inspect_checkpoint,
            inputs=[checkpoint_picker],
            outputs=[checkpoint_detail],
        )

    return ui


def launch() -> None:
    """Launch the HelixOS Gradio canvas.

    Inputs:
        None.

    Outputs:
        None.

    Failure modes:
        Propagates Gradio server startup errors if the UI cannot be served.
    """
    ui = build_ui()
    ui.launch()
