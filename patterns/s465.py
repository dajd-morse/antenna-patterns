"""
ITU-R S.465 — Reference earth station antenna gain pattern for interference assessment.

Simpler than S.580 — no intermediate G₁ plateau; main lobe transitions directly
to the 32−25 log(φ) sidelobe envelope.

  G(φ) = Gmax − 2.5×10⁻³(D/λ · φ)²   0 ≤ |φ| < φ₁
  G(φ) = 32 − 25 log(|φ|)             φ₁ ≤ |φ| ≤ 48°
  G(φ) = −10 dBi                        48° < |φ|

φ₁ is the angle where the main lobe Gaussian descends to equal 32−25log(φ).
"""
import numpy as np
from .base import AntennaPattern, ParamSpec


def _dλ(gmax: float, eta: float = 0.6) -> float:
    return np.sqrt(10 ** (gmax / 10) / eta) / np.pi


def _find_transition(gmax: float, dλ: float) -> float:
    """
    Find φ₁ where  Gmax − 2.5e-3·(dλ·φ)²  =  32 − 25·log10(φ).
    Searches for the last falling crossing (main lobe dropping below sidelobe mask).
    """
    phi_test = np.linspace(0.05, 90.0, 200_000)
    main = gmax - 2.5e-3 * (dλ * phi_test) ** 2
    side = 32.0 - 25.0 * np.log10(phi_test)
    diff = main - side
    # Falling crossings: diff goes from positive to negative
    idx = np.where(np.diff(np.sign(diff)) < 0)[0]
    if len(idx) > 0:
        # Interpolate for accuracy
        i = idx[-1]
        t = diff[i] / (diff[i] - diff[i + 1])
        return float(phi_test[i] + t * (phi_test[i + 1] - phi_test[i]))
    return 100.0 / dλ


class S465Pattern(AntennaPattern):
    name = "ITU-R S.465"
    description = "Reference earth station gain pattern for interference assessment (FSS)"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain', 'float', 45.0, 0.0, 70.0, 0.5,
                      units='dBi',
                      tooltip='Maximum gain at boresight'),
        ]

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gmax = params['gmax']
        dλ = _dλ(gmax)

        phi = np.abs(phi)
        G = np.full_like(phi, -10.0, dtype=float)

        phi_1 = _find_transition(gmax, dλ)

        r1 = phi <= phi_1
        r2 = (phi > phi_1) & (phi <= 48.0)

        G[r1] = gmax - 2.5e-3 * (dλ * phi[r1]) ** 2
        with np.errstate(divide='ignore', invalid='ignore'):
            G[r2] = 32.0 - 25.0 * np.log10(np.where(phi[r2] > 0, phi[r2], 1e-9))

        return G
