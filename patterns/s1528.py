"""
ITU-R S.1528-0 reference patterns for non-GSO FSS space-station antennas.

This module exposes the current recommendation's reference-pattern variants:
section 1.2 multiple-beam envelope, and section 1.3 simplified D/lambda, LEO,
and MEO masks.  Measured patterns and the section 1.4 Taylor fitting model are
not represented by this point-and-click generator.
"""
import math
import numpy as np

from .base import AntennaPattern, ParamSpec
from utils.aperture import d_lambda_from_gmax, psi_b_from_d_lambda


_SECTION_12 = '1.2 multiple-beam envelope'
_SECTION_13_DLT35 = '1.3 D/lambda < 35'
_SECTION_13_LEO = '1.3 LEO'
_SECTION_13_MEO = '1.3 MEO'

_LN_TABLE: dict[float, tuple[float, float, float]] = {
    -15.0: (1.4, 6.32, 1.5),
    -20.0: (1.0, 6.32, 1.5),
    -25.0: (0.6, 6.32, 1.5),
    -30.0: (0.4, 6.32, 1.5),
}


def _psi_b_from_d_lambda(d_over_lambda: float, z: float, axis: str) -> float:
    psi_b = psi_b_from_d_lambda(d_over_lambda)
    if axis == 'Major axis':
        psi_b *= max(z, 1.0)
    return psi_b


