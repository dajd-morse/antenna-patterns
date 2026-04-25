"""
ITU-R S.580 — Earth station antenna design-objective pattern near the GSO.

Takes D/λ as a direct input. Requires D/λ ≥ 50.
Returns NaN for angles below φ_min (pattern is undefined there).

  φ_min = max(1°, 100/D·λ)

Post-1995 (default):  top = 29 dBi
Pre-1995:             top = 32 dBi  (for D/λ ≤ 150),  29 dBi (for D/λ > 150)

  G(φ) = top − 25·log₁₀(φ)    φ_min ≤ φ ≤ 20°
  G(φ) = −3.5 dBi              20° < φ ≤ 26.3°  (flat bridge)
  G(φ) = 32 − 25·log₁₀(φ)    26.3° < φ ≤ 48°  (bridges to S.465)
  G(φ) = −10 dBi               φ > 48°
"""
import math
import numpy as np
from .base import AntennaPattern, ParamSpec

_D_LAMBDA_MIN = 50.0


class S580Pattern(AntennaPattern):
    name = "ITU-R S.580"
    description = "Earth station antenna design-objective pattern near the GSO (FSS)"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('d_over_lambda', 'D/λ', 'float', 100.0, _D_LAMBDA_MIN, 10000.0, 1.0,
                      tooltip=f'Antenna diameter / wavelength. Must be ≥ {_D_LAMBDA_MIN:.0f}.'),
            ParamSpec('era', 'Standard Version', 'choice', 'Post-1995',
                      choices=['Post-1995', 'Pre-1995'],
                      tooltip='Post-1995: uses 29−25log(φ); '
                              'Pre-1995: uses 32−25log(φ) for D/λ ≤ 150, else 29−25log(φ)'),
        ]

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        dλ        = float(params['d_over_lambda'])
        post_1995 = params.get('era', 'Post-1995') == 'Post-1995'

        if dλ < _D_LAMBDA_MIN:
            return np.full_like(phi, np.nan, dtype=float)

        phi = np.abs(phi)
        G = np.full_like(phi, np.nan, dtype=float)

        phi_min = max(1.0, 100.0 / dλ)
        top = 29.0 if post_1995 else (32.0 if dλ <= 150.0 else 29.0)

        m1 = (phi >= phi_min) & (phi <= 20.0)
        m2 = (phi > 20.0)     & (phi <= 26.3)
        m3 = (phi > 26.3)     & (phi <= 48.0)
        m4 =  phi > 48.0

        with np.errstate(divide='ignore', invalid='ignore'):
            G[m1] = top - 25.0 * np.log10(np.where(phi[m1] > 0, phi[m1], 1e-30))
        G[m2] = -3.5
        with np.errstate(divide='ignore', invalid='ignore'):
            G[m3] = 32.0 - 25.0 * np.log10(np.where(phi[m3] > 0, phi[m3], 1e-30))
        G[m4] = -10.0

        return G
