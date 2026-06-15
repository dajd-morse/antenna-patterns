import math
import unittest

import numpy as np

from patterns.s1528 import S1528Pattern
from patterns.s672 import S672Pattern
from patterns.s465 import S465Pattern
from patterns.s580 import S580Pattern
from utils.contours import first_descent
from utils.geometry import nadir_angle_from_elevation, max_elevation_angle, EARTH_RADIUS_KM


class PatternFormulaTests(unittest.TestCase):
    def test_s672_current_single_feed_boundaries(self):
        pattern = S672Pattern()
        gm = 32.3
        psi_b = 1.0
        ln = -25.0
        b = 6.32
        y = b * psi_b * 10.0 ** (0.04 * (gm + ln))
        phi = np.array([0.0, 2.58, 0.5 * b, b, y + 0.1, 91.0])

        gain = pattern.gain(phi, {
            'gmax': gm,
            'psi_b': psi_b,
            'z': 1.0,
            'ln': '-25 dB',
        })

        self.assertAlmostEqual(gain[0], gm, places=9)
        self.assertAlmostEqual(gain[1], gm - 3.0 * 2.58 ** 2, places=9)
        self.assertAlmostEqual(gain[2], gm + ln, places=9)
        self.assertAlmostEqual(gain[3], gm + ln, places=9)
        self.assertAlmostEqual(gain[4], 0.0, places=9)
        self.assertAlmostEqual(gain[5], max(15.0 + ln + 0.25 * gm, 0.0), places=9)

    def test_s672_does_not_expose_undefined_minus_30_case(self):
        choices = next(spec.choices for spec in S672Pattern().get_params_spec() if spec.name == 'ln')
        self.assertNotIn('-30 dB', choices)

    def test_s1528_section_12_uses_itu_coefficients(self):
        pattern = S1528Pattern()
        gm = 32.3
        psi_b = 1.0
        ln = -20.0
        b = 6.32
        y = b * psi_b * 10.0 ** (0.04 * (gm + ln))
        phi = np.array([0.0, 2.58, 0.5 * b, b, y + 0.1, 91.0])

        gain = pattern.gain(phi, {
            'model': '1.2 multiple-beam envelope',
            'gmax': gm,
            'd_over_lambda': 35.0,
            'z': 1.0,
            'axis': 'Minor axis',
            'psi_b': psi_b,
            'ln': '-20 dB',
            'ls': -15.0,
            'lf': 0.0,
        })

        self.assertAlmostEqual(gain[0], gm, places=9)
        self.assertAlmostEqual(gain[1], gm - 3.0 * 2.58 ** 1.5, places=9)
        self.assertAlmostEqual(gain[2], gm + ln, places=9)
        self.assertAlmostEqual(gain[3], gm + ln, places=9)
        self.assertAlmostEqual(gain[4], 0.0, places=9)
        self.assertAlmostEqual(gain[5], max(15.0 + ln + 0.25 * gm, 0.0), places=9)

    def test_s1528_psi_b_suggestion_uses_sqrt_1200(self):
        pattern = S1528Pattern()
        d_lambda = pattern.suggest_derived('d_over_lambda', {
            'gmax': 32.3,
            'aperture_efficiency': 0.60,
        })
        minor = pattern.suggest_derived('psi_b', {
            'd_over_lambda': 100.0,
            'z': 2.0,
            'axis': 'Minor axis',
        })
        major = pattern.suggest_derived('psi_b', {
            'd_over_lambda': 100.0,
            'z': 2.0,
            'axis': 'Major axis',
        })

        expected_d_lambda = math.sqrt(10.0 ** (32.3 / 10.0) / 0.60) / math.pi
        self.assertAlmostEqual(d_lambda, round(expected_d_lambda, 3))
        self.assertAlmostEqual(minor, round(math.sqrt(1200.0) / 100.0, 3))
        self.assertAlmostEqual(major, round(2.0 * math.sqrt(1200.0) / 100.0, 3))

    def test_s1528_applicability_tracks_reference_pattern(self):
        pattern = S1528Pattern()
        self.assertTrue(pattern.is_param_applicable('ln', {'model': '1.2 multiple-beam envelope'}))
        self.assertFalse(pattern.is_param_applicable('ls', {'model': '1.2 multiple-beam envelope'}))
        self.assertFalse(pattern.is_param_applicable('ln', {'model': '1.3 D/lambda < 35'}))
        self.assertTrue(pattern.is_param_applicable('ls', {'model': '1.3 D/lambda < 35'}))
        self.assertFalse(pattern.is_param_applicable('ln', {'model': '1.3 LEO'}))
        self.assertFalse(pattern.is_param_applicable('ls', {'model': '1.3 LEO'}))
        self.assertTrue(pattern.param_warning('d_over_lambda', {
            'model': '1.3 D/lambda < 35',
            'd_over_lambda': 35.0,
        }))
        self.assertTrue(pattern.param_warning('z', {
            'model': '1.2 multiple-beam envelope',
            'z': 10.0,
            'ln': '-15 dB',
        }))

    def test_s465_note5_and_no_legacy_mode(self):
        pattern = S465Pattern()
        phi = np.array([2.0, 2.5, 48.0])

        default_gain = pattern.gain(phi, {'d_over_lambda': 30.0, 'use_note5': 'No'})
        note5_gain = pattern.gain(phi, {'d_over_lambda': 30.0, 'use_note5': 'Yes'})

        self.assertTrue(np.isnan(default_gain[0]))
        self.assertTrue(np.isnan(note5_gain[0]))
        self.assertAlmostEqual(note5_gain[1], 32.0 - 25.0 * math.log10(2.5), places=9)
        self.assertAlmostEqual(note5_gain[2], -10.0, places=9)

        spec_names = [spec.name for spec in pattern.get_params_spec()]
        self.assertNotIn('era', spec_names)
        self.assertTrue(pattern.is_param_applicable('use_note5', {'d_over_lambda': 30.0}))
        self.assertFalse(pattern.is_param_applicable('use_note5', {'d_over_lambda': 40.0}))
        self.assertTrue(pattern.param_warning('use_note5', {'d_over_lambda': 30.0}))

    def test_s580_current_only_and_48_degree_boundary(self):
        pattern = S580Pattern()
        phi = np.array([20.0, 21.0, 26.4, 48.0])
        gain = pattern.gain(phi, {'d_over_lambda': 100.0})

        self.assertAlmostEqual(gain[0], 29.0 - 25.0 * math.log10(20.0), places=9)
        self.assertAlmostEqual(gain[1], -3.5, places=9)
        self.assertAlmostEqual(gain[2], 32.0 - 25.0 * math.log10(26.4), places=9)
        self.assertAlmostEqual(gain[3], -10.0, places=9)

        spec_names = [spec.name for spec in pattern.get_params_spec()]
        self.assertNotIn('era', spec_names)

    def test_contour_finder_reports_start_of_plateau(self):
        phi = np.array([0.0, 1.0, 2.0, 3.0])
        gain = np.array([30.0, 10.0, 10.0, 5.0])

        self.assertAlmostEqual(first_descent(phi, gain, 10.0), 1.0)

    def test_minimum_elevation_creates_nonzero_nadir_scan_offset(self):
        self.assertAlmostEqual(nadir_angle_from_elevation(90.0, 500.0), 0.0, places=9)
        self.assertGreater(nadir_angle_from_elevation(10.0, 500.0), 0.0)

    # ----------------------------------------------------- new edge-case tests

    def test_s1528_section_13_leo_main_lobe_continuous_at_Y(self):
        # At Y = 1.5 psi_b the main lobe equals Gm + Ls (Ls = -6.75), so the
        # mask is continuous across the main-lobe / sidelobe boundary.
        pattern = S1528Pattern()
        gm, psi_b = 40.0, 1.0
        y = 1.5 * psi_b
        phi = np.array([y])  # region phi <= Y includes the boundary
        gain = pattern.gain(phi, {
            'model': '1.3 LEO', 'gmax': gm, 'd_over_lambda': 100.0,
            'z': 1.0, 'axis': 'Minor axis', 'psi_b': psi_b, 'lf': 0.0,
        })
        self.assertAlmostEqual(gain[0], gm - 3.0 * 1.5 ** 2, places=6)
        self.assertAlmostEqual(gm - 3.0 * 1.5 ** 2, gm - 6.75, places=9)

    def test_s1528_section_13_meo_uses_fixed_boundary(self):
        pattern = S1528Pattern()
        gm, psi_b = 40.0, 1.0
        y = 2.0 * psi_b  # MEO: Y = 2 psi_b
        gain = pattern.gain(np.array([y]), {
            'model': '1.3 MEO', 'gmax': gm, 'd_over_lambda': 100.0,
            'z': 1.0, 'axis': 'Minor axis', 'psi_b': psi_b, 'lf': 0.0,
        })
        self.assertAlmostEqual(gain[0], gm - 3.0 * 2.0 ** 2, places=6)

    def test_s1528_warns_when_far_out_level_exceeds_near_sidelobe(self):
        # Low Gmax with LF = 0 makes the envelope rise off-axis; must warn.
        pattern = S1528Pattern()
        warning = pattern.param_warning('lf', {
            'model': '1.2 multiple-beam envelope',
            'gmax': 20.0, 'ln': '-25 dB', 'lf': 0.0,
        })
        self.assertTrue(warning)
        # Well-formed case: no warning.
        self.assertFalse(pattern.param_warning('lf', {
            'model': '1.2 multiple-beam envelope',
            'gmax': 40.0, 'ln': '-25 dB', 'lf': 0.0,
        }))

    def test_s672_warns_when_fixed_far_out_level_exceeds_shelf(self):
        pattern = S672Pattern()
        self.assertTrue(pattern.param_warning('gmax', {'gmax': 20.0, 'ln': '-25 dB'}))
        self.assertFalse(pattern.param_warning('gmax', {'gmax': 40.0, 'ln': '-25 dB'}))

    def test_s1528_section_13_warns_on_gm_dlambda_discontinuity(self):
        # Per S.1528 1.3, LEO/MEO masks are continuous at Y only when
        # Gm ~ 20 log10(D/lambda) + 8. A consistent pair must not warn; a
        # wildly inconsistent pair must.
        pattern = S1528Pattern()
        d = 100.0
        gm_consistent = 20.0 * math.log10(d) + 8.0  # ~48 dBi
        self.assertFalse(pattern.param_warning('gmax', {
            'model': '1.3 LEO', 'gmax': gm_consistent, 'd_over_lambda': d,
        }))
        self.assertTrue(pattern.param_warning('gmax', {
            'model': '1.3 LEO', 'gmax': gm_consistent - 10.0, 'd_over_lambda': d,
        }))
        # MEO uses the same continuity relationship.
        self.assertFalse(pattern.param_warning('d_over_lambda', {
            'model': '1.3 MEO', 'gmax': gm_consistent, 'd_over_lambda': d,
        }))

    def test_reference_peak_per_pattern(self):
        # Space patterns report Gmax; earth-station envelopes report None so the
        # plot widget falls back to the actual curve maximum.
        self.assertAlmostEqual(S1528Pattern().reference_peak({'gmax': 33.0}), 33.0)
        self.assertAlmostEqual(S672Pattern().reference_peak({'gmax': 33.0}), 33.0)
        self.assertIsNone(S465Pattern().reference_peak({'gmax': 33.0}))
        self.assertIsNone(S580Pattern().reference_peak({'gmax': 33.0}))

    def test_contour_finder_skips_nan_and_checks_final_sample(self):
        # NaN gaps do not trigger a crossing.
        phi = np.array([0.0, 1.0, 2.0, 3.0])
        gain = np.array([30.0, np.nan, np.nan, 10.0])
        self.assertIsNone(first_descent(phi, gain, 20.0))
        # Equality exactly on the final sample is reported.
        phi2 = np.array([0.0, 1.0, 2.0])
        gain2 = np.array([30.0, 25.0, 20.0])
        self.assertAlmostEqual(first_descent(phi2, gain2, 20.0), 2.0)
        # Target never reached -> None.
        self.assertIsNone(first_descent(phi2, gain2, -5.0))

    def test_nadir_angle_saturates_and_max_elevation(self):
        # arg is clipped to [-1, 1]; a 0 deg elevation must not raise/NaN.
        val = nadir_angle_from_elevation(0.0, 500.0)
        self.assertFalse(math.isnan(val))
        self.assertGreater(val, 0.0)
        # max_elevation_angle matches arccos(R/(R+h)).
        expected = math.degrees(math.acos(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + 500.0)))
        self.assertAlmostEqual(max_elevation_angle(500.0), expected, places=9)


if __name__ == '__main__':
    unittest.main()
