"""End-to-end check of the fit and ring commands on a noisy synthetic shot.

Nothing here is measured data. The shot is a Gaussian ring on a known ellipse (centre (200, 150) px,
semi-axes 120 and 60 px, tilt 30 degrees, ring at k = 1.3) on a flat floor of 5 counts, plus a
dark level of 40 counts with Gaussian noise (sigma 3), in the beamline HDF5 layout of
``tests/conftest.py``. The commands run through ``qoradfxm.cli.main`` like a user would, and the
test checks invariants of the physics and of the error report:

* points on the true ellipse give the true centre, diameters and tilt;
* the reported ``fit_error`` (RMS Sampson distance, px) follows the jitter of the picked points:
  for N points and 5 conic parameters it is about ``sigma * sqrt(1 - 5 / N)``, and it grows with
  sigma;
* the fitted centre and axes stay within a few standard errors of the truth;
* ``sub_bg:/dark`` removes the dark level from the ring profile and leaves the peak at k = 1.3;
* a shot whose ring sits at k = 1.4 reports k = 1.4.

Reproduce: ``uv run pytest tests/test_end_to_end.py``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from conftest import (
    DETECTOR_PATH,
    RING_ANGLE_DEG,
    RING_AXES,
    RING_CENTER,
    RING_FLOOR,
    RING_K,
    ellipse_points,
)

from qoradfxm.cli import main

_spec = importlib.util.spec_from_file_location(
    "synthetic_ring",
    Path(__file__).resolve().parents[1] / "examples" / "synthetic_ring.py",
)
synthetic_ring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(synthetic_ring)

DARK_LEVEL = 40.0
DARK_SIGMA = 3.0
N_POINTS = 200


def write_shot(path, *, k: float, seed: int):
    rng = np.random.default_rng(seed)
    ring = synthetic_ring.make_ring_image(k=k)
    shape = ring.shape
    image = ring + rng.normal(DARK_LEVEL, DARK_SIGMA, shape).astype(np.float32)
    dark = rng.normal(DARK_LEVEL, DARK_SIGMA, shape).astype(np.float32)
    with h5py.File(path, "w") as hf:
        hf.create_dataset(DETECTOR_PATH, data=image[None])
        hf.create_dataset("dark", data=dark[None])
    return path


def write_points(path, sigma: float, seed: int):
    pts = np.asarray(ellipse_points(N_POINTS))
    pts = pts + np.random.default_rng(seed).normal(0.0, sigma, pts.shape)
    path.write_text(json.dumps(pts.tolist()), encoding="utf-8")
    return path


def fit(shot, pts, out):
    args = ["fit", str(shot), "--dataset", DETECTOR_PATH, "--op", "sub_bg:/dark"]
    assert main([*args, "--points", str(pts), "--out", str(out)]) == 0
    return pd.read_csv(out, encoding="utf-8-sig").iloc[0]


def ring(shot, pts, out, *, subtract: bool):
    args = ["ring", str(shot), "--dataset", DETECTOR_PATH, "--points", str(pts)]
    args += ["--k", "0.5:2.0:0.01", "--out", str(out)]
    if subtract:
        args += ["--op", "sub_bg:/dark"]
    assert main(args) == 0
    return pd.read_csv(out, encoding="utf-8-sig")


@pytest.fixture
def shot(tmp_path):
    return write_shot(tmp_path / "shot.h5", k=RING_K, seed=1)


def test_exact_points_recover_the_ellipse(shot, tmp_path):
    pts = write_points(tmp_path / "pts.json", 0.0, 0)
    row = fit(shot, pts, tmp_path / "fit.csv")
    assert row["center_x"] == pytest.approx(RING_CENTER[0], abs=1e-6)
    assert row["center_y"] == pytest.approx(RING_CENTER[1], abs=1e-6)
    assert row["major_axis"] == pytest.approx(
        2 * RING_AXES[0], abs=1e-6
    )  # full diameters
    assert row["minor_axis"] == pytest.approx(2 * RING_AXES[1], abs=1e-6)
    assert row["angle_deg"] == pytest.approx(RING_ANGLE_DEG, abs=1e-6)
    assert row["fit_error"] < 1e-6


def test_fit_error_follows_the_point_jitter(shot, tmp_path):
    errors = []
    for sigma in (0.25, 0.5, 1.0):
        pts = write_points(tmp_path / f"pts_{sigma}.json", sigma, seed=7)
        row = fit(shot, pts, tmp_path / f"fit_{sigma}.csv")
        expected = sigma * np.sqrt(1 - 5 / N_POINTS)
        assert row["fit_error"] == pytest.approx(expected, rel=0.15)
        # a few standard errors: the centre error scales as sigma / sqrt(N)
        bound = 5 * sigma / np.sqrt(N_POINTS) * 3
        assert abs(row["center_x"] - RING_CENTER[0]) < bound
        assert abs(row["center_y"] - RING_CENTER[1]) < bound
        assert abs(row["major_axis"] - 2 * RING_AXES[0]) < 2 * bound
        assert abs(row["minor_axis"] - 2 * RING_AXES[1]) < 2 * bound
        errors.append(row["fit_error"])
    assert errors == sorted(errors)


def test_dark_subtraction_cleans_the_ring_profile(shot, tmp_path):
    pts = write_points(tmp_path / "pts.json", 0.0, 0)
    clean = ring(shot, pts, tmp_path / "clean.csv", subtract=True)
    raw = ring(shot, pts, tmp_path / "raw.csv", subtract=False)
    far = clean["k"] < 0.9  # well inside the ring, only floor and dark
    assert clean.loc[far, "mean"].mean() == pytest.approx(RING_FLOOR, abs=1.0)
    assert raw.loc[far, "mean"].mean() == pytest.approx(
        RING_FLOOR + DARK_LEVEL, abs=1.0
    )
    for profile in (clean, raw):
        assert profile.loc[profile["mean"].idxmax(), "k"] == pytest.approx(
            RING_K, abs=0.02
        )


def test_each_shot_reports_its_own_ring_radius(tmp_path):
    pts = write_points(tmp_path / "pts.json", 0.0, 0)
    peaks = []
    for name, k in (("a", 1.3), ("b", 1.4)):
        path = write_shot(tmp_path / f"{name}.h5", k=k, seed=3)
        profile = ring(path, pts, tmp_path / f"{name}.csv", subtract=True)
        peaks.append(profile.loc[profile["mean"].idxmax(), "k"])
    assert peaks == pytest.approx([1.3, 1.4], abs=0.02)
