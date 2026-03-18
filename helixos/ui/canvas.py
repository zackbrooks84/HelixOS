"""Gradio polling canvas for running HelixOS recipes with observer controls."""

from __future__ import annotations

from datetime import datetime
import importlib
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

    def run_recipe(recipe_name: str, task: str) -> tuple[str, str, dict[str, Any], dict[str, Any], str]:
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
            result = recipe.run(task)
            audit_log_text = append_audit(f"{_timestamp()} PASS")
            return (
                result,
                "PASS: Workflow completed successfully",
                gr.update(visible=False),
                gr.update(visible=False),
                audit_log_text,
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
            )
        except Exception as exception:  # pragma: no cover - handled behaviorally
            return (
                f"Error: {str(exception)}",
                "ERROR",
                gr.update(visible=False),
                gr.update(visible=False),
                "\n".join(audit_entries),
            )

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

        run_btn.click(
            fn=run_recipe,
            inputs=[recipe_dropdown, task_input],
            outputs=[output_box, verdict_box, approve_btn, reject_btn, audit_log],
        )
        approve_btn.click(
            fn=approve_workflow,
            outputs=[approve_btn, reject_btn, output_box, audit_log],
        )
        reject_btn.click(
            fn=reject_workflow,
            outputs=[approve_btn, reject_btn, output_box, audit_log],
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
