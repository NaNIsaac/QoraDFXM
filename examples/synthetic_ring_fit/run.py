"""Synthetic end-to-end fit: a known ellipse and ring -> noisy beamline-layout HDF5 -> qoradfxm fit
and ring -> geometry, fit error and ring radius.

Runs the command line a user runs (``qoradfxm fit`` and ``qoradfxm ring`` through
``qoradfxm.cli.main``) on shots whose answer is known: picked points with a known jitter, and a
ring at a known scale k on a dark level that ``--op sub_bg:/dark`` must remove.

    uv run python examples/synthetic_ring_fit/run.py

Prints the result next to the truth and writes result.json beside this file.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from qoradfxm.cli import main

HERE = Path(__file__).parent
SEED = 2026

_spec = importlib.util.spec_from_file_location(
    "synthetic_ring", HERE.parent / "synthetic_ring.py"
)
synthetic_ring = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(synthetic_ring)

# The ellipse of examples/synthetic_ring.py, in pixels of a 400 x 300 image (x right, y down).
CENTER = synthetic_ring.CENTER  # (cx, cy)
AXES = synthetic_ring.AXES  # semi-major, semi-minor
ANGLE_DEG = synthetic_ring.ANGLE_DEG
FLOOR = 5.0  # counts under the ring, before the dark level
DATASET = synthetic_ring.DATASET_PATH
# Detector: a dark level of 40 counts with Gaussian read noise sigma 3, in the image and in /dark.
DARK_LEVEL, DARK_SIGMA = 40.0, 3.0
# Picking: 200 points on the ellipse with Gaussian jitter of these sizes (px).
N_POINTS = 200
JITTER_PX = [0.0, 0.25, 0.5, 1.0]
RING_K = [1.3, 1.4]  # one shot per ring scale


def write_shot(path: Path, k: float, rng: np.random.Generator) -> Path:
    ring = synthetic_ring.make_ring_image(k=k, floor=FLOOR)
    image = ring + rng.normal(DARK_LEVEL, DARK_SIGMA, ring.shape).astype(np.float32)
    dark = rng.normal(DARK_LEVEL, DARK_SIGMA, ring.shape).astype(np.float32)
    with h5py.File(path, "w") as hf:
        hf.create_dataset(DATASET, data=image[None])
        hf.create_dataset("dark", data=dark[None])
    return path


def write_points(path: Path, jitter: float, rng: np.random.Generator) -> Path:
    pts = np.asarray(synthetic_ring.ellipse_points(N_POINTS))
    pts = pts + rng.normal(0.0, jitter, pts.shape)
    path.write_text(json.dumps(pts.tolist()), encoding="utf-8")
    return path


def cli(*args: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        code = main([str(a) for a in args])
    if code:
        raise RuntimeError(f"qoradfxm {' '.join(map(str, args))} exited with {code}")


def run(seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        shots = {k: write_shot(tmp / f"shot_k{k}.h5", k, rng) for k in RING_K}
        base = ["--dataset", DATASET]

        fits = []
        for jitter in JITTER_PX:
            pts = write_points(tmp / f"pts_{jitter}.json", jitter, rng)
            out = tmp / f"fit_{jitter}.csv"
            cli(
                "fit",
                shots[RING_K[0]],
                *base,
                "--op",
                "sub_bg:/dark",
                "--points",
                pts,
                "--out",
                out,
            )
            row = pd.read_csv(out, encoding="utf-8-sig").iloc[0]
            fits.append(
                {
                    "jitter_px": jitter,
                    **{
                        key: float(row[key])
                        for key in (
                            "center_x",
                            "center_y",
                            "major_axis",
                            "minor_axis",
                            "angle_deg",
                            "fit_error",
                        )
                    },
                }
            )

        exact = write_points(tmp / "pts_exact.json", 0.0, rng)
        rings = {}
        for k, shot in shots.items():
            for subtract in (True, False):
                out = tmp / f"ring_{k}_{subtract}.csv"
                ops = ["--op", "sub_bg:/dark"] if subtract else []
                cli(
                    "ring",
                    shot,
                    *base,
                    *ops,
                    "--points",
                    exact,
                    "--k",
                    "0.5:2.0:0.01",
                    "--out",
                    out,
                )
                profile = pd.read_csv(out, encoding="utf-8-sig")
                inside = profile["k"] < 0.9  # well inside the ring: floor and dark only
                rings[f"k{k}_{'sub' if subtract else 'raw'}"] = {
                    "peak_k": float(profile.loc[profile["mean"].idxmax(), "k"]),
                    "peak_mean": float(profile["mean"].max()),
                    "inside_mean": float(profile.loc[inside, "mean"].mean()),
                }
    return {"seed": seed, "fits": fits, "rings": rings}


if __name__ == "__main__":
    result = run()
    (HERE / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    a, b = AXES
    print(
        f"truth: centre ({CENTER[0]}, {CENTER[1]}), diameters {2 * a} x {2 * b}, {ANGLE_DEG} deg"
    )
    print(
        f"{'jitter':>7s}{'cx':>9s}{'cy':>9s}{'major':>9s}{'minor':>9s}{'angle':>8s}{'error':>8s}{'expected':>9s}"
    )
    for f in result["fits"]:
        expected = f["jitter_px"] * np.sqrt(1 - 5 / N_POINTS)
        print(
            f"{f['jitter_px']:7.2f}{f['center_x']:9.3f}{f['center_y']:9.3f}{f['major_axis']:9.3f}"
            f"{f['minor_axis']:9.3f}{f['angle_deg']:8.3f}{f['fit_error']:8.3f}{expected:9.3f}"
        )
    for name, r in result["rings"].items():
        print(
            f"{name:10s} peak k {r['peak_k']:.2f}  inside mean {r['inside_mean']:.2f}"
        )
