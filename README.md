<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/qoradfxm/gui/assets/logo_full_on_dark.png">
  <img src="src/qoradfxm/gui/assets/logo_full.png" width="96" align="right" alt="">
</picture>

# QoraDFXM

[![CI](https://github.com/NaNIsaac/QoraDFXM/actions/workflows/ci.yml/badge.svg)](https://github.com/NaNIsaac/QoraDFXM/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Dark-Field X-ray Microscopy detector-image analysis: a pure Python engine with
two front-ends, a headless CLI and a PySide6 desktop app.**

For DFXM beamline users who need to measure ring-shaped features in detector
images shot by shot. QoraDFXM loads frames from HDF5 or image files, applies dark
subtraction, flat-field division and display transforms, fits an ellipse to
points picked on a ring, and collects centre, axes, tilt and fit error for every
shot in one table (CSV). It can also sweep the fitted ellipse outward and report
the mean brightness along it. The same steps run from the command line for batch
work or in a desktop app for picking points by hand.

```bash
qoradfxm fit shot.h5 --dataset /run/scan00001/det/eh1hama_img/data     --op sub_bg:/dark --op log --points pts.json --out results.csv
```

`pts.json` is a list of `[x, y]` pixel coordinates on the ring (at least 5).
Layer layout: [docs/ARCHITECTURE.md](https://github.com/NaNIsaac/QoraDFXM/blob/main/docs/ARCHITECTURE.md).

## Install

Requires Python 3.14. Not on PyPI yet; install from GitHub or a clone:

```bash
pip install "qoradfxm[gui] @ git+https://github.com/NaNIsaac/QoraDFXM"   # desktop app
pip install "git+https://github.com/NaNIsaac/QoraDFXM"                  # headless: engine + CLI, no Qt
```

From a clone with [uv](https://docs.astral.sh/uv/):

```bash
uv sync                     # engine + CLI + GUI (the dev group pulls qoradfxm[gui])
uv sync --no-dev            # engine + CLI only, no Qt
```

`cupy` (GPU) is an opt-in extra: `uv sync --extra cuda`.

## CLI

```bash
qoradfxm info shot.h5 [--tree]                    # frames, shapes, HDF5 structure
qoradfxm convert dat/ -o tif/                     # export detector frames to TIFF
qoradfxm fit shot.h5 \
    --dataset /run/scan00001/det/eh1hama_img/data \
    --op sub_bg:/dark --op divide:flat.tif --op gamma:0.5 --op log \
    --points pts.json --out results.csv
qoradfxm ring shot.h5 --points pts.json \
    --k 0.5:2.0:0.005 --width 3 --out ring.csv --map ring_map.tif
qoradfxm gui shot.h5                              # launch the desktop app
```

`ring` sweeps the fitted ellipse's scale `k` and reports the mean brightness
along its contour (intensity per unit length), with `peak k` / FWHM printed and
the curve written to CSV. The ellipse comes from `--points` or from a Master CSV
(`--from-csv results.csv --shot-id …`). It measures on **linear** intensity —
log/gamma ops are stripped unless you pass `--keep-log`.

Ops apply in the order given:

| op | meaning |
|---|---|
| `sub_bg:SRC` / `divide:SRC` | dark subtract / flat-field divide |
| `log`, `pure_log`, `sqrt`, `gamma:0.5`, `normalize` | intensity transforms |
| `scale:1.5`, `scale:2x0.5` | resize; `sxXsy` changes the aspect ratio |
| `rotate:30` | rotate degrees, + = counter-clockwise (canvas expands) |
| `flip:h` / `flip:v` / `flip:both` | mirror |

`SRC` starting with `/` (and not an image suffix) is a dataset inside the same
HDF5; anything else is a file path. Geometric ops change the image shape — put
them after `sub_bg`/`divide` (a reference of another shape is an error, not a
skip) and before a fit, since points picked earlier no longer line up.
Without `--points`, `fit` only reports the processed image stats.

The desktop app also has its own entry point, `qoradfxm-gui [files...]`.
Module form (no install step): `python -m qoradfxm.cli ...`, `python -m qoradfxm.gui`.

## Python

```python
from qoradfxm.core import QoraDFXMDataset

ds = (QoraDFXMDataset.from_h5("shot.h5", "/run/scan00001/det/eh1hama_img/data")
        .sub_bg(dataset_path="/dark")
        .apply_log()
        .fit_ellipse(points))
row = ds.to_record()   # one Master-table row
```

## Dev

```bash
uv run task gui     # launch the app
uv run task cli     # qoradfxm CLI
uv run task lint    # ruff check + format --check
uv run pytest       # GUI tests run on Qt's offscreen platform
```

## Citation

See [CITATION.cff](CITATION.cff).

## License

MIT, see [LICENSE](LICENSE).
