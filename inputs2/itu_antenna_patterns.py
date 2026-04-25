#!/usr/bin/env python3
import argparse
import math
from typing import Tuple
import numpy as np
import matplotlib.pyplot as plt


def s1528_r13(psi_deg: np.ndarray, gmax: float, ls: float, psi_b: float = 1.0, lf: float = 0.0) -> np.ndarray:
    psi = np.asarray(psi_deg, dtype=float)
    g = np.full_like(psi, np.nan, dtype=float)
    g[psi == 0] = gmax
    y = psi_b * math.sqrt(-ls / 3.0)
    z = y * 10 ** (0.04 * (gmax + ls - lf))
    m1 = (psi > 0) & (psi <= y)
    g[m1] = gmax - 3.0 * (psi[m1] / psi_b) ** 2
    m2 = (psi > y) & (psi <= z)
    g[m2] = gmax + ls - 25.0 * np.log10(psi[m2] / y)
    m3 = psi > z
    g[m3] = lf
    return g


def s672_single_feed(psi_deg: np.ndarray, gmax: float, ls: float, psi0: float = 1.0) -> np.ndarray:
    table = {
        -20.0: (2.58, 6.32),
        -25.0: (2.88, 6.32),
        -30.0: (3.16, 6.32),
    }
    key = float(ls)
    if key not in table:
        raise ValueError('S.672 single-feed supports Ls values of -20, -25, or -30 dB as specified in the Recommendation.')
    a, b = table[key]
    psi = np.asarray(psi_deg, dtype=float)
    g = np.full_like(psi, np.nan, dtype=float)
    g[psi == 0] = gmax
    psi1 = b * psi0 * 10 ** (0.04 * (gmax + ls))
    m1 = (psi > 0) & (psi <= a * psi0)
    g[m1] = gmax - 3.0 * (psi[m1] / psi0) ** 2
    m2 = (psi > a * psi0) & (psi <= b * psi0)
    g[m2] = gmax + ls
    m3 = (psi > b * psi0) & (psi <= psi1)
    g[m3] = gmax + ls + 20.0 - 25.0 * np.log10(psi[m3] / psi0)
    m4 = psi > psi1
    g[m4] = 0.0
    return g


def s465(phi_deg: np.ndarray, d_over_lambda: float, legacy_pre1993: bool = False) -> np.ndarray:
    phi = np.asarray(phi_deg, dtype=float)
    g = np.full_like(phi, np.nan, dtype=float)
    if legacy_pre1993:
        phi_min = max(100.0 / d_over_lambda, 0.0)
        m1 = (phi >= phi_min) & (phi < 48.0)
        g[m1] = 52.0 - 10.0 * math.log10(d_over_lambda) - 25.0 * np.log10(phi[m1])
        m2 = (phi >= 48.0) & (phi <= 180.0)
        g[m2] = 10.0 - 10.0 * math.log10(d_over_lambda)
        return g
    if d_over_lambda >= 50.0:
        phi_min = max(1.0, 100.0 / d_over_lambda)
    else:
        phi_min = max(2.0, 114.0 * (d_over_lambda ** -1.09))
    m1 = (phi >= phi_min) & (phi < 48.0)
    g[m1] = 32.0 - 25.0 * np.log10(phi[m1])
    m2 = (phi >= 48.0) & (phi <= 180.0)
    g[m2] = -10.0
    return g


def s580(phi_deg: np.ndarray, d_over_lambda: float, post_1995: bool = True) -> np.ndarray:
    if d_over_lambda < 50.0:
        raise ValueError('S.580 does not define a design objective for D/lambda < 50.')
    phi = np.asarray(phi_deg, dtype=float)
    g = np.full_like(phi, np.nan, dtype=float)
    phi_min = max(1.0, 100.0 / d_over_lambda)
    top = 29.0 if post_1995 else 32.0 if d_over_lambda <= 150.0 else 29.0
    m1 = (phi >= phi_min) & (phi <= 20.0)
    g[m1] = top - 25.0 * np.log10(phi[m1])
    m2 = (phi > 20.0) & (phi <= 26.3)
    g[m2] = -3.5
    m3 = (phi > 26.3) & (phi <= 48.0)
    g[m3] = 32.0 - 25.0 * np.log10(phi[m3])
    m4 = (phi > 48.0) & (phi <= 180.0)
    g[m4] = -10.0
    return g


