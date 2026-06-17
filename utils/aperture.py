"""Shared aperture/beamwidth estimators used by the pattern modules and GUI.

Keeping these in one place avoids the formulas drifting between the per-pattern
Calc buttons and the compare panel.
"""
import math


def d_lambda_from_gmax(gmax: float, aperture_efficiency: float) -> float:
    """Estimate D/lambda from peak gain and aperture efficiency.

    G = eta * (pi * D / lambda)^2  ->  D/lambda = sqrt(10^(G/10) / eta) / pi
    """
    eta = max(aperture_efficiency, 1e-6)
    return math.sqrt(10.0 ** (gmax / 10.0) / eta) / math.pi


def psi_b_from_d_lambda(d_over_lambda: float) -> float:
    """ITU half-beamwidth estimate: psi_b = sqrt(1200) / (D/lambda)."""
    return math.sqrt(1200.0) / max(d_over_lambda, 1e-9)
