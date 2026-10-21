"""Write synthetic example inputs for the README and the notebook.

Nothing here is measured data. Every image is a Gaussian ring on a rotated
ellipse plus a flat dark level, with the same geometry as ``tests/conftest.py``:

    ring.tif   ring image (float32, 400x300), no dark level, no noise
    pts.json   eight [x, y] points on the inner ellipse
    shot.h5    the ring plus a noisy dark level, beamline layout:
                 /run/scan00001/det/camera/data   (1, 300, 400)
                 /dark                            (1, 300, 400)
    shot2.h5   a second shot of the same layout, ring moved out to k = 1.4

Usage::

    python examples/synthetic_ring.py [OUT_DIR]   # default: examples/data
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import h5py
import numpy as np
import tifffile

CENTER = (200.0, 150.0)  # cx, cy
AXES = (120.0, 60.0)  # semi-major a, semi-minor b
ANGLE_DEG = 30.0
RING_K = 1.3
DATASET_PATH = "/run/scan00001/det/camera/data"


def make_ring_image(
    h: int = 300,
    w: int = 400,
    *,
    k: float = RING_K,
    sigma: float = 0.05,
    amp: float = 100.0,
    floor: float = 5.0,
) -> np.ndarray:
    cx, cy = CENTER
    a, b = AXES
    th = np.radians(ANGLE_DEG)
    yy, xx = np.mgrid[0:h, 0:w]
    x = (xx - cx) * np.cos(th) + (yy - cy) * np.sin(th)
    y = -(xx - cx) * np.sin(th) + (yy - cy) * np.cos(th)
    r = np.sqrt((x / a) ** 2 + (y / b) ** 2)  # r == 1 on the fitted ellipse
    ring = amp * np.exp(-((r - k) ** 2) / (2 * sigma**2))
    return (ring + floor).astype(np.float32)


def ellipse_points(n: int = 8) -> list[list[float]]:
    cx, cy = CENTER
    a, b = AXES
    th = np.radians(ANGLE_DEG)
    t = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    return [
        [
            round(cx + a * np.cos(u) * np.cos(th) - b * np.sin(u) * np.sin(th), 2),
            round(cy + a * np.cos(u) * np.sin(th) + b * np.sin(u) * np.cos(th), 2),
        ]
        for u in t
    ]


def write_shot(path: Path, ring: np.ndarray, dark_level: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    dark = (dark_level + rng.normal(0.0, 2.0, ring.shape)).astype(np.float32)
    with h5py.File(path, "w") as hf:
        hf.attrs["synthetic"] = True
        hf.create_dataset(DATASET_PATH, data=(ring + dark)[None])
        hf.create_dataset("/dark", data=dark[None])


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ring = make_ring_image()
    tifffile.imwrite(out_dir / "ring.tif", ring)
    (out_dir / "pts.json").write_text(json.dumps(ellipse_points()), encoding="utf-8")
    write_shot(out_dir / "shot.h5", ring, dark_level=20.0, seed=1)
    write_shot(out_dir / "shot2.h5", make_ring_image(k=1.4), dark_level=25.0, seed=2)
    print(f"wrote synthetic ring.tif, pts.json, shot.h5, shot2.h5 to {out_dir}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "data")
