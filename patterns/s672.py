"""
ITU-R S.672 — Space station reference antenna gain pattern.

Gaussian main lobe + near-sidelobe plateau + far-sidelobe rolloff.
Two standard plateau options: Ls = Gmax − 10 dB  or  Ls = Gmax − 20 dB.

  G(φ) = Gmax − 12(φ/φ₀)²        0 ≤ |φ| ≤ φs
  G(φ) = Ls                        φs < |φ| ≤ φe
  G(φ) = 32 − 25 log(|φ|)        φe < |φ| ≤ 48°
  G(φ) = −10 dBi                   48° < |φ| ≤ 180°

φ₀  = 3 dB half-beamwidth
φs  = φ₀ × sqrt((Gmax − Ls) / 12)     [main lobe → plateau transition]
φe  = 10^((32 − Ls) / 25)              [plateau → 32−25log transition]
"""
import numpy as np
from .base import AntennaPattern, ParamSpec


def _dλ(gmax: float, eta: float = 0.6) -> float:
    return np.sqrt(10 ** (gmax / 10) / eta) / np.pi


def _recommended_beamwidth(gmax: float) -> float:
    """Approximate 3 dB half-beamwidth from peak gain (degrees)."""
    dλ = _dλ(gmax)
    return round(70.0 / dλ, 3)


class S672Pattern(AntennaPattern):
    name = "ITU-R S.672"
    description = "Space station reference antenna gain pattern"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain', 'float', 30.0, 0.0, 65.0, 0.5,
                      units='dBi',
                      tooltip='Maximum gain at boresight'),
            ParamSpec('phi0', '3 dB Half-Beamwidth (φ₀)', 'float', 1.5, 0.01, 90.0, 0.01,
                      units='deg',
                      tooltip='Half-power (3 dB) beamwidth. Click Calc to derive from peak gain.',
                      computed=True),
            ParamSpec('ls_choice', 'Sidelobe Plateau (Ls)', 'choice', '10 dB below peak',
                      choices=['10 dB below peak', '20 dB below peak', 'Custom (absolute)'],
                      tooltip='Level of the near-sidelobe plateau'),
            ParamSpec('ls_custom', 'Custom Ls', 'float', 20.0, -40.0, 40.0, 0.5,
                      units='dBi',
                      tooltip='Absolute Ls value in dBi — used only when "Custom" is selected'),
        ]

    def suggest_derived(self, name: str, params: dict):
        if name == 'phi0':
            return _recommended_beamwidth(params.get('gmax', 30.0))
        return None

    def _ls(self, params: dict) -> float:
        choice = params.get('ls_choice', '10 dB below peak')
        gmax = params['gmax']
        if choice == '10 dB below peak':
            return gmax - 10.0
        if choice == '20 dB below peak':
            return gmax - 20.0
        return params.get('ls_custom', gmax - 10.0)

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gmax = params['gmax']
        phi0 = max(params['phi0'], 1e-6)
        ls = self._ls(params)

        phi = np.abs(phi)
        G = np.full_like(phi, -10.0, dtype=float)

        if gmax <= ls:
            return G

        phi_s = phi0 * np.sqrt((gmax - ls) / 12.0)
        phi_e = 10 ** ((32.0 - ls) / 25.0)
        phi_e = max(phi_e, phi_s)

        r1 = phi <= phi_s
        r2 = (phi > phi_s) & (phi <= phi_e)
        r3 = (phi > phi_e) & (phi <= 48.0)

        G[r1] = gmax - 12.0 * (phi[r1] / phi0) ** 2
        G[r2] = ls
        with np.errstate(divide='ignore', invalid='ignore'):
            G[r3] = 32.0 - 25.0 * np.log10(np.where(phi[r3] > 0, phi[r3], 1e-9))

        return G
