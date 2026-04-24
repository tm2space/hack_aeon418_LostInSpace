"""
geometry
========

Ground-footprint projection and AOI coverage accumulation.

Pipeline for one shutter window:
    q_BN (body->ECI), r_eci (satellite position in ECI), and FOV half-angles
    |-> boresight direction in ECI    (R_BN @ [0,0,1])
    |-> ray-cast to WGS84 ellipsoid   (quadratic solve)
    |-> nadir hit point + 4 corner rays at (+/-fov_x/2, +/-fov_y/2)
    |-> rotate via GMST to ECEF, convert to lat/lon
    |-> shapely Polygon in an equirectangular local tangent plane (meters)

We use a *local* equirectangular projection centered on the AOI centroid so
polygon union / intersection produce meaningful areas in m^2 without the
full cost of a proper geodesic buffer. The AOI is ~100x100 km at 45N, so
scale distortion across the AOI is < 0.1%.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from . import sgp4_utils as s4u


# ------------------------------------------------------------------- quaternion
def quat_to_rot_BN(q: np.ndarray) -> np.ndarray:
    """
    Body -> Inertial rotation matrix from scalar-last quaternion [qx,qy,qz,qw].

    v_N = R_BN @ v_B     (column-vector convention).
    """
    qx, qy, qz, qw = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    n = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
    if n < 1e-12:
        raise ValueError("zero quaternion")
    qx, qy, qz, qw = qx/n, qy/n, qz/n, qw/n
    # Hamilton convention
    return np.array([
        [1 - 2*(qy*qy + qz*qz),   2*(qx*qy - qz*qw),       2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw),       1 - 2*(qx*qx + qz*qz),   2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw),       2*(qy*qz + qx*qw),       1 - 2*(qx*qx + qy*qy)],
    ])


def slerp(q0: np.ndarray, q1: np.ndarray, u: float) -> np.ndarray:
    """Scalar-last quaternion SLERP. u in [0,1]."""
    q0 = np.asarray(q0, float); q1 = np.asarray(q1, float)
    q0 = q0 / np.linalg.norm(q0)
    q1 = q1 / np.linalg.norm(q1)
    d = float(np.dot(q0, q1))
    if d < 0.0:
        q1 = -q1
        d = -d
    if d > 0.9995:
        q = q0 + u * (q1 - q0)
        return q / np.linalg.norm(q)
    theta_0 = math.acos(max(-1.0, min(1.0, d)))
    theta   = theta_0 * u
    sin_t0 = math.sin(theta_0)
    s0 = math.sin(theta_0 - theta) / sin_t0
    s1 = math.sin(theta) / sin_t0
    return s0 * q0 + s1 * q1


def sample_attitude(attitude: List[dict], t: float) -> np.ndarray:
    """Linear-time SLERP of the attitude schedule at query time t.

    Clamps to endpoints if t is outside [t_first, t_last].
    """
    if t <= attitude[0]["t"]:
        return np.asarray(attitude[0]["q_BN"], float) / np.linalg.norm(attitude[0]["q_BN"])
    if t >= attitude[-1]["t"]:
        return np.asarray(attitude[-1]["q_BN"], float) / np.linalg.norm(attitude[-1]["q_BN"])
    # Linear search is fine: attitude lists are O(1e3) and we call this O(1e2) times.
    for i in range(len(attitude) - 1):
        t0, t1 = attitude[i]["t"], attitude[i+1]["t"]
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            return slerp(np.asarray(attitude[i]["q_BN"], float),
                         np.asarray(attitude[i+1]["q_BN"], float), u)
    # Fallback — should not reach here because of the endpoint guards.
    return np.asarray(attitude[-1]["q_BN"], float)


# ------------------------------------------------------------------- ray cast
def _ray_ellipsoid_intersect(origin: np.ndarray, direction: np.ndarray
                             ) -> Optional[np.ndarray]:
    """
    Intersect a ray (origin + t*dir, t>=0) with the WGS84 ellipsoid.
    Returns the near-side hit (ECEF meters) or None if no hit.
    origin and direction must be expressed in ECEF (or a frame co-rotating
    with the ellipsoid — we handle the ECI->ECEF rotation upstream).
    """
    a = s4u.WGS84_A
    b = s4u.WGS84_B
    # Scale axes so the ellipsoid becomes a unit sphere.
    D = np.array([1/a, 1/a, 1/b])
    o = origin * D
    d = direction * D
    A = float(np.dot(d, d))
    B = 2.0 * float(np.dot(o, d))
    C = float(np.dot(o, o)) - 1.0
    disc = B*B - 4*A*C
    if disc < 0 or A < 1e-18:
        return None
    sq = math.sqrt(disc)
    t1 = (-B - sq) / (2*A)
    t2 = (-B + sq) / (2*A)
    # Pick the smallest non-negative root.
    if t1 >= 0:
        t = t1
    elif t2 >= 0:
        t = t2
    else:
        return None
    hit = origin + t * direction
    return hit


# ------------------------------------------------------------------- footprint
@dataclass
class Footprint:
    """Ground footprint from one shutter window."""
    t_mid: float                       # seconds from pass_start
    nadir_hit_llh: Tuple[float, float] # (lat_deg, lon_deg) of boresight hit
    corners_llh:   List[Tuple[float, float]]  # 4 corners, lat_deg,lon_deg
    off_nadir_deg: float               # angle between boresight & local nadir (deg)


def project_footprint(q_BN: np.ndarray,
                      r_eci:   np.ndarray,
                      gmst:    float,
                      fov_deg: Tuple[float, float],
                      t_mid:   float
                      ) -> Optional[Footprint]:
    """
    Project a single shutter's frame to the ground.

    Parameters
    ----------
    q_BN    : quaternion body->inertial, scalar-last
    r_eci   : satellite position in ECI [m]
    gmst    : Greenwich mean sidereal time [rad] at t_mid
    fov_deg : (cross_track_deg, along_track_deg)
    t_mid   : shutter midpoint time [s since pass_start], stored for debugging

    Returns
    -------
    Footprint, or None if any corner ray misses the Earth.
    """
    # Rotate everything to ECEF so the ellipsoid intersection is clean.
    Rzi = np.array([[ math.cos(-gmst), -math.sin(-gmst), 0.],
                    [ math.sin(-gmst),  math.cos(-gmst), 0.],
                    [ 0.,                0.,             1.]])
    R_BN = quat_to_rot_BN(q_BN)
    r_ecef = Rzi @ r_eci

    # Imager boresight in body +Z -> inertial -> ECEF
    b_B = np.array([0., 0., 1.])
    b_N = R_BN @ b_B
    b_E = Rzi @ b_N
    b_E = b_E / np.linalg.norm(b_E)

    # Imager points OUT of +Z; we want the ray going "down", so the ray must go
    # from r_ecef in direction b_E only if b_E points toward Earth.
    # Construct corner rays: small rotations of body-z by half-FOV angles.
    fx = math.radians(fov_deg[0]) / 2.0  # half-angle cross-track (about body-y)
    fy = math.radians(fov_deg[1]) / 2.0  # half-angle along-track (about body-x)
    # Standard pinhole model: direction = normalize(tan(fx)*x_hat + tan(fy)*y_hat + z_hat)
    tx, ty = math.tan(fx), math.tan(fy)
    corner_dirs_B = [
        np.array([ +tx, +ty, 1.0]),
        np.array([ -tx, +ty, 1.0]),
        np.array([ -tx, -ty, 1.0]),
        np.array([ +tx, -ty, 1.0]),
    ]

    def _ray_hit_llh(d_B: np.ndarray) -> Optional[Tuple[float, float]]:
        d_B = d_B / np.linalg.norm(d_B)
        d_N = R_BN @ d_B
        d_E = Rzi @ d_N
        hit = _ray_ellipsoid_intersect(r_ecef, d_E)
        if hit is None:
            return None
        lat, lon, _ = s4u.ecef_to_llh(hit)
        return (math.degrees(lat), math.degrees(lon))

    nadir_hit = _ray_hit_llh(b_B)
    if nadir_hit is None:
        return None

    corners: List[Tuple[float, float]] = []
    for d in corner_dirs_B:
        c = _ray_hit_llh(d)
        if c is None:
            return None
        corners.append(c)

    # Off-nadir angle: angle between boresight in ECEF and local up at the hit.
    hit_ecef = _ray_ellipsoid_intersect(r_ecef, b_E)
    local_up = hit_ecef / np.linalg.norm(hit_ecef)
    # Boresight points from sat to ground; invert for up comparison.
    cos_off = float(np.dot(-b_E, local_up))
    cos_off = max(-1.0, min(1.0, cos_off))
    off_nadir = math.degrees(math.acos(cos_off))

    return Footprint(
        t_mid=t_mid,
        nadir_hit_llh=nadir_hit,
        corners_llh=corners,
        off_nadir_deg=off_nadir,
    )


# ------------------------------------------------------------------- projection
class LocalTangentProjection:
    """
    Local equirectangular projection centered on a reference point.
    Good enough for AOIs ~100 km across at mid-latitudes.

    x = (lon - lon0) * cos(lat0) * R_E,    y = (lat - lat0) * R_E
    """
    def __init__(self, lat0_deg: float, lon0_deg: float):
        self.lat0 = math.radians(lat0_deg)
        self.lon0 = math.radians(lon0_deg)
        self.cos0 = math.cos(self.lat0)
        self.R    = s4u.WGS84_A

    def to_xy(self, lat_deg: float, lon_deg: float) -> Tuple[float, float]:
        lat = math.radians(lat_deg); lon = math.radians(lon_deg)
        x = (lon - self.lon0) * self.cos0 * self.R
        y = (lat - self.lat0) * self.R
        return x, y


# ------------------------------------------------------------------- coverage
class CoverageAccumulator:
    """
    Accumulates valid image footprints as a shapely MultiPolygon in local meters,
    then reports coverage fraction against the AOI polygon.
    """
    def __init__(self, aoi_polygon_llh: List[Tuple[float, float]]):
        lats = [p[0] for p in aoi_polygon_llh]
        lons = [p[1] for p in aoi_polygon_llh]
        self.proj = LocalTangentProjection(
            lat0_deg=sum(lats) / len(lats),
            lon0_deg=sum(lons) / len(lons),
        )
        self.aoi_xy = Polygon([self.proj.to_xy(lat, lon) for lat, lon in aoi_polygon_llh])
        if not self.aoi_xy.is_valid:
            self.aoi_xy = make_valid(self.aoi_xy)
        self._frames: List[Polygon] = []

    def add_frame(self, footprint: Footprint) -> None:
        xy = [self.proj.to_xy(lat, lon) for lat, lon in footprint.corners_llh]
        poly = Polygon(xy)
        if not poly.is_valid:
            poly = make_valid(poly)
        if poly.is_empty:
            return
        self._frames.append(poly)

    def coverage_fraction(self) -> float:
        if self.aoi_xy.area <= 0:
            return 0.0
        if not self._frames:
            return 0.0
        merged = unary_union(self._frames)
        covered = merged.intersection(self.aoi_xy)
        return float(covered.area / self.aoi_xy.area)

    def covered_area_m2(self) -> float:
        if not self._frames:
            return 0.0
        merged = unary_union(self._frames)
        return float(merged.intersection(self.aoi_xy).area)

    def aoi_area_m2(self) -> float:
        return float(self.aoi_xy.area)
