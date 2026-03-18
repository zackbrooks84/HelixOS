from __future__ import annotations

import pytest

import gradio as gr


def test_blocks_collect_components_and_dependencies() -> None:
    """Blocks should record components and callbacks in config.

    Inputs:
        None.

    Outputs:
        None.

    Failure modes:
        Test fails if the stub does not mimic the subset used by the UI.
    """

    def on_click() -> str:
        return "done"

    with gr.Blocks() as ui:
        gr.Dropdown(choices=["a", "b"], label="Mode", value="a")
        button = gr.Button("Run")
        button.click(fn=on_click)

    assert ui.config["components"][0]["props"]["choices"] == [("a", "a"), ("b", "b")]
    assert ui.config["dependencies"] == [{"id": 0}]
    assert ui.fns[0].fn() == "done"


def test_component_creation_without_blocks_raises_runtime_error() -> None:
    """Component creation should fail outside a Blocks context.

    Inputs:
        None.

    Outputs:
        None.

    Failure modes:
        Test fails if the stub silently allows invalid component creation.
    """
    with pytest.raises(RuntimeError, match="Blocks context is not active"):
        gr.Textbox(label="Loose field")
