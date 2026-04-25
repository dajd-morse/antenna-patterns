"""Satellite-Earth geometry utilities (spherical Earth)."""
import numpy as np

EARTH_RADIUS_KM = 6371.0


def nadir_angle_from_elevation(elevation_deg: float, orbit_alt_km: float) -> float:
    """
    Nadir angle (degrees) at the satellite subtended to a ground point
    that is seen at the given elevation angle.

    Derivation (law of sines on the Earth-centre–satellite–ground triangle):
        sin(nadir) / R = sin(90° + ε) / (R + h)
        nadir = arcsin( R · cos(ε) / (R + h) )

    Returns the nadir angle in degrees (0° = directly below satellite,
    increasing toward the horizon).
    """
    R = EARTH_RADIUS_KM
    h = orbit_alt_km
    elev_rad = np.radians(elevation_deg)
    arg = R * np.cos(elev_rad) / (R + h)
    arg = np.clip(arg, -1.0, 1.0)
    return float(np.degrees(np.arcsin(arg)))


def max_elevation_angle(orbit_alt_km: float) -> float:
    """Maximum possible Earth central angle for a given altitude."""
    R = EARTH_RADIUS_KM
    h = orbit_alt_km
    return float(np.degrees(np.arccos(R / (R + h))))
