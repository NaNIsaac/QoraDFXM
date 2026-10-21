---
title: 'QoraDFXM: detector-image analysis for dark-field X-ray microscopy with a shared engine, a command line and a desktop app'
tags:
  - Python
  - dark-field X-ray microscopy
  - X-ray diffraction
  - image analysis
  - ellipse fitting
  - HDF5
authors:
  - name: Isaac Yong
    # TODO(Isaac): ORCID, and whether co-authors belong here.
    affiliation: 1
affiliations:
  - name: Sogang University
    index: 1
date: 22 October 2026
bibliography: paper.bib
---

<!--
Draft. Facts come from the repository at the commit this file is committed on. Items marked
TODO need Isaac. Before submitting, check the current JOSS submission requirements against the
repository: length of public history (first commit 2026-07-12), evidence of research use, and the
policy on disclosing AI assistance. Not for submission as it stands.
-->

# Summary

Dark-field X-ray microscopy (DFXM) images the local lattice orientation and strain inside a crystal
by placing an objective lens behind the sample and recording one Bragg reflection on an area
detector [@simons2015]. QoraDFXM is a Python package for one recurring step in analysing such
detector images: measuring ring-shaped features shot by shot. It loads frames from HDF5 or image
files, applies dark subtraction, flat-field division and display transforms, fits an ellipse to
points picked on a ring, and writes the ellipse centre, axes, tilt and fit error for every shot to a
single table. It can also sweep the fitted ellipse outward and report the mean brightness per unit
contour length against the scale factor, which gives a ring profile that can be compared between
shots.

The same engine is reached through a headless command line for batch work and through a PySide6
desktop application for picking points by hand.

# Statement of need

Ring features in detector images are measured by picking points and fitting a conic, repeatedly,
for many shots in a scan. Done by hand in a general image viewer this is slow and not recorded: the
processing applied to each image (background, flat field, log or gamma display scaling, resizing,
rotation) and the points picked are not stored with the result. QoraDFXM keeps the processing as an
ordered, serializable list of operations, stores it with the picked points and the fit in the results
table, and runs the same steps from the command line, so that a result can be reproduced from the
shot file, the operation list and the points.

TODO(Isaac): who the users are and at which beamline or in which experiment the tool was used. The
repository ships no measured data, and a research-impact statement needs a real use (a measurement,
a publication in preparation, or users) that I cannot take from the code.

# State of the field

Ellipse fitting itself is available in general libraries, for example OpenCV [@opencv] and
scikit-image. TODO(Isaac): name the DFXM analysis software in use at the beamlines you know and say
what QoraDFXM adds or does differently; this draft deliberately makes no comparison it cannot
support.

# Software design

The package has three layers with one dependency direction, `core <- cli <- gui`, described in
`docs/ARCHITECTURE.md`.

- `core` is a pure engine with no Qt import. Operations are pure functions in a registry, applied
  through an immutable, JSON-serializable history. Fitting uses the numerically stable direct
  least-squares ellipse method of Halir and Flusser [@halir1998], a reformulation of the
  Fitzgibbon-Pilu-Fisher method [@fitzgibbon1999]. The reported `fit_error` is the root-mean-square
  Sampson distance [@sampson1982] of the picked points from the fitted ellipse.
- `cli` provides `info`, `convert`, `fit`, `ring` and `gui` subcommands and never imports Qt, so a
  beamline or batch machine installs only the engine and the command line.
- `gui` only displays and orchestrates. Batch work started from the app runs the same command line
  as a child process.

Two details of the ring profile matter for correctness. Sampling the ellipse at equal angle steps
over-weights the high-curvature ends of the major axis, so each sample is weighted by its
arc-length element and the weighted mean is the intensity per unit length. And the profile is
measured on linear intensity, because the mean of a logarithm is not the logarithm of the mean; the
command line strips log and gamma operations unless asked to keep them.

# Validation

Tests run on synthetic images only (`tests/`, run in CI). `examples/synthetic_ring.py` writes a
synthetic ring image whose ellipse is known (centre (200, 150), semi-axes 120 and 60, tilt 30
degrees). Fitting eight points on it with `qoradfxm fit` returns a major axis of 240.0016 and a
minor axis of 120.0008 (full diameters, pixels), tilt 29.9987 degrees and fit error 0.0025, and
`qoradfxm ring` finds the profile maximum at k = 1.3, the scale at which the synthetic ring was
placed. This checks the arithmetic, not the behaviour on measured detector images.

TODO(Isaac): add a comparison on approved measured data if permission to publish exists; none is
used here.

# Availability

QoraDFXM is MIT licensed, at <https://github.com/NaNIsaac/QoraDFXM>, requires Python 3.14, and is
not on PyPI yet.

<!-- TODO(Isaac): AI-assistance disclosure section, if the JOSS policy in force requires one. -->

# Acknowledgements

TODO(Isaac): funding and beamline acknowledgements.

# References
