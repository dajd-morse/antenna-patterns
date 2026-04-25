"""
ITU-R S.1528 — Reference antenna gain pattern for non-GSO FSS space stations.

Gaussian main lobe rolling off into a log-taper sidelobe region, terminating
at a flat far-field floor.

  G(ψ) = Gm − 3·(ψ/ψb)²                   0 ≤ |ψ| ≤ Y
  G(ψ) = (Gm + Ls) − 25·log₁₀(|ψ|/Y)      Y < |ψ| ≤ Z
  G(ψ) = LF                                  |ψ| > Z

Transition angles:
  Y = ψb × sqrt(−Ls / 3)                 [main lobe drops to Ls below peak]
  Z = Y × 10^(0.04 × (Gm + Ls − LF))    [sidelobe rolloff reaches floor LF]

Parameters:
  Gm  — peak gain (dBi)
  ψb  — 3 dB half-beamwidth (deg); Calc button suggests ≈ 32.5 / (D/λ)
  Ls  — near sidelobe level RELATIVE to peak (dB, negative); default −15 dB
  LF  — far-field floor (dBi); default 0 dBi
"""
import numpy as np
from .base import AntennaPattern, ParamSpec


def _dλ(gmax: float, eta: float = 0.6) -> float:
    return np.sqrt(10 ** (gmax / 10) / eta) / np.pi


class S1528Pattern(AntennaPattern):
    name = "ITU-R S.1528"
    description = "Non-GSO FSS space station reference antenna gain pattern"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Maximum gain at boresight'),
            ParamSpec('psi_b', '3 dB Half-Beamwidth (ψb)', 'float', 1.0, 0.001, 90.0, 0.01,
                      units='deg',
                      tooltip='Half-power (3 dB) half-beamwidth. '
                              'Click Calc for an estimate from peak gain (≈ 32.5 / (D/λ)).',
                      computed=True),
            ParamSpec('ls', 'Near Sidelobe Level (Ls)', 'float', -15.0, -60.0, -0.1, 0.5,
                      units='dB re peak',
                      tooltip='Sidelobe level relative to peak gain (must be negative). '
                              'ITU-R S.1528 default: −15 dB'),
            ParamSpec('lf', 'Far-Field Floor (LF)', 'float', 0.0, -30.0, 30.0, 0.5,
                      units='dBi',
                      tooltip='Absolute gain floor beyond the sidelobe region. '
                              'ITU-R S.1528 default: 0 dBi'),
            ParamSpec('mode', 'Antenna Mode', 'choice', 'Transmit',
                      choices=['Transmit', 'Receive'],
                      tooltip='TX/RX label — both use the same piecewise formula'),
        ]

    def suggest_derived(self, name: str, params: dict):
        if name == 'psi_b':
            gmax = params.get('gmax', 30.0)
            return round(32.5 / _dλ(gmax), 3)
        return None

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gm   = params['gmax']
        psi_b = max(float(params['psi_b']), 1e-9)
        ls   = float(params['ls'])    # negative dB relative to peak
        lf   = float(params['lf'])    # absolute floor dBi

        if ls >= 0:
            ls = -0.01  # guard: must be negative

        phi = np.abs(phi)
        G = np.full_like(phi, lf, dtype=float)

        Y = psi_b * np.sqrt(-ls / 3.0)
        Z = Y * 10 ** (0.04 * (gm + ls - lf))

        r1 = phi <= Y
        r2 = (phi > Y) & (phi <= Z)

        G[r1] = gm - 3.0 * (phi[r1] / psi_b) ** 2
        with np.errstate(divide='ignore', invalid='ignore'):
            psi_r2 = np.where(phi[r2] > 0, phi[r2], 1e-30)
            G[r2] = (gm + ls) - 25.0 * np.log10(psi_r2 / Y)

        return G
