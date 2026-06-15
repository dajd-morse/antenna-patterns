"""
ITU-R S.672-4 single-feed circular/elliptical spacecraft antenna pattern.

Implements the current in-force single-feed design-objective envelope from
recommends 1.  The -30 dB row is not exposed because S.672-4 does not define
numeric a/alpha values for that case.
"""
import math
import numpy as np

from .base import AntennaPattern, ParamSpec
from utils.aperture import d_lambda_from_gmax, psi_b_from_d_lambda


_LN_TABLE: dict[float, tuple[float, float, float]] = {
    -20.0: (1.0, 6.32, 2.0),
    -25.0: (0.8, 6.32, 2.0),
}


class S672Pattern(AntennaPattern):
    name = "ITU-R S.672"
    description = "Space-station single-feed design-objective pattern"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('gmax', 'Peak Gain', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Maximum gain in the main lobe'),
            ParamSpec('d_over_lambda', 'D/lambda', 'float', 100.0, 0.1, 10000.0, 1.0,
                      tooltip='Optional estimate input used by the 3 dB beamwidth Calc button',
                      computed=True),
            ParamSpec('aperture_efficiency', 'Aperture Efficiency', 'float', 0.60, 0.05, 1.00, 0.01,
                      tooltip='Used only for estimating D/lambda from peak gain'),
            ParamSpec('psi_b', '3 dB Half-Beamwidth', 'float', 1.0, 0.001, 90.0, 0.01,
                      units='deg',
                      tooltip='One-half the 3 dB beamwidth in the plane of interest',
                      computed=True),
            ParamSpec('z', 'Beam Axis Ratio z', 'float', 1.0, 1.0, 5.0, 0.01,
                      tooltip='Major-axis/minor-axis ratio for the radiated beam'),
            ParamSpec('ln', 'Near Sidelobe Level LN', 'choice', '-25 dB',
                      choices=['-20 dB', '-25 dB'],
                      tooltip='S.672-4 defines numeric single-feed coefficients for -20 and -25 dB'),
        ]

    @staticmethod
    def _ln_value(params: dict) -> float:
        return float(str(params.get('ln', '-25 dB')).replace(' dB', ''))

    def reference_peak(self, params: dict):
        return float(params.get('gmax', 0.0))

    def suggest_derived(self, name: str, params: dict):
        if name == 'd_over_lambda':
            return round(d_lambda_from_gmax(
                float(params.get('gmax', 30.0)),
                float(params.get('aperture_efficiency', 0.60)),
            ), 3)
        if name == 'psi_b':
            return round(psi_b_from_d_lambda(float(params.get('d_over_lambda', 100.0))), 3)
        return None

    def param_warning(self, name: str, params: dict) -> str:
        if name not in {'z', 'ln', 'gmax'}:
            return ''

        z = max(float(params.get('z', 1.0)), 1.0)
        ln = self._ln_value(params)
        if name in {'z', 'ln'} and ln in _LN_TABLE:
            a_factor, _, _ = _LN_TABLE[ln]
            if 1.0 - a_factor * math.log10(z) < 0.0:
                return 'This z/LN combination makes the S.672 a coefficient undefined.'

        # S.672 fixes the far-out level LF at 0 dBi. For low peak gains the near
        # sidelobe shelf Gm+LN can fall below it, producing a rising envelope.
        gm = float(params.get('gmax', 0.0))
        if 0.0 > gm + ln:
            return ('Far-out level LF (0 dBi) exceeds the near sidelobe shelf '
                    'Gm+LN ({:.1f} dBi); the envelope rises off-axis.'.format(gm + ln))
        return ''

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gm = float(params['gmax'])
        psi_b = max(float(params['psi_b']), 1e-9)
        z = max(float(params.get('z', 1.0)), 1.0)
        ln = self._ln_value(params)

        if ln not in _LN_TABLE:
            ln = min(_LN_TABLE.keys(), key=lambda v: abs(v - ln))

        a_factor, b, alpha = _LN_TABLE[ln]
        log_z = math.log10(z)
        a_arg = 1.0 - a_factor * log_z
        if a_arg < 0.0:
            return np.full_like(phi, np.nan, dtype=float)

        a = 2.58 * math.sqrt(a_arg)
        lf = 0.0
        lb = max(15.0 + ln + 0.25 * gm + 5.0 * log_z, 0.0)
        y = b * psi_b * 10.0 ** (0.04 * (gm + ln - lf))
        x = gm + ln + 25.0 * math.log10(b * psi_b)

        phi_abs = np.abs(phi)
        G = np.full_like(phi_abs, np.nan, dtype=float)

        r0 = phi_abs == 0.0
        r1 = (phi_abs > 0.0) & (phi_abs <= a * psi_b)
        r2a = (phi_abs > a * psi_b) & (phi_abs <= 0.5 * b * psi_b)
        r2b = (phi_abs > 0.5 * b * psi_b) & (phi_abs <= b * psi_b)
        r3 = (phi_abs > b * psi_b) & (phi_abs <= y)
        r4a = (phi_abs > y) & (phi_abs <= 90.0)
        r4b = (phi_abs > 90.0) & (phi_abs <= 180.0)

        G[r0] = gm
        G[r1] = gm - 3.0 * (phi_abs[r1] / psi_b) ** alpha
        G[r2a] = gm + ln + 20.0 * log_z
        G[r2b] = gm + ln
        with np.errstate(divide='ignore', invalid='ignore'):
            G[r3] = x - 25.0 * np.log10(phi_abs[r3])
        G[r4a] = lf
        G[r4b] = lb

        return G
