#!/usr/bin/env python3
import argparse
import math
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
        raise ValueError('S.672 single-feed supports Ls values of -20, -25, or -30 dB.')
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


def compare_plot(gmax: float, ls: float, psi_b: float, psi0: float, d_over_lambda: float,
                 x_max: float, points: int, output: str, include_legacy: bool = False) -> None:
    x = np.linspace(0.0, x_max, points)
    curves = []

    curves.append((f'S.1528  Gmax={gmax} dBi, Ls={ls} dB', s1528_r13(x, gmax, ls, psi_b=psi_b)))

    if ls in (-20.0, -25.0, -30.0):
        curves.append((f'S.672  Gmax={gmax} dBi, Ls={ls} dB', s672_single_feed(x, gmax, ls, psi0=psi0)))

    if d_over_lambda is not None:
        curves.append((f'S.465  D/λ={d_over_lambda:g}', s465(x, d_over_lambda, legacy_pre1993=False)))
        if d_over_lambda >= 50.0:
            curves.append((f'S.580  D/λ={d_over_lambda:g}', s580(x, d_over_lambda, post_1995=True)))
        if include_legacy:
            curves.append((f'S.465 legacy  D/λ={d_over_lambda:g}', s465(x, d_over_lambda, legacy_pre1993=True)))
            if d_over_lambda >= 50.0:
                curves.append((f'S.580 pre-1995  D/λ={d_over_lambda:g}', s580(x, d_over_lambda, post_1995=False)))

    plt.figure(figsize=(10, 6), dpi=180)
    for label, y in curves:
        plt.plot(x, y, lw=2, label=label)
    plt.grid(True, alpha=0.3)
    plt.xlabel('Off-axis angle (deg)')
    plt.ylabel('Gain (dBi)')
    plt.title('Comparison of ITU antenna patterns for common inputs')
    plt.xlim(0.0, x_max)
    plt.legend(fontsize=8)
    finite = np.concatenate([y[np.isfinite(y)] for _, y in curves if np.isfinite(y).any()])
    if finite.size:
        pad = max(3.0, 0.08 * (float(np.nanmax(finite)) - float(np.nanmin(finite)) + 1.0))
        plt.ylim(float(np.nanmin(finite)) - pad, float(np.nanmax(finite)) + pad)
    plt.tight_layout()
    plt.savefig(output, bbox_inches='tight')
    plt.close()


def main():
    p = argparse.ArgumentParser(description='Compare ITU-R S.1528, S.672, S.465, and S.580 antenna patterns on one plot using common inputs.')
    p.add_argument('--gmax', type=float, default=32.3, help='Peak gain for S.1528 and S.672')
    p.add_argument('--ls', type=float, default=-25.0, help='Ls for S.1528 and S.672; S.672 requires -20, -25, or -30')
    p.add_argument('--psi-b', type=float, default=1.0, help='Half the 3 dB beamwidth for S.1528')
    p.add_argument('--psi0', type=float, default=1.0, help='Reference beamwidth parameter for S.672')
    p.add_argument('--d-over-lambda', type=float, default=100.0, help='D/lambda for S.465 and S.580')
    p.add_argument('--x-max', type=float, default=40.0, help='Maximum off-axis angle to plot in degrees')
    p.add_argument('--points', type=int, default=2001, help='Number of points in the angle grid')
    p.add_argument('--include-legacy', action='store_true', help='Also plot legacy/pre-1993 S.465 and pre-1995 S.580 variants')
    p.add_argument('--output', default='itu_compare.png', help='Output PNG filename')
    args = p.parse_args()

    compare_plot(
        gmax=args.gmax,
        ls=args.ls,
        psi_b=args.psi_b,
        psi0=args.psi0,
        d_over_lambda=args.d_over_lambda,
        x_max=args.x_max,
        points=args.points,
        output=args.output,
        include_legacy=args.include_legacy,
    )


if __name__ == '__main__':
    main()
