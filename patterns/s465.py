"""
ITU-R S.465-6 reference earth-station antenna pattern.

Implements the current in-force reference pattern and Note 5 receiving-antenna
phi_min option. Historical pre-1993 Note 4 behavior is intentionally not exposed.
"""
import numpy as np

from .base import AntennaPattern, ParamSpec
from utils.aperture import d_lambda_from_gmax


class S465Pattern(AntennaPattern):
    name = "ITU-R S.465"
    description = "Reference earth-station gain pattern for FSS coordination"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain Estimate', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Used only for estimating D/lambda from peak gain'),
            ParamSpec('aperture_efficiency', 'Aperture Efficiency', 'float', 0.60, 0.05, 1.00, 0.01,
                      tooltip='Used only for estimating D/lambda from peak gain'),
            ParamSpec('d_over_lambda', 'D/lambda', 'float', 100.0, 1.0, 10000.0, 1.0,
                      tooltip='Antenna diameter divided by wavelength',
                      computed=True),
            ParamSpec('use_note5', 'Use Receiving Note 5', 'choice', 'No',
                      choices=['No', 'Yes'],
                      tooltip='For receiving earth-station coordination with D/lambda < 33.3, use phi_min = 2.5 deg'),
        ]

    def suggest_derived(self, name: str, params: dict):
        if name == 'd_over_lambda':
            return round(d_lambda_from_gmax(
                float(params.get('gmax', 30.0)),
                float(params.get('aperture_efficiency', 0.60)),
            ), 3)
        return None

    def is_param_applicable(self, name: str, params: dict) -> bool:
        if name == 'use_note5':
            return float(params.get('d_over_lambda', 100.0)) < 33.3
        return True

    def param_warning(self, name: str, params: dict) -> str:
        d_over_lambda = float(params.get('d_over_lambda', 100.0))
        if name == 'use_note5' and d_over_lambda < 33.3:
            return 'Use only for receiving earth-station coordination cases covered by Note 5.'
        return ''

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        d_over_lambda = float(params['d_over_lambda'])
        use_note5 = params.get('use_note5', 'No') == 'Yes'

        phi_abs = np.abs(phi)
        G = np.full_like(phi_abs, np.nan, dtype=float)

        if use_note5 and d_over_lambda < 33.3:
            phi_min = 2.5
        elif d_over_lambda >= 50.0:
            phi_min = max(1.0, 100.0 / d_over_lambda)
        else:
            phi_min = max(2.0, 114.0 * (d_over_lambda ** -1.09))

        m1 = (phi_abs >= phi_min) & (phi_abs < 48.0)
        m2 = (phi_abs >= 48.0) & (phi_abs <= 180.0)

        with np.errstate(divide='ignore', invalid='ignore'):
            G[m1] = 32.0 - 25.0 * np.log10(phi_abs[m1])
        G[m2] = -10.0

        return G
