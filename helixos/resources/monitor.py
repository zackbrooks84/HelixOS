"""System resource monitoring helpers for local model routing."""

from __future__ import annotations

from types import SimpleNamespace

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - environment-dependent fallback
    def _missing_virtual_memory() -> SimpleNamespace:
        """Raise a clear error when psutil is unavailable.

        Inputs:
            None.

        Outputs:
            This function does not return successfully.

        Failure modes:
            Raises ``ModuleNotFoundError`` describing the missing dependency.
        """

        raise ModuleNotFoundError(
            "psutil is required for ResourceMonitor RAM inspection."
        )

    psutil = SimpleNamespace(virtual_memory=_missing_virtual_memory)


class ResourceMonitor:
    """Inspect available system resources for local model selection.

    Inputs:
        None.

    Outputs:
        A monitor instance with GPU availability state cached in ``has_gpu``.

    Failure modes:
        GPU initialization failures are swallowed and recorded by setting
        ``has_gpu`` to ``False``.
    """

    def __init__(self) -> None:
        """Initialize optional NVML access.

        Inputs:
            None.

        Outputs:
            None.

        Failure modes:
            Any exception raised while importing or initializing ``pynvml`` is
            swallowed and causes ``has_gpu`` to be set to ``False``.
        """

        self.has_gpu = False
        self._pynvml = None

        try:
            import pynvml  # type: ignore

            pynvml.nvmlInit()
            self._pynvml = pynvml
            self.has_gpu = True
        except Exception:
            self.has_gpu = False
            self._pynvml = None

    def get_available_vram_gb(self) -> float:
        """Return the free VRAM for GPU device 0 in gigabytes.

        Inputs:
            None.

        Outputs:
            Free VRAM measured as ``bytes / 1e9``.

        Failure modes:
            Returns ``0.0`` when no GPU is available.
        """

        if not self.has_gpu or self._pynvml is None:
            return 0.0

        handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
        memory_info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
        return float(memory_info.free) / 1e9

    def get_available_ram_gb(self) -> float:
        """Return currently available system RAM in gigabytes.

        Inputs:
            None.

        Outputs:
            Available RAM measured as ``bytes / 1e9``.

        Failure modes:
            Propagates unexpected ``psutil`` errors.
        """

        return float(psutil.virtual_memory().available) / 1e9

    def can_run(self, model_name: str) -> bool:
        """Estimate whether the current system can run a model.

        Inputs:
            model_name: Model identifier whose parameter size suffix is used to
                estimate memory requirements.

        Outputs:
            ``True`` when enough VRAM or RAM is available, otherwise ``False``.

        Failure modes:
            Propagates unexpected ``psutil`` or NVML errors encountered during
            resource inspection after initialization succeeds.
        """

        normalized_name = model_name.lower()
        required_gb = 8.0
        if "70b" in normalized_name:
            required_gb = 48.0
        elif "14b" in normalized_name:
            required_gb = 16.0
        elif "7b" in normalized_name:
            required_gb = 8.0
        elif "3b" in normalized_name:
            required_gb = 4.0

        if self.has_gpu:
            return self.get_available_vram_gb() >= required_gb
        return self.get_available_ram_gb() >= required_gb
