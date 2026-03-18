from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SimpleMocker:
    """Minimal pytest-mock compatible helper for local tests.

    Inputs:
        None.

    Outputs:
        A helper exposing ``patch`` and ``Mock`` similar to pytest-mock's
        fixture API.

    Failure modes:
        Propagates patching errors from ``unittest.mock``.
    """

    def __init__(self) -> None:
        """Initialize the patch tracker.

        Inputs:
            None.

        Outputs:
            None.

        Failure modes:
            None.
        """
        self._patches: list[patch] = []
        self.Mock = MagicMock

    def patch(self, target: str, *args, **kwargs):
        """Start and track a patcher.

        Inputs:
            target: Import path to patch.
            *args: Positional arguments forwarded to ``unittest.mock.patch``.
            **kwargs: Keyword arguments forwarded to ``unittest.mock.patch``.

        Outputs:
            The started mock object returned by the patcher.

        Failure modes:
            Propagates invalid patch target or configuration errors.
        """
        patcher = patch(target, *args, **kwargs)
        started = patcher.start()
        self._patches.append(patcher)
        return started

    def stopall(self) -> None:
        """Stop all active patchers created through this helper.

        Inputs:
            None.

        Outputs:
            None.

        Failure modes:
            Propagates unexpected teardown errors from ``unittest.mock``.
        """
        for patcher in reversed(self._patches):
            patcher.stop()
        self._patches.clear()


@pytest.fixture()
def mocker() -> SimpleMocker:
    """Provide a lightweight stand-in for the pytest-mock fixture.

    Inputs:
        None.

    Outputs:
        A ``SimpleMocker`` instance.

    Failure modes:
        None directly; teardown stops all started patchers.
    """
    helper = SimpleMocker()
    try:
        yield helper
    finally:
        helper.stopall()