class S1528Pattern(AntennaPattern):
    name = "ITU-R S.1528"
    description = "Non-GSO FSS space-station reference antenna patterns"

    def get_params_spec(self) -> list[ParamSpec]:
        return [
            ParamSpec('model', 'Reference Pattern', 'choice', _SECTION_12,
                      choices=[_SECTION_12, _SECTION_13_DLT35, _SECTION_13_LEO, _SECTION_13_MEO],
                      tooltip='Current S.1528-0 reference pattern section to plot'),
            ParamSpec('gmax', 'Peak Gain', 'float', 32.3, 0.0, 65.0, 0.1,
                      units='dBi',
                      tooltip='Maximum gain in the main lobe'),
            ParamSpec('d_over_lambda', 'D/lambda', 'float', 35.0, 0.1, 10000.0, 1.0,
                      tooltip='Antenna diameter divided by wavelength at the lower band edge',
                      computed=True),
            ParamSpec('aperture_efficiency', 'Aperture Efficiency', 'float', 0.60, 0.05, 1.00, 0.01,
                      tooltip='Used only for estimating D/lambda from peak gain'),
            ParamSpec('z', 'Beam Axis Ratio z', 'float', 1.0, 1.0, 5.0, 0.01,
                      tooltip='Major-axis/minor-axis ratio for the radiated beam'),
            ParamSpec('axis', 'Pattern Plane', 'choice', 'Minor axis',
                      choices=['Minor axis', 'Major axis'],
                      tooltip='Plane used for the ITU psi_b estimate'),
            ParamSpec('psi_b', '3 dB Half-Beamwidth', 'float', 1.0, 0.001, 90.0, 0.01,
                      units='deg',
                      tooltip='One-half the 3 dB beamwidth. Use measured/known values when available.',
                      computed=True),
            ParamSpec('ln', 'Near Sidelobe Level LN', 'choice', '-25 dB',
                      choices=['-15 dB', '-20 dB', '-25 dB', '-30 dB'],
                      tooltip='Section 1.2 near-in sidelobe level relative to peak'),
            ParamSpec('ls', 'Section 1.3 Ls', 'float', -15.0, -60.0, -3.0, 0.5,
                      units='dB re peak',
                      tooltip='Used only by the section 1.3 D/lambda < 35 pattern'),
            ParamSpec('lf', 'Far-Out Sidelobe Level LF', 'float', 0.0, -30.0, 30.0, 0.5,
                      units='dBi',
                      tooltip='Far-out sidelobe level; S.1528 uses about 0 dBi for ideal patterns'),
        ]

    def reference_peak(self, params: dict):
        return float(params.get('gmax', 0.0))

    def suggest_derived(self, name: str, params: dict):
        if name == 'd_over_lambda':
            return round(d_lambda_from_gmax(
                float(params.get('gmax', 30.0)),
                float(params.get('aperture_efficiency', 0.60)),
            ), 3)
        if name == 'psi_b':
            return round(_psi_b_from_d_lambda(
                float(params.get('d_over_lambda', 35.0)),
                float(params.get('z', 1.0)),
                str(params.get('axis', 'Minor axis')),
            ), 3)
        return None

    def is_param_applicable(self, name: str, params: dict) -> bool:
        model = params.get('model', _SECTION_12)
        if name == 'ln':
            return model == _SECTION_12
        if name == 'ls':
            return model == _SECTION_13_DLT35
        return True

    def param_warning(self, name: str, params: dict) -> str:
        model = params.get('model', _SECTION_12)
        d_over_lambda = float(params.get('d_over_lambda', 35.0))
        z = max(float(params.get('z', 1.0)), 1.0)

        if name == 'd_over_lambda' and model == _SECTION_13_DLT35 and d_over_lambda >= 35.0:
            return 'Section 1.3 D/lambda < 35 is outside its stated domain.'

        if name in {'z', 'ln'} and model == _SECTION_12:
            ln = self._level_value(params, 'ln', '-25 dB')
            if ln in _LN_TABLE:
                a_factor, _, _ = _LN_TABLE[ln]
                if 1.0 - a_factor * math.log10(z) < 0.0:
                    return 'This z/LN combination makes the S.1528 a coefficient undefined.'

        if name in {'lf', 'gmax', 'ln'} and model == _SECTION_12:
            gm = float(params.get('gmax', 0.0))
            ln = self._level_value(params, 'ln', '-25 dB')
            lf = float(params.get('lf', 0.0))
            if lf > gm + ln:
                return ('Far-out level LF ({:.1f} dBi) exceeds the near sidelobe '
                        'shelf Gm+LN ({:.1f} dBi); the envelope rises off-axis.'
                        .format(lf, gm + ln))

        # In S.1528 1.3 the LEO/MEO sidelobe floor is set by 20 log10(D/lambda)
        # while the main lobe uses Gm. The mask is continuous at Y only when
        # Gm ~ 20 log10(D/lambda) + 8; flag a large step so the user can check
        # whether their Gm and D/lambda are consistent.
        if name in {'gmax', 'd_over_lambda'} and model in (_SECTION_13_LEO, _SECTION_13_MEO):
            gap = self._section_13_edge_step(params, model)
            if abs(gap) > 2.0:
                return ('Gm and D/lambda imply a {:+.1f} dB step at the main-lobe '
                        'edge (mask is continuous when Gm ~ 20 log10(D/lambda) + 8). '
                        'Expected for scanned beams, but verify if unintended.'
                        .format(gap))

        return ''

    @staticmethod
    def _section_13_edge_step(params: dict, model: str) -> float:
        """Main-lobe(Y) minus sidelobe(Y) for the 1.3 LEO/MEO masks (dB)."""
        gm = float(params.get('gmax', 0.0))
        d = max(float(params.get('d_over_lambda', 35.0)), 1e-9)
        if model == _SECTION_13_LEO:  # Ls = -6.75, Y = 1.5 psi_b
            main_at_y = gm - 6.75
            side_at_y = 20.0 * math.log10(d) + 5.65 - 25.0 * math.log10(1.5)
        else:                          # MEO: Ls = -12, Y = 2 psi_b
            main_at_y = gm - 12.0
            side_at_y = 20.0 * math.log10(d) + 3.5 - 25.0 * math.log10(2.0)
        return main_at_y - side_at_y

    @staticmethod
    def _level_value(params: dict, key: str, default: str) -> float:
        return float(str(params.get(key, default)).replace(' dB', ''))

    def gain(self, phi: np.ndarray, params: dict) -> np.ndarray:
        model = params.get('model', _SECTION_12)
        if model == _SECTION_12:
            return self._gain_section_12(phi, params)
        return self._gain_section_13(phi, params)

    def _gain_section_12(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gm = float(params['gmax'])
        psi_b = max(float(params['psi_b']), 1e-9)
        d_over_lambda = float(params.get('d_over_lambda', 35.0))
        z = max(float(params.get('z', 1.0)), 1.0)
        ln = self._level_value(params, 'ln', '-25 dB')
        lf = float(params.get('lf', 0.0))

        if ln not in _LN_TABLE:
            ln = min(_LN_TABLE.keys(), key=lambda v: abs(v - ln))

        a_factor, b, alpha = _LN_TABLE[ln]
        log_z = math.log10(z)
        a_arg = 1.0 - a_factor * log_z
        if a_arg < 0.0 or d_over_lambda <= 0.0:
            return np.full_like(phi, np.nan, dtype=float)

        a = 2.58 * math.sqrt(a_arg)
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

    def _gain_section_13(self, phi: np.ndarray, params: dict) -> np.ndarray:
        gm = float(params['gmax'])
        psi_b = max(float(params['psi_b']), 1e-9)
        d_over_lambda = max(float(params.get('d_over_lambda', 35.0)), 1e-9)
        lf = float(params.get('lf', 0.0))
        model = params.get('model', _SECTION_13_DLT35)

        if model == _SECTION_13_LEO:
            ls = -6.75
            y = 1.5 * psi_b
            log_region = lambda psi: 20.0 * math.log10(d_over_lambda) + 5.65 - 25.0 * np.log10(psi / psi_b)
        elif model == _SECTION_13_MEO:
            ls = -12.0
            y = 2.0 * psi_b
            log_region = lambda psi: 20.0 * math.log10(d_over_lambda) + 3.5 - 25.0 * np.log10(psi / psi_b)
        else:
            if d_over_lambda >= 35.0:
                return np.full_like(phi, np.nan, dtype=float)
            ls = float(params.get('ls', -15.0))
            if ls >= 0.0:
                ls = -0.01
            y = psi_b * math.sqrt(-ls / 3.0)
            log_region = lambda psi: gm + ls - 25.0 * np.log10(psi / y)

        phi_far = y * 10.0 ** (0.04 * (gm + ls - lf))

        phi_abs = np.abs(phi)
        G = np.full_like(phi_abs, lf, dtype=float)
        r1 = phi_abs <= y
        r2 = (phi_abs > y) & (phi_abs <= phi_far)

        G[r1] = gm - 3.0 * (phi_abs[r1] / psi_b) ** 2
        with np.errstate(divide='ignore', invalid='ignore'):
            G[r2] = log_region(phi_abs[r2])

        return G
