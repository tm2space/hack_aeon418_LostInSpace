"""
basilisk_sim
============

Real 6-DoF spacecraft simulation using AVS Lab's Basilisk Astrodynamics
Framework. Requires Basilisk installed (https://hanspeterschaub.info/basilisk).

Architecture
------------
    SGP4 (sgp4 py package)  --> seed initial r, v in ECI
                |
                v
    spacecraft (Basilisk)   <-- rigid-body dynamics
                |
                +-- reactionWheelStateEffector (4-RW pyramid cluster)
                |
                v
    Attitude tracking pipeline:
        ScheduleAttRefModule (custom: SLERPs the commanded attitude schedule)
            |
            v
        attTrackingError
            |
            v
        mrpFeedback   (body-frame control torque)
            |
            v
        rwMotorTorque (maps body torque -> per-wheel torque)
            |
            v
        reactionWheelStateEffector

Outputs
-------
A Telemetry struct (scorer.Telemetry) with time-series:
    t_s, q_BN, omega_B, H_wheels, r_eci, gmst_rad

Version notes (Basilisk module naming drifts — VERIFY on your install)
---------------------------------------------------------------------
The imports and class names below target Basilisk >= 2.2 (post-module-
renaming).  If your copy is older you may need to swap:

    from Basilisk.simulation import spacecraft            # older: spacecraftPlus
    from Basilisk.simulation import reactionWheelStateEffector  # ok 2.0+
    from Basilisk.fswAlgorithms import mrpFeedback        # older: MRP_Feedback
    from Basilisk.fswAlgorithms import attTrackingError   # older: attTrackingError (same)
    from Basilisk.fswAlgorithms import rwMotorTorque
    from Basilisk.architecture import messaging            # older: sim_model + messaging2

Also note:
  * Messages: `XxxMsgPayload` (modern), `XxxSimMsg` (pre-2020). Methods on
    Message objects: `.write(payload, time, moduleID)`.
  * `simIncludeRW.rwFactory` is the recommended way to build wheel clusters;
    we use it below but inline the pyramid layout so the geometry is explicit.

If anything below breaks due to a module rename, search for 'BSK-VERIFY:'
comments — those mark places you'll need to touch.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from . import geometry as geo
from . import sgp4_utils as s4u
from .config import PassConfig
from .scorer import Telemetry

# -- Basilisk is imported lazily so the package is usable without it --------
_bsk_available: Optional[bool] = None

def basilisk_available() -> bool:
    global _bsk_available
    if _bsk_available is None:
        try:
            import Basilisk  # noqa: F401
            _bsk_available = True
        except ImportError:
            _bsk_available = False
    return _bsk_available


# ============================================================================
# Simulation
# ============================================================================
class BasiliskSim:
    """
    Run one pass in Basilisk with the team's attitude/shutter schedule.

    Usage
    -----
        sim = BasiliskSim(cfg)
        telemetry = sim.run(schedule)          # -> scorer.Telemetry
    """

    def __init__(self, cfg: PassConfig,
                 step_s: float = 0.050,        # integrator step (50 ms default)
                 log_every_n: int = 1):
        if not basilisk_available():
            raise ImportError(
                "Basilisk is not importable. Install from "
                "https://hanspeterschaub.info/basilisk or use mock_sim.run_mock() "
                "for a Basilisk-free dry run."
            )
        self.cfg = cfg
        self.step_s = float(step_s)
        self.log_every_n = int(log_every_n)
        self.T_pass = s4u.pass_duration_s(cfg.pass_start, cfg.pass_end)

    # ------------------------------------------------------------------ public
    def run(self, schedule: Dict[str, Any]) -> Telemetry:
        # Import Basilisk only when run() is called so `import basilisk_harness`
        # works on machines without Basilisk.
        from Basilisk.utilities import SimulationBaseClass, macros, simIncludeRW
        from Basilisk.simulation import spacecraft, reactionWheelStateEffector
        from Basilisk.fswAlgorithms import (
            attTrackingError, mrpFeedback, rwMotorTorque,
        )
        from Basilisk.architecture import messaging

        sim = SimulationBaseClass.SimBaseClass()
        proc = sim.CreateNewProcess("bsk_proc")
        task_name = "bsk_task"
        proc.addTask(sim.CreateNewTask(task_name, macros.sec2nano(self.step_s)))

        # ---------- Spacecraft ----------
        sc = spacecraft.Spacecraft()
        sc.ModelTag = "sc"
        I = self.cfg.sc_params["inertia_kgm2"]
        sc.hub.mHub = 20.0  # kg, placeholder -- not used by the scorer
        sc.hub.IHubPntBc_B = [[I[0][0], I[0][1], I[0][2]],
                              [I[1][0], I[1][1], I[1][2]],
                              [I[2][0], I[2][1], I[2][2]]]
        # SGP4 initial state at t = 0
        prop0 = s4u.Sgp4Propagator(self.cfg.tle1, self.cfg.tle2)
        s0 = prop0.at(s4u.parse_iso_utc(self.cfg.pass_start), rel_t=0.0)
        sc.hub.r_CN_NInit = [[s0.r_eci[0]], [s0.r_eci[1]], [s0.r_eci[2]]]
        sc.hub.v_CN_NInit = [[s0.v_eci[0]], [s0.v_eci[1]], [s0.v_eci[2]]]
        sc.hub.sigma_BNInit  = [[0.0], [0.0], [0.0]]     # identity attitude
        sc.hub.omega_BN_BInit = [[0.0], [0.0], [0.0]]

        sim.AddModelToTask(task_name, sc)

        # ---------- Reaction wheels: 4-RW pyramid ----------
        rwFactory = simIncludeRW.rwFactory()
        # Cant = 45 deg from +Z, azimuths 0/90/180/270.
        c45, s45 = math.cos(math.radians(45)), math.sin(math.radians(45))
        azs = [0.0, 90.0, 180.0, 270.0]
        rw_objs = []
        for az in azs:
            a = math.radians(az)
            g_B = [s45 * math.cos(a), s45 * math.sin(a), c45]
            # BSK-VERIFY: 'Honeywell_HR16' is just a preset; any will do since we
            # override Omega_max and the max torque below via custom args.
            rw = rwFactory.create(
                "Honeywell_HR16",
                g_B,
                maxMomentum=self.cfg.sc_params["wheel_Hmax_Nms"],  # 30 mNms
                Omega=0.0,
            )
            rw_objs.append(rw)
        rwStateEffector = reactionWheelStateEffector.ReactionWheelStateEffector()
        rwStateEffector.ModelTag = "rwCluster"
        rwFactory.addToSpacecraft(sc.ModelTag, rwStateEffector, sc)
        sim.AddModelToTask(task_name, rwStateEffector, 2)

        # ---------- FSW: attitude reference from schedule ----------
        # BSK-VERIFY: we write the reference AttRefMsg directly from Python each
        # step via a Reset/Update pattern. If your Basilisk version disallows
        # Python SysModel subclassing, fall back to pre-computing the reference
        # on a fine grid and using a stored-message playback (example in docs).
        ref_module = _ScheduleAttRefModule(schedule["attitude"],
                                            msg_name="attRefMsg")
        # In modern Basilisk, custom Python SysModels are subclassed from
        # Basilisk.architecture.sysModel.SysModel. We wire it up below.
        sim.AddModelToTask(task_name, ref_module)

        # Attitude tracking error: body attitude vs reference
        attErrorConfig = attTrackingError.attTrackingErrorConfig()
        attErrorWrap   = sim.setModelDataWrap(attErrorConfig)
        attErrorWrap.ModelTag = "attErr"
        sim.AddModelToTask(task_name, attErrorWrap, attErrorConfig)

        # MRP feedback control
        ctrlConfig = mrpFeedback.mrpFeedbackConfig()
        ctrlWrap   = sim.setModelDataWrap(ctrlConfig)
        ctrlWrap.ModelTag = "mrpCtl"
        ctrlConfig.K   = 0.15
        ctrlConfig.Ki  = -1.0   # integral off; harness keeps the plant clean
        ctrlConfig.P   = 0.6
        ctrlConfig.integralLimit = 2.0 / ctrlConfig.P * 0.1
        sim.AddModelToTask(task_name, ctrlWrap, ctrlConfig)

        # Map body torque to wheel torques
        rwMotorConfig = rwMotorTorque.rwMotorTorqueConfig()
        rwMotorWrap   = sim.setModelDataWrap(rwMotorConfig)
        rwMotorWrap.ModelTag = "rwMotor"
        rwMotorConfig.controlAxes_B = [1, 0, 0,
                                        0, 1, 0,
                                        0, 0, 1]
        sim.AddModelToTask(task_name, rwMotorWrap, rwMotorConfig)

        # ---------- Wire messages ----------
        # BSK-VERIFY: message wiring API is `msgInName = msgOutName.addSubscriber()`
        # as of Basilisk >= 2.0.
        attErrorConfig.attNavInMsg.subscribeTo(sc.attOutMsg)
        attErrorConfig.attRefInMsg.subscribeTo(ref_module.attRefOutMsg)

        ctrlConfig.guidInMsg.subscribeTo(attErrorConfig.attGuidOutMsg)
        ctrlConfig.vehConfigInMsg.subscribeTo(_make_veh_config_msg(
            messaging, self.cfg.sc_params["inertia_kgm2"]))
        ctrlConfig.rwParamsInMsg.subscribeTo(rwFactory.getConfigMessage())
        ctrlConfig.rwSpeedsInMsg.subscribeTo(rwStateEffector.rwSpeedOutMsg)

        rwMotorConfig.rwParamsInMsg.subscribeTo(rwFactory.getConfigMessage())
        rwMotorConfig.vehControlInMsg.subscribeTo(ctrlConfig.cmdTorqueOutMsg)

        rwStateEffector.rwMotorCmdInMsg.subscribeTo(rwMotorConfig.rwMotorTorqueOutMsg)

        # ---------- Loggers ----------
        sc_log        = sc.scStateOutMsg.recorder()
        rw_speed_log  = rwStateEffector.rwSpeedOutMsg.recorder()
        sim.AddModelToTask(task_name, sc_log)
        sim.AddModelToTask(task_name, rw_speed_log)

        # ---------- Run ----------
        sim.ConfigureStopTime(macros.sec2nano(self.T_pass))
        sim.InitializeSimulation()
        sim.ExecuteSimulation()

        # ---------- Harvest telemetry ----------
        t_ns    = np.asarray(sc_log.times())
        t_s     = t_ns * 1e-9
        # State message format in modern Basilisk:
        #   sigma_BN (3,), omega_BN_B (3,), r_BN_N (3,), v_BN_N (3,)
        sigma   = np.asarray(sc_log.sigma_BN)       # (N,3)
        omega_B = np.asarray(sc_log.omega_BN_B)     # (N,3)
        r_eci   = np.asarray(sc_log.r_BN_N)         # (N,3)
        # Wheel speeds -> H via I_wheel * Omega (I_w per wheel from the factory)
        rw_omega = np.asarray(rw_speed_log.wheelSpeeds)[:, :4]   # (N,4) rad/s
        I_w = np.array([rw.Js for rw in rw_objs])               # (4,) kg m^2
        H_wheels = rw_omega * I_w[None, :]

        # MRP -> quaternion (scalar-last)
        q_BN = np.array([_mrp_to_quat_xyzw(s) for s in sigma])

        # GMST timeseries (from pass_start epoch)
        t0 = s4u.parse_iso_utc(self.cfg.pass_start)
        gmst = np.array([s4u.gmst_rad(t0 + _td_seconds(t)) for t in t_s])

        return Telemetry(
            t_s=t_s, q_BN=q_BN, omega_B=omega_B, H_wheels=H_wheels,
            r_eci=r_eci, gmst_rad=gmst,
        )


# ============================================================================
# Python-side SysModel that publishes the attitude reference each step.
# ============================================================================
def _make_schedule_ref_module():
    """
    Factory that returns a SysModel subclass publishing an AttRefMsg from the
    commanded schedule. Deferred so `from Basilisk...` only runs at call time.
    """
    from Basilisk.architecture import sysModel, messaging
    from Basilisk.utilities import macros

    class _ScheduleAttRef(sysModel.SysModel):
        def __init__(self, attitude_samples, msg_name="attRefMsg"):
            super().__init__()
            self.ModelTag = msg_name
            self._samples = attitude_samples
            self.attRefOutMsg = messaging.AttRefMsg()

        def Reset(self, currentSimNanos):
            pass

        def UpdateState(self, currentSimNanos):
            t_s = currentSimNanos * 1e-9
            q = geo.sample_attitude(self._samples, t_s)    # [qx,qy,qz,qw]
            sigma = _quat_xyzw_to_mrp(q)
            msg = messaging.AttRefMsgPayload()
            # BSK-VERIFY: AttRefMsgPayload field names in modern Basilisk:
            #   sigma_RN, omega_RN_N, domega_RN_N
            msg.sigma_RN     = [float(sigma[0]), float(sigma[1]), float(sigma[2])]
            msg.omega_RN_N   = [0.0, 0.0, 0.0]     # feed-forward ignored here
            msg.domega_RN_N  = [0.0, 0.0, 0.0]
            self.attRefOutMsg.write(msg, currentSimNanos, self.moduleID)

    return _ScheduleAttRef


def _ScheduleAttRefModule(samples, msg_name="attRefMsg"):
    cls = _make_schedule_ref_module()
    return cls(samples, msg_name=msg_name)


def _make_veh_config_msg(messaging_module, I_kgm2):
    """Build a VehicleConfigMsg carrying the inertia tensor."""
    from Basilisk.architecture import messaging
    msg = messaging.VehicleConfigMsgPayload()
    msg.ISCPntB_B = [I_kgm2[0][0], I_kgm2[0][1], I_kgm2[0][2],
                     I_kgm2[1][0], I_kgm2[1][1], I_kgm2[1][2],
                     I_kgm2[2][0], I_kgm2[2][1], I_kgm2[2][2]]
    out = messaging.VehicleConfigMsg().write(msg)
    return out


# ============================================================================
# MRP <-> Quaternion (scalar-last) helpers
# ============================================================================
def _mrp_to_quat_xyzw(sigma) -> np.ndarray:
    """
    Schaub & Junkins eq. 3.151:
        q_v = 2*sigma/(1+|sigma|^2)
        q_s = (1-|sigma|^2)/(1+|sigma|^2)
    Returns [qx, qy, qz, qw].
    """
    s = np.asarray(sigma, float)
    s2 = float(np.dot(s, s))
    denom = 1.0 + s2
    qv = 2.0 * s / denom
    qw = (1.0 - s2) / denom
    return np.array([qv[0], qv[1], qv[2], qw])


def _quat_xyzw_to_mrp(q) -> np.ndarray:
    """Inverse: q -> sigma = q_v / (1 + q_s). Switches to shadow set if |sigma|>1."""
    q = np.asarray(q, float)
    q = q / max(np.linalg.norm(q), 1e-12)
    sigma = q[:3] / (1.0 + q[3])
    if np.linalg.norm(sigma) > 1.0:
        # shadow MRP set: -q/(1-q_s) after renormalization
        sigma = -q[:3] / (1.0 - q[3])
    return sigma


def _td_seconds(t):
    from datetime import timedelta
    return timedelta(seconds=float(t))
