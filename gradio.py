"""Lightweight Gradio test double used when the real dependency is unavailable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, ClassVar


class Blocks:
    """Minimal subset of ``gradio.Blocks`` needed by the test suite.

    Inputs:
        None.

    Outputs:
        A context manager that records component definitions and callback
        registrations in a ``config`` dictionary.

    Failure modes:
        Raises ``RuntimeError`` if a component is created outside an active
        ``Blocks`` context.
    """

    _stack: ClassVar[list["Blocks"]] = []

    def __init__(self) -> None:
        """Initialize an empty Blocks tree.

        Inputs:
            None.

        Outputs:
            None. Sets up component and dependency registries.

        Failure modes:
            None.
        """
        self.config: dict[str, Any] = {"components": [], "dependencies": []}
        self.fns: list[_DependencyFn] = []

    def __enter__(self) -> "Blocks":
        """Enter the active Blocks context.

        Inputs:
            None.

        Outputs:
            The active ``Blocks`` instance.

        Failure modes:
            None.
        """
        Blocks._stack.append(self)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit the active Blocks context.

        Inputs:
            exc_type: Exception type if one was raised in the context.
            exc: Exception instance if one was raised in the context.
            tb: Traceback object if one was raised in the context.

        Outputs:
            None.

        Failure modes:
            None.
        """
        Blocks._stack.pop()

    @classmethod
    def current(cls) -> "Blocks":
        """Return the currently active Blocks instance.

        Inputs:
            None.

        Outputs:
            The top-most active ``Blocks`` instance.

        Failure modes:
            Raises ``RuntimeError`` when called with no active context.
        """
        if not cls._stack:
            raise RuntimeError("Blocks context is not active.")
        return cls._stack[-1]

    def _register_component(self, component_type: str, props: dict[str, Any]) -> None:
        """Record a component configuration.

        Inputs:
            component_type: Logical component type label.
            props: Serialized component properties.

        Outputs:
            None.

        Failure modes:
            None.
        """
        self.config["components"].append({"type": component_type, "props": props})

    def _register_dependency(self, fn: Callable[..., Any]) -> int:
        """Register an event callback.

        Inputs:
            fn: Callable to expose through ``fns`` and ``dependencies``.

        Outputs:
            The numeric dependency identifier.

        Failure modes:
            None.
        """
        dependency_id = len(self.fns)
        self.fns.append(_DependencyFn(fn=fn))
        self.config["dependencies"].append({"id": dependency_id})
        return dependency_id

    def launch(self) -> None:
        """Launch the UI server.

        Inputs:
            None.

        Outputs:
            None.

        Failure modes:
            None in the test double.
        """
        return None


@dataclass
class _DependencyFn:
    """Stored dependency callback wrapper.

    Inputs:
        fn: Callback function registered by a component event.

    Outputs:
        Dataclass instance exposing ``fn``.

    Failure modes:
        None.
    """

    fn: Callable[..., Any]


class _Component:
    """Base component that auto-registers itself with the active Blocks tree.

    Inputs:
        **props: Serialized component properties.

    Outputs:
        Component instance with stored props.

    Failure modes:
        Raises ``RuntimeError`` if no ``Blocks`` context is active.
    """

    component_type = "component"

    def __init__(self, **props: Any) -> None:
        """Register a component with the active Blocks context.

        Inputs:
            **props: Serialized component properties.

        Outputs:
            None.

        Failure modes:
            Raises ``RuntimeError`` if the component is created outside a
            ``Blocks`` context.
        """
        self.props = props
        Blocks.current()._register_component(self.component_type, props)


class Dropdown(_Component):
    """Dropdown component with normalized choice tuples."""

    component_type = "dropdown"

    def __init__(self, choices: list[str], label: str, value: str) -> None:
        """Create a dropdown component.

        Inputs:
            choices: List of selectable string options.
            label: User-facing field label.
            value: Default selected option.

        Outputs:
            None.

        Failure modes:
            Propagates ``RuntimeError`` from ``Blocks.current`` if there is no
            active UI context.
        """
        normalized = [(choice, choice) for choice in choices]
        super().__init__(choices=normalized, label=label, value=value)


class Textbox(_Component):
    """Textbox component for editable or read-only text."""

    component_type = "textbox"

    def __init__(self, label: str, lines: int = 1, interactive: bool = True) -> None:
        """Create a textbox component.

        Inputs:
            label: User-facing field label.
            lines: Default rendered line count.
            interactive: Whether the textbox accepts user edits.

        Outputs:
            None.

        Failure modes:
            Propagates ``RuntimeError`` from ``Blocks.current`` if there is no
            active UI context.
        """
        super().__init__(label=label, lines=lines, interactive=interactive)


class Button(_Component):
    """Button component supporting click callback registration."""

    component_type = "button"

    def __init__(self, value: str, visible: bool = True) -> None:
        """Create a button component.

        Inputs:
            value: Button label.
            visible: Whether the button is initially visible.

        Outputs:
            None.

        Failure modes:
            Propagates ``RuntimeError`` from ``Blocks.current`` if there is no
            active UI context.
        """
        super().__init__(value=value, visible=visible)

    def click(
        self,
        fn: Callable[..., Any],
        inputs: list[Any] | None = None,
        outputs: list[Any] | None = None,
    ) -> None:
        """Register a click callback.

        Inputs:
            fn: Callback to execute when the button is clicked.
            inputs: Unused in the test double, kept for compatibility.
            outputs: Unused in the test double, kept for compatibility.

        Outputs:
            None.

        Failure modes:
            Propagates ``RuntimeError`` from ``Blocks.current`` if there is no
            active UI context.
        """
        del inputs, outputs
        Blocks.current()._register_dependency(fn)


def update(**kwargs: Any) -> dict[str, Any]:
    """Return a Gradio-style component update payload.

    Inputs:
        **kwargs: Arbitrary component property overrides.

    Outputs:
        A plain dictionary containing the provided update fields.

    Failure modes:
        None.
    """
    return kwargs
