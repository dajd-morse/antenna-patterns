"""
ITU-R S.672 — Space station reference antenna gain pattern (single-feed).

Four-region envelope from Annex 1, Figure 1. Ls is restricted to the three
tabulated values: −20, −25, or −30 dB (relative to peak).

  G(ψ) = Gm − 3·(ψ/ψ₀)²              0 < |ψ| ≤ a·ψ₀       (Gaussian main lobe)
  G(ψ) = Gm + Ls                       a·ψ₀ < |ψ| ≤ b·ψ₀    (sidelobe plateau)
  G(ψ) = Gm + Ls + 20 − 25·log₁₀(|ψ|/ψ₀)   b·ψ₀ < |ψ| ≤ ψ₁   (log-taper rolloff)
  G(ψ) = 0 dBi                          |ψ| > ψ₁              (far-field floor)

Coefficients (from ITU-R S.672 Annex 1 Table):
  Ls = −20 dB → a = 2.58, b = 6.32
  Ls = −25 dB → a = 2.88, b = 6.32
  Ls = −30 dB → a = 3.16, b = 6.32

  ψ₁ = b·ψ₀ · 10^(0.04·(Gm + Ls))   [rolloff reaches 0 dBi at ψ₁]

ψ₀ is the 3 dB half-beamwidth (Gaussian drops 3 dB at ψ = ψ₀).
The formula is continuous at a·ψ₀ (Gaussian meets plateau) and at b·ψ₀
(plateau meets log-taper, since 25·log₁₀(b=6.32) ≈ 20 exactly).
"""
import numpy as np
from .base import AntennaPattern, ParamSpec

_LS_TABLE: dict[float, tuple[float, float]] = {
    -20.0: (2.58, 6.32),
    -25.0: (2.88, 6.32),
    -30.0: (3.16, 6.32),
}

_VALID_LS = [-20.0, -25.0, -30.0]


def _dλ(gmax: float, eta: float = 0.6) -> float:
    return np.sqrt(10 ** (gmax / 10) / eta) / np.pi


class S672Pattern(AntennaPattern):
    name = "ITU-R S.672"
    description = "Space station reference antenna gain pattern (single-feed)"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Maximum gain at boresight'),
            ParamSpec('psi0', '3 dB Half-Beamwidth (ψ₀)', 'float', 1.0, 0.001, 90.0, 0.01,
                      units='deg',
                      tooltip='Half-power (3 dB) half-beamwidth. '
                              'Click Calc for an estimate from peak gain (≈ 32.5 / (D/λ)).',
                      computed=True),
            ParamSpec('ls', 'Sidelobe Level (Ls)', 'choice', '-25 dB',
                      choices=['-20 dB', '-25 dB', '-30 dB'],
                      tooltip='Near-sidelobe plateau level relative to peak. '
                              'ITU-R S.672 tabulates coefficients for −20, −25, and −30 dB only.'),
        ]

    def suggest_derived(self, name: str, params: dict):
        if name == 'psi0':
            return round(32.5 / _dλ(params.get('gmax', 30.0)), 3)
        return None

    @staticmethod
    def _ls_value(params: dict) -> float:
        return float(params.get('ls', '-25 dB').replace(' dB', ''))

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gm   = float(params['gmax'])
        psi0 = max(float(params['psi0']), 1e-9)
        ls   = self._ls_value(params)

        if ls not in _LS_TABLE:
            ls = min(_VALID_LS, key=lambda v: abs(v - ls))
        a, b = _LS_TABLE[ls]

        phi = np.abs(phi)
        G = np.full_like(phi, 0.0, dtype=float)   # far-field floor = 0 dBi

        psi1 = b * psi0 * 10 ** (0.04 * (gm + ls))

        r0 = phi == 0
        r1 = (phi > 0)        & (phi <= a * psi0)
        r2 = (phi > a * psi0) & (phi <= b * psi0)
        r3 = (phi > b * psi0) & (phi <= psi1)

        G[r0] = gm
        G[r1] = gm - 3.0 * (phi[r1] / psi0) ** 2
        G[r2] = gm + ls
        with np.errstate(divide='ignore', invalid='ignore'):
            G[r3] = gm + ls + 20.0 - 25.0 * np.log10(
                np.where(phi[r3] > 0, phi[r3] / psi0, 1e-30)
            )

        return G
