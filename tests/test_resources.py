from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from helixos.resources.monitor import ResourceMonitor


def test_resource_monitor_enables_gpu_when_pynvml_initializes() -> None:
    fake_pynvml = ModuleType("pynvml")
    fake_pynvml.nvmlInit = lambda: None

    with patch.dict(sys.modules, {"pynvml": fake_pynvml}):
        monitor = ResourceMonitor()

    assert monitor.has_gpu is True


@patch("helixos.resources.monitor.psutil.virtual_memory")
def test_get_available_ram_gb_uses_psutil(mock_virtual_memory) -> None:
    mock_virtual_memory.return_value = SimpleNamespace(available=12_500_000_000)

    monitor = ResourceMonitor()

    assert monitor.get_available_ram_gb() == 12.5


@patch.object(ResourceMonitor, "get_available_vram_gb", return_value=8.0)
def test_can_run_7b_with_8gb_vram(mock_get_available_vram_gb) -> None:
    monitor = ResourceMonitor()
    monitor.has_gpu = True

    assert monitor.can_run("qwen2.5:7b") is True
    mock_get_available_vram_gb.assert_called_once_with()


@patch.object(ResourceMonitor, "get_available_vram_gb", return_value=8.0)
def test_cannot_run_14b_with_8gb_vram(mock_get_available_vram_gb) -> None:
    monitor = ResourceMonitor()
    monitor.has_gpu = True

    assert monitor.can_run("deepseek-coder:14b") is False
    mock_get_available_vram_gb.assert_called_once_with()


@patch.object(ResourceMonitor, "get_available_ram_gb", return_value=16.0)
def test_falls_back_to_ram_when_no_gpu(mock_get_available_ram_gb) -> None:
    monitor = ResourceMonitor()
    monitor.has_gpu = False

    assert monitor.can_run("qwen2.5:7b") is True
    mock_get_available_ram_gb.assert_called_once_with()
