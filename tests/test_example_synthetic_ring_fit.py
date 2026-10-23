"""examples/synthetic_ring_fit end to end: synthetic shot -> qoradfxm fit / ring -> geometry, fit
error, ring radius.

Checks the commands against the drawn ellipse and ring (truth, with tolerances from the point
jitter), today's output as a regression snapshot, and two invariants: the reported fit error grows
with the jitter, and dark subtraction lowers the profile by the dark level without moving the peak.
Units: pixels, degrees, counts.
"""

import importlib.util
import json
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).parents[1] / "examples" / "synthetic_ring_fit"
EXPECTED = json.loads((EXAMPLE / "expected.json").read_text(encoding="utf-8"))
FIT_KEYS = [
    "center_x",
    "center_y",
    "major_axis",
    "minor_axis",
    "angle_deg",
    "fit_error",
]

_spec = importlib.util.spec_from_file_location("synthetic_ring_fit", EXAMPLE / "run.py")
example = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(example)


@pytest.fixture(scope="module")
def result():
    return example.run()


def _check(name: str, got: float, spec: dict):
    assert abs(got - spec["value"]) <= spec["tol"], (
        f"{name}: {got:.6g} vs {spec['value']} ± {spec['tol']}"
    )


def test_truth_is_the_drawn_geometry():
    for fit in EXPECTED["truth"]["fits"]:
        assert fit["center_x"]["value"] == example.CENTER[0]
        assert fit["center_y"]["value"] == example.CENTER[1]
        assert fit["major_axis"]["value"] == 2 * example.AXES[0]
        assert fit["minor_axis"]["value"] == 2 * example.AXES[1]
        assert fit["angle_deg"]["value"] == example.ANGLE_DEG
    assert [f["jitter_px"] for f in EXPECTED["truth"]["fits"]] == example.JITTER_PX


@pytest.mark.parametrize("i", range(len(EXPECTED["truth"]["fits"])))
def test_fit_matches_the_truth(result, i):
    truth = EXPECTED["truth"]["fits"][i]
    got = result["fits"][i]
    for key in FIT_KEYS:
        _check(f"jitter {truth['jitter_px']} {key}", got[key], truth[key])


@pytest.mark.parametrize("name", list(EXPECTED["truth"]["rings"]))
def test_ring_matches_the_truth(result, name):
    for key, spec in EXPECTED["truth"]["rings"][name].items():
        _check(f"{name} {key}", result["rings"][name][key], spec)


def test_fit_error_grows_with_the_jitter(result):
    errors = [f["fit_error"] for f in result["fits"]]
    assert errors == sorted(errors)


def test_dark_subtraction_lowers_the_profile_by_the_dark_level(result):
    for k in example.RING_K:
        sub, raw = result["rings"][f"k{k}_sub"], result["rings"][f"k{k}_raw"]
        assert raw["inside_mean"] - sub["inside_mean"] == pytest.approx(
            example.DARK_LEVEL, abs=0.5
        )
        assert raw["peak_k"] == sub["peak_k"]


@pytest.mark.parametrize("i", range(len(EXPECTED["regression"]["fits"])))
def test_fit_output_is_unchanged(result, i):
    spec = EXPECTED["regression"]["fits"][i]
    for key in FIT_KEYS:
        _check(f"jitter {spec['jitter_px']} {key}", result["fits"][i][key], spec[key])


@pytest.mark.parametrize("name", list(EXPECTED["regression"]["rings"]))
def test_ring_output_is_unchanged(result, name):
    for key, spec in EXPECTED["regression"]["rings"][name].items():
        _check(f"{name} {key}", result["rings"][name][key], spec)
