# QoraDFXM

QoraDFXM measures ring-shaped features in dark-field X-ray microscopy (DFXM) detector images,
shot by shot. It loads frames from HDF5 or image files, applies dark subtraction, flat-field
division and display transforms, fits an ellipse to points picked on a ring, and collects the
centre, axes, tilt and fit error of every shot in one table (CSV). It can also sweep the fitted
ellipse outward and report the mean brightness along it, the ring profile I(k).

One pure-Python engine (`qoradfxm.core`, no Qt) does the work. Two front-ends call it: a
command line for batch work on a beamline machine, and a PySide6 desktop app for picking points
by hand. A preprocessing recipe is data, an ordered list of ops, and `qoradfxm.cli.spec`
translates it to and from the command line's `--op` arguments (`argv_for_dataset` turns a
dataset and its recipe into the equivalent `qoradfxm fit` arguments), so the two front-ends
cannot disagree about what an op means.

![The desktop app on a synthetic ring image: fitted ellipse and the ring profile I(k)](screenshot.png)

## Install

Python 3.14. QoraDFXM is not on PyPI; install it from GitHub with uv:

```sh
uv tool install --python 3.14 "git+https://github.com/NaNIsaac/QoraDFXM"                # engine + CLI, no Qt
uv tool install --python 3.14 "qoradfxm[gui] @ git+https://github.com/NaNIsaac/QoraDFXM"  # with the desktop app
```

The README's [Install](../README.md#install) section has the pip and clone variants.

On a machine where uv has a free-threaded 3.14 installed (`python3.14t`), uv can choose it for
a 3.14 request (seen with `uv sync` in a clone when the free-threaded build was the newer patch
release), and OpenCV then fails to build because it has no free-threaded wheel. Ask for the
regular build by its patch release instead, for example `--python 3.14.5`; `uv python list`
shows what is installed.

## First run

`examples/synthetic_ring.py` writes a synthetic ring image and a beamline-style HDF5 file with a
dark frame, plus `pts.json`, eight points picked on the inner ellipse (centre 200, 150; semi-axes
120 and 60 px; 30 degrees). No measured data ships with the repository.

```sh
git clone https://github.com/NaNIsaac/QoraDFXM
cd QoraDFXM
uv sync --no-dev
uv run python examples/synthetic_ring.py
cd examples/data
uv run qoradfxm info shot.h5 --tree
uv run qoradfxm fit shot.h5 --dataset /run/scan00001/det/camera/data --points pts.json --out results.csv
uv run qoradfxm ring shot.h5 --dataset /run/scan00001/det/camera/data --op sub_bg:/dark \
    --points pts.json --k 0.5:2.0:0.005 --width 3 --out ring.csv
```

`info --tree` lists the frames and the HDF5 layout:

```
shot.h5: 1 frame(s)
  scan00001 / camera  (300, 400)  ->  /run/scan00001/det/camera/data
...
  dark  (1, 300, 400) float32
```

`fit` writes one row to `results.csv` with `center_x` 200.0, `center_y` 150.0, `major_axis`
240.0, `minor_axis` 120.0 (full diameters, not semi-axes), `angle_deg` 30.0 and `fit_error`
0.0025 px. The fit uses only the picked points; preprocessing matters to it only when a
geometric op (`scale`, `rotate`, `flip`) moves the pixels the points refer to.

`ring` prints the peak of the ring profile:

```
peak     : k=1.3000 (a·k=156.00 px)  I=100.833  FWHM=0.1230 k
```

The synthetic ring sits at 1.3 times the fitted ellipse, so the peak is at k = 1.3. Without
`--op sub_bg:/dark` the peak is at the same k but reads I = 120.866: the 20-count dark level of
the file is still in it. The profile is always measured on linear intensity; `log`, `sqrt` and
`gamma` ops are dropped for it unless `--keep-log` is given.

In Git Bash on Windows, set `MSYS_NO_PATHCONV=1` first: otherwise an HDF5 path such as
`/run/scan00001/...` is rewritten into a Windows file path and `--dataset` fails with
`component not found`. PowerShell and cmd leave it alone.

To open the same file in the desktop app (needs the `gui` extra, or `uv sync` without
`--no-dev` in a clone): `qoradfxm gui shot.h5`.

## Where to go next

The README is the full user guide:

- [CLI](../README.md#cli): every subcommand, the `--op` grammar, and what each column of `results.csv` means.
- [Python](../README.md#python): the same steps through `QoraDFXMDataset`.
- [Validation](../README.md#validation): the synthetic test with known truth, and how its tolerance was set.

On this site:

- [Architecture](ARCHITECTURE.md): the engine, CLI and GUI layers, why the GUI runs batch work through the CLI, the immutable dataset and its recipe, which state lives where, and how the ring profile is measured.
- The Python API page lists the public functions and classes of the `qoradfxm` package with their docstrings.
