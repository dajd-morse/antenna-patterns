"""
ITU-R S.580-6 earth-station antenna design objective near the GSO.

Implements the current in-force S.580-6 objective only. Historical objectives
from superseded revisions are intentionally not exposed.
"""
import numpy as np

from .base import AntennaPattern, ParamSpec
from utils.aperture import d_lambda_from_gmax


_D_LAMBDA_MIN = 50.0


class S580Pattern(AntennaPattern):
    name = "ITU-R S.580"
    station_type = "earth"
    description = "Earth-station design-objective pattern near the GSO"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain Estimate', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Used only for estimating D/lambda from peak gain'),
            ParamSpec('aperture_efficiency', 'Aperture Efficiency', 'float', 0.60, 0.05, 1.00, 0.01,
                      tooltip='Used only for estimating D/lambda from peak gain'),
            # Spinbox minimum is 1, not _D_LAMBDA_MIN: a small antenna's estimated
            # D/lambda (e.g. ~17 for 32.3 dBi) must display honestly rather than
            # being silently clamped up to 50. Values < 50 are flagged as
            # out-of-domain by param_warning() and yield an empty (NaN) curve.
            ParamSpec('d_over_lambda', 'D/lambda', 'float', 100.0, 1.0, 10000.0, 1.0,
                      tooltip='Antenna diameter divided by wavelength; S.580-6 applies only for D/lambda >= 50',
                      computed=True),
        ]

    def suggest_derived(self, name: str, params: dict):
        if name == 'd_over_lambda':
            return round(d_lambda_from_gmax(
                float(params.get('gmax', 30.0)),
                float(params.get('aperture_efficiency', 0.60)),
            ), 3)
        return None

    def param_warning(self, name: str, params: dict) -> str:
        if name == 'd_over_lambda' and float(params.get('d_over_lambda', 100.0)) < _D_LAMBDA_MIN:
            return 'S.580-6 applies only for D/lambda >= 50.'
        return ''

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        d_over_lambda = float(params['d_over_lambda'])
        if d_over_lambda < _D_LAMBDA_MIN:
            return np.full_like(phi, np.nan, dtype=float)

        phi_abs = np.abs(phi)
        G = np.full_like(phi_abs, np.nan, dtype=float)

        phi_min = max(1.0, 100.0 / d_over_lambda)

        m1 = (phi_abs >= phi_min) & (phi_abs <= 20.0)
        m2 = (phi_abs > 20.0) & (phi_abs <= 26.3)
        m3 = (phi_abs > 26.3) & (phi_abs < 48.0)
        m4 = (phi_abs >= 48.0) & (phi_abs <= 180.0)

        with np.errstate(divide='ignore', invalid='ignore'):
            G[m1] = 29.0 - 25.0 * np.log10(phi_abs[m1])
            G[m3] = 32.0 - 25.0 * np.log10(phi_abs[m3])
        G[m2] = -3.5
        G[m4] = -10.0

        return G
