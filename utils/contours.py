import numpy as np


def first_descent(phi: np.ndarray, gain: np.ndarray, target: float) -> float | None:
    """
    Return the first angle where gain reaches or descends through target.

    Equality matters for ITU masks with sidelobe plateaus: a -20 dB contour
    should report the beginning of a -20 dB plateau, not the far edge where the
    curve finally drops below it.
    """
    eps = 1e-9
    for i in range(len(gain) - 1):
        g0, g1 = gain[i], gain[i + 1]
        if np.isnan(g0) or np.isnan(g1):
            continue
        if abs(g0 - target) <= eps:
            return float(phi[i])
        if g0 > target and g1 <= target:
            t = (target - g0) / (g1 - g0)
            return float(phi[i] + t * (phi[i + 1] - phi[i]))
    if len(gain) and np.isfinite(gain[-1]) and abs(gain[-1] - target) <= eps:
        return float(phi[-1])
    return None
