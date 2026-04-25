"""
ITU-R S.465 — Reference earth station antenna gain pattern for interference assessment.

Takes D/λ as a direct input (not derived from peak gain).
Returns NaN for angles below φ_min (pattern is undefined there).

Modern (post-1993, default):
  φ_min = max(1°, 100/D·λ)           for D/λ ≥ 50
  φ_min = max(2°, 114·(D/λ)^−1.09)  for D/λ < 50

  G(φ) = 32 − 25·log₁₀(φ)    φ_min ≤ φ < 48°
  G(φ) = −10 dBi               φ ≥ 48°

Legacy (pre-1993, Note 4):
  φ_min = max(100/D·λ, 0)
  G(φ) = 52 − 10·log₁₀(D/λ) − 25·log₁₀(φ)    φ_min ≤ φ < 48°
  G(φ) = 10 − 10·log₁₀(D/λ)                    φ ≥ 48°
"""
import math
import numpy as np
from .base import AntennaPattern, ParamSpec


class S465Pattern(AntennaPattern):
    name = "ITU-R S.465"
    description = "Reference earth station gain pattern for interference assessment (FSS)"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('d_over_lambda', 'D/λ', 'float', 100.0, 1.0, 10000.0, 1.0,
                      tooltip='Antenna diameter divided by wavelength'),
            ParamSpec('era', 'Standard Version', 'choice', 'Post-1993 (modern)',
                      choices=['Post-1993 (modern)', 'Pre-1993 (legacy Note 4)'],
                      tooltip='Modern: 32−25log(φ); Legacy: 52−10log(D/λ)−25log(φ)'),
        ]

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        dλ     = float(params['d_over_lambda'])
        legacy = params.get('era', 'Post-1993 (modern)') == 'Pre-1993 (legacy Note 4)'

        phi = np.abs(phi)
        G = np.full_like(phi, np.nan, dtype=float)

        if legacy:
            phi_min = max(100.0 / dλ, 0.0)
            m1 = (phi >= phi_min) & (phi < 48.0)
            m2 = phi >= 48.0
            with np.errstate(divide='ignore', invalid='ignore'):
                G[m1] = 52.0 - 10.0 * math.log10(dλ) - 25.0 * np.log10(
                    np.where(phi[m1] > 0, phi[m1], 1e-30))
            G[m2] = 10.0 - 10.0 * math.log10(dλ)
        else:
            if dλ >= 50.0:
                phi_min = max(1.0, 100.0 / dλ)
            else:
                phi_min = max(2.0, 114.0 * (dλ ** -1.09))
            m1 = (phi >= phi_min) & (phi < 48.0)
            m2 = phi >= 48.0
            with np.errstate(divide='ignore', invalid='ignore'):
                G[m1] = 32.0 - 25.0 * np.log10(
                    np.where(phi[m1] > 0, phi[m1], 1e-30))
            G[m2] = -10.0

        return G
