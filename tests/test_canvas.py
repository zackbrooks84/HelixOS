from __future__ import annotations

from typing import Any

import gradio as gr
import pytest

from helixos.exceptions import ObserverHaltException
from helixos.pydantic_models.critic import CriticVerdict
from helixos.ui.canvas import build_ui


def _find_component(blocks: gr.Blocks, label: str) -> Any:
    """Find a component in the Gradio config by label.

    Inputs:
        blocks: Gradio Blocks instance to inspect.
        label: Component label to locate.

    Outputs:
        The matching component configuration dictionary.

    Failure modes:
        Raises ``AssertionError`` if the component label is not present.
    """
    for component in blocks.config["components"]:
        props = component.get("props", {})
        if props.get("label") == label:
            return component
    raise AssertionError(f"Component with label {label!r} not found")


def test_build_ui_returns_blocks() -> None:
    """Build UI should return a Gradio Blocks instance.

    Inputs:
        None.

    Outputs:
        None.

    Failure modes:
        Test fails if ``build_ui`` does not return ``gr.Blocks``.
    """
    ui = build_ui()

    assert isinstance(ui, gr.Blocks)


def test_build_ui_configures_expected_components_and_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build UI should register required components and click handlers.

    Inputs:
        monkeypatch: Pytest monkeypatch fixture for deterministic setup.

    Outputs:
        None.

    Failure modes:
        Test fails if required components or event handlers are missing.
    """
    monkeypatch.setattr('helixos.ui.canvas.datetime', type('FixedDateTime', (), {
        'utcnow': staticmethod(lambda: __import__('datetime').datetime(2026, 3, 18, 12, 0, 0))
    }))
    ui = build_ui()

    recipe_dropdown = _find_component(ui, 'Recipe')
    task_input = _find_component(ui, 'Task')
    output_box = _find_component(ui, 'Agent Output')
    verdict_box = _find_component(ui, 'Observer Verdict')
    audit_log = _find_component(ui, 'Audit Log')

    assert recipe_dropdown['props']['choices'] == [
        ('repo_auditor', 'repo_auditor'),
        ('frontend_builder', 'frontend_builder'),
        ('research_report', 'research_report'),
    ]
    assert recipe_dropdown['props']['value'] == 'repo_auditor'
    assert task_input['props']['lines'] == 4
    assert output_box['props']['interactive'] is False
    assert verdict_box['props']['interactive'] is False
    assert audit_log['props']['interactive'] is False
    assert len(ui.config['dependencies']) == 3


def test_run_handler_reports_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run handler should report PASS results for successful recipes.

    Inputs:
        monkeypatch: Pytest monkeypatch fixture for dependency injection.

    Outputs:
        None.

    Failure modes:
        Test fails if the click handler does not map success state correctly.
    """

    class FixedDateTime:
        @staticmethod
        def utcnow() -> Any:
            import datetime as dt

            return dt.datetime(2026, 3, 18, 12, 0, 0)

    class SuccessRecipe:
        @staticmethod
        def run(task: str) -> str:
            return f'Result for {task}'

    monkeypatch.setattr('helixos.ui.canvas.datetime', FixedDateTime)
    monkeypatch.setattr('helixos.ui.canvas.importlib.import_module', lambda name: SuccessRecipe)
    ui = build_ui()
    run_dep = ui.config['dependencies'][0]
    run_fn = ui.fns[run_dep['id']].fn

    result = run_fn('repo_auditor', 'inspect repo')

    assert result[0] == 'Result for inspect repo'
    assert result[1] == 'PASS: Workflow completed successfully'
    assert result[2]['visible'] is False
    assert result[3]['visible'] is False
    assert result[4].endswith('PASS')


def test_run_handler_reports_halt_and_approve_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    """Handlers should map halt, approve, and reject UI states correctly.

    Inputs:
        monkeypatch: Pytest monkeypatch fixture for dependency injection.

    Outputs:
        None.

    Failure modes:
        Test fails if halt or follow-up controls do not return expected state.
    """

    class FixedDateTime:
        @staticmethod
        def utcnow() -> Any:
            import datetime as dt

            return dt.datetime(2026, 3, 18, 12, 0, 0)

    class HaltRecipe:
        @staticmethod
        def run(task: str) -> str:
            raise ObserverHaltException(
                CriticVerdict(
                    status='halt',
                    failure_mode='Bug found',
                    recommendation='Fix it',
                )
            )

    monkeypatch.setattr('helixos.ui.canvas.datetime', FixedDateTime)
    monkeypatch.setattr('helixos.ui.canvas.importlib.import_module', lambda name: HaltRecipe)
    ui = build_ui()
    run_fn = ui.fns[ui.config['dependencies'][0]['id']].fn
    approve_fn = ui.fns[ui.config['dependencies'][1]['id']].fn
    reject_fn = ui.fns[ui.config['dependencies'][2]['id']].fn

    halt_result = run_fn('repo_auditor', 'inspect repo')
    approve_result = approve_fn()
    reject_result = reject_fn()

    assert halt_result[0] == 'Observer halted the workflow.'
    assert halt_result[1] == 'HALT: Bug found  Recommendation: Fix it'
    assert halt_result[2]['visible'] is True
    assert halt_result[3]['visible'] is True
    assert 'HALT: Bug found' in halt_result[4]
    assert approve_result[0]['visible'] is False
    assert approve_result[1]['visible'] is False
    assert approve_result[2] == 'Approved. Workflow resuming...'
    assert approve_result[3].endswith('APPROVED by user')
    assert reject_result[0]['visible'] is False
    assert reject_result[1]['visible'] is False
    assert reject_result[2] == 'Rejected. Rolled back to last checkpoint.'
    assert reject_result[3].endswith('REJECTED by user')