def plot_pattern(x, y, title, xlabel, outfile):
    plt.figure(figsize=(9, 5.5), dpi=180)
    plt.plot(x, y, lw=2)
    plt.grid(True, alpha=0.3)
    plt.xlabel(xlabel)
    plt.ylabel('Gain (dBi)')
    plt.title(title)
    plt.xlim(float(np.nanmin(x)), float(np.nanmax(x)))
    finite = y[np.isfinite(y)]
    if finite.size:
        pad = max(3.0, 0.08 * (float(np.nanmax(finite)) - float(np.nanmin(finite)) + 1.0))
        plt.ylim(float(np.nanmin(finite)) - pad, float(np.nanmax(finite)) + pad)
    plt.tight_layout()
    plt.savefig(outfile, bbox_inches='tight')
    plt.close()


def main():
    p = argparse.ArgumentParser(description='Generate ITU antenna reference/design-objective patterns for S.1528, S.672, S.465, and S.580.')
    sub = p.add_subparsers(dest='rec', required=True)

    p1528 = sub.add_parser('s1528', help='ITU-R S.1528 recommend 1.3 pattern')
    p1528.add_argument('--gmax', type=float, required=True)
    p1528.add_argument('--ls', type=float, required=True)
    p1528.add_argument('--psi-b', type=float, default=1.0)
    p1528.add_argument('--lf', type=float, default=0.0)
    p1528.add_argument('--psi-max', type=float, default=40.0)
    p1528.add_argument('--points', type=int, default=2001)
    p1528.add_argument('--output', default='s1528.png')

    p672 = sub.add_parser('s672', help='ITU-R S.672 single-feed circular/elliptical beam pattern from Annex 1 Fig. 1')
    p672.add_argument('--gmax', type=float, required=True)
    p672.add_argument('--ls', type=float, required=True, help='Must be -20, -25, or -30 dB')
    p672.add_argument('--psi0', type=float, default=1.0)
    p672.add_argument('--psi-max', type=float, default=40.0)
    p672.add_argument('--points', type=int, default=2001)
    p672.add_argument('--output', default='s672.png')

    p465 = sub.add_parser('s465', help='ITU-R S.465 reference earth-station pattern')
    p465.add_argument('--d-over-lambda', type=float, required=True)
    p465.add_argument('--legacy-pre1993', action='store_true')
    p465.add_argument('--phi-max', type=float, default=180.0)
    p465.add_argument('--points', type=int, default=4001)
    p465.add_argument('--output', default='s465.png')

    p580 = sub.add_parser('s580', help='ITU-R S.580 earth-station design-objective pattern near the GSO')
    p580.add_argument('--d-over-lambda', type=float, required=True)
    p580.add_argument('--pre-1995', action='store_true', help='Use 32 - 25 log(phi) for 50 <= D/lambda <= 150 instead of post-1995 29 - 25 log(phi) design objective')
    p580.add_argument('--phi-max', type=float, default=180.0)
    p580.add_argument('--points', type=int, default=4001)
    p580.add_argument('--output', default='s580.png')

    args = p.parse_args()

    if args.rec == 's1528':
        x = np.linspace(0.0, args.psi_max, args.points)
        y = s1528_r13(x, args.gmax, args.ls, args.psi_b, args.lf)
        plot_pattern(x, y, f'ITU-R S.1528 pattern: Gmax={args.gmax} dBi, Ls={args.ls} dB', 'Off-axis angle ψ (deg)', args.output)
    elif args.rec == 's672':
        x = np.linspace(0.0, args.psi_max, args.points)
        y = s672_single_feed(x, args.gmax, args.ls, args.psi0)
        plot_pattern(x, y, f'ITU-R S.672 single-feed pattern: Gmax={args.gmax} dBi, Ls={args.ls} dB', 'Off-axis angle ψ (deg)', args.output)
    elif args.rec == 's465':
        x = np.linspace(0.0, args.phi_max, args.points)
        y = s465(x, args.d_over_lambda, args.legacy_pre1993)
        plot_pattern(x, y, f'ITU-R S.465 pattern: D/λ={args.d_over_lambda}', 'Off-axis angle ϕ (deg)', args.output)
    elif args.rec == 's580':
        x = np.linspace(0.0, args.phi_max, args.points)
        y = s580(x, args.d_over_lambda, post_1995=not args.pre_1995)
        label = 'post-1995' if not args.pre_1995 else 'pre-1995'
        plot_pattern(x, y, f'ITU-R S.580 pattern ({label}): D/λ={args.d_over_lambda}', 'Off-axis angle ϕ (deg)', args.output)


if __name__ == '__main__':
    main()
