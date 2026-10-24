# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

First version. It loads detector frames from HDF5 or image files, applies dark subtraction,
flat-field division and display transforms, fits an ellipse to points picked on a ring, reports
centre, axes, tilt and fit error per shot as a CSV table, and measures the mean brightness along a
swept ellipse. The steps run from the `qoradfxm` command line or from the PySide6 desktop app.
