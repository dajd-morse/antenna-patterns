"""
ITU-R S.1528 — Reference antenna gain pattern for non-GSO FSS space stations.

Pattern structure (D/λ ≥ 100):
  G(φ) = Gmax − 2.5×10⁻³(D/λ · φ)²   0 ≤ |φ| ≤ φm
  G(φ) = Ls                             φm < |φ| ≤ φr
  G(φ) = 32 − 25 log(|φ|)             φr < |φ| ≤ 48°
  G(φ) = −10 dBi                        48° < |φ| ≤ 180°

For D/λ < 100 the outer sidelobe formula changes to 52 − 10 log(D/λ) − 25 log(φ).
φm = (20/Dλ) × sqrt(Gmax − Ls)
φr = 10^((32 − Ls)/25)  for D/λ ≥ 100
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
            ParamSpec('gmax', 'Peak Gain', 'float', 30.0, 0.0, 65.0, 0.5,
                      units='dBi',
                      tooltip='Maximum gain at boresight'),
            ParamSpec('ls', 'Near Sidelobe Level (Ls)', 'float', -15.0, -40.0, 30.0, 0.5,
                      units='dBi',
                      tooltip='Near sidelobe plateau level. ITU-R default: −15 dBi'),
            ParamSpec('mode', 'Antenna Mode', 'choice', 'Transmit',
                      choices=['Transmit', 'Receive'],
                      tooltip='Transmit uses standard outer-sidelobe rolloff; '
                              'Receive uses same formula (Ls default differs)'),
        ]

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gmax = params['gmax']
        ls = params['ls']
        dλ = _dλ(gmax)

        phi = np.abs(phi)
        G = np.full_like(phi, -10.0, dtype=float)

        if gmax <= ls:
            return G  # degenerate case

        phi_m = (20.0 / dλ) * np.sqrt(gmax - ls)

        if dλ >= 100:
            phi_r = 10 ** ((32.0 - ls) / 25.0)
            phi_r = max(phi_r, phi_m)

            r1 = phi <= phi_m
            r2 = (phi > phi_m) & (phi <= phi_r)
            r3 = (phi > phi_r) & (phi <= 48.0)

            G[r1] = gmax - 2.5e-3 * (dλ * phi[r1]) ** 2
            G[r2] = ls
            with np.errstate(divide='ignore', invalid='ignore'):
                G[r3] = 32.0 - 25.0 * np.log10(np.where(phi[r3] > 0, phi[r3], 1e-9))
        else:
            outer_floor = 10.0 - 10.0 * np.log10(dλ)
            outer_sl = 52.0 - 10.0 * np.log10(dλ)
            phi_r = 10 ** ((outer_sl - ls) / 25.0)
            phi_r = max(phi_r, phi_m)

            r1 = phi <= phi_m
            r2 = (phi > phi_m) & (phi <= phi_r)
            r3 = (phi > phi_r) & (phi <= 48.0)
            r4 = phi > 48.0

            G[r1] = gmax - 2.5e-3 * (dλ * phi[r1]) ** 2
            G[r2] = ls
            with np.errstate(divide='ignore', invalid='ignore'):
                G[r3] = outer_sl - 25.0 * np.log10(np.where(phi[r3] > 0, phi[r3], 1e-9))
            G[r4] = outer_floor

        return G
