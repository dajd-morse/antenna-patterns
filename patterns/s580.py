"""
ITU-R S.580 — Reference earth station antenna gain pattern (FSS).

For D/λ ≥ 100:
  G(φ) = Gmax − 2.5×10⁻³(D/λ · φ)²   0 ≤ |φ| < φm
  G(φ) = G₁ = −1 + 15 log(D/λ)        φm ≤ |φ| ≤ φ₁
  G(φ) = 32 − 25 log(|φ|)             φ₁ < |φ| ≤ 48°
  G(φ) = −10 dBi                        48° < |φ|

For D/λ < 100:
  Outer sidelobe → 52 − 10 log(D/λ) − 25 log(|φ|),  floor 10 − 10 log(D/λ)
"""
import numpy as np
from .base import AntennaPattern, ParamSpec


def _dλ(gmax: float, eta: float = 0.6) -> float:
    return np.sqrt(10 ** (gmax / 10) / eta) / np.pi


class S580Pattern(AntennaPattern):
    name = "ITU-R S.580"
    description = "Earth station reference antenna gain pattern (FSS)"

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

        if dλ >= 100:
            g1 = -1.0 + 15.0 * np.log10(dλ)
            if gmax <= g1:
                g1 = gmax - 1.0
            phi_m = (20.0 / dλ) * np.sqrt(gmax - g1)
            # φ₁: where G₁ plateau meets 32−25log rolloff
            phi_1 = max(100.0 / dλ, 10 ** ((32.0 - g1) / 25.0))

            r1 = phi <= phi_m
            r2 = (phi > phi_m) & (phi <= phi_1)
            r3 = (phi > phi_1) & (phi <= 48.0)

            G[r1] = gmax - 2.5e-3 * (dλ * phi[r1]) ** 2
            G[r2] = g1
            with np.errstate(divide='ignore', invalid='ignore'):
                G[r3] = 32.0 - 25.0 * np.log10(np.where(phi[r3] > 0, phi[r3], 1e-9))
        else:
            outer_sl = 52.0 - 10.0 * np.log10(dλ)
            outer_floor = 10.0 - 10.0 * np.log10(dλ)
            g1 = outer_sl
            if gmax <= g1:
                g1 = gmax - 1.0
            phi_m = (20.0 / dλ) * np.sqrt(gmax - g1)
            phi_1 = max(100.0 / dλ, 10 ** ((outer_sl - g1) / 25.0))

            r1 = phi <= phi_m
            r2 = (phi > phi_m) & (phi <= phi_1)
            r3 = (phi > phi_1) & (phi <= 48.0)
            r4 = phi > 48.0

            G[r1] = gmax - 2.5e-3 * (dλ * phi[r1]) ** 2
            G[r2] = g1
            with np.errstate(divide='ignore', invalid='ignore'):
                G[r3] = outer_sl - 25.0 * np.log10(np.where(phi[r3] > 0, phi[r3], 1e-9))
            G[r4] = outer_floor

        return G
