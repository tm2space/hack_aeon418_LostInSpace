"""Sanity tests for StructuralValidator."""
import math
import sys
import pathlib

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from basilisk_harness.schedule_validator import StructuralValidator


def _iq(): return [0.0, 0.0, 0.0, 1.0]


def test_happy_path():
    v = StructuralValidator(pass_duration_s=120.0)
    sched = {
        "objective": "max_coverage",
        "attitude": [{"t": 0.0, "q_BN": _iq()}, {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [{"t_start": 1.0, "duration": 0.120}],
    }
    r = v.validate(sched)
    assert r.ok, r.errors


def test_missing_key():
    v = StructuralValidator(120.0)
    r = v.validate({"objective": "x", "attitude": []})
    assert not r.ok and any("shutter" in e for e in r.errors)


def test_first_sample_not_zero():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.5, "q_BN": _iq()}, {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [],
    }
    r = v.validate(sched)
    assert not r.ok and any("t=0" in e for e in r.errors)


def test_quat_not_unit():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.0, "q_BN": [1, 1, 1, 1]}, {"t": 1.0, "q_BN": _iq()}],
        "shutter":  [],
    }
    r = v.validate(sched)
    assert not r.ok and any("norm" in e for e in r.errors)


def test_shutter_wrong_duration():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.0, "q_BN": _iq()}, {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [{"t_start": 1.0, "duration": 0.100}],
    }
    r = v.validate(sched)
    assert not r.ok and any("0.12" in e for e in r.errors)


def test_shutter_overlap():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.0, "q_BN": _iq()}, {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [
            {"t_start": 1.0, "duration": 0.120},
            {"t_start": 1.05, "duration": 0.120},
        ],
    }
    r = v.validate(sched)
    assert not r.ok and any("overlap" in e for e in r.errors)


def test_attitude_too_fast():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.0, "q_BN": _iq()},
                      {"t": 0.005, "q_BN": _iq()},
                      {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [],
    }
    r = v.validate(sched)
    assert not r.ok and any("spacing" in e for e in r.errors)


def test_empty_shutter_is_warning_not_error():
    v = StructuralValidator(120.0)
    sched = {
        "objective": "x",
        "attitude": [{"t": 0.0, "q_BN": _iq()}, {"t": 10.0, "q_BN": _iq()}],
        "shutter":  [],
    }
    r = v.validate(sched)
    assert r.ok
    assert any("empty" in w for w in r.warnings)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests)-failed}/{len(tests)} passed")
    sys.exit(failed)
