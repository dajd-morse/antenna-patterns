from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
import numpy as np


@dataclass
class ParamSpec:
    name: str
    label: str
    type: str        # 'float' | 'choice'
    default: Any
    min: float = None
    max: float = None
    step: float = None
    choices: list = None
    units: str = ''
    tooltip: str = ''
    computed: bool = False   # adds an auto-compute button in the UI


class AntennaPattern(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        """Return gain (dBi) array for angles phi (degrees from boresight)."""
        pass

    @abstractmethod
    def get_params_spec(self) -> list[ParamSpec]:
        pass

    def get_default_params(self) -> dict:
        return {p.name: p.default for p in self.get_params_spec()}

    def reference_peak(self, params: dict) -> Optional[float]:
        """Reference peak gain (dBi) for "dB below peak" contours, or None.

        Return None when the pattern has no meaningful main-lobe peak parameter
        (e.g. earth-station envelopes whose peak is the curve maximum). The
        plot widget then falls back to the maximum finite gain of the curve.
        """
        return None

    def suggest_derived(self, name: str, params: dict) -> Optional[float]:
        """Return a suggested value for a 'computed' parameter, or None."""
        return None

    def is_param_applicable(self, name: str, params: dict) -> bool:
        """Return whether a parameter is active for the current selection."""
        return True

    def param_warning(self, name: str, params: dict) -> str:
        """Return a user-facing warning for a parameter, or an empty string."""
        return ""
