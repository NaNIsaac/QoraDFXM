"""Inputs that must be refused or flagged, not turned into plausible-looking results."""

from __future__ import annotations

import h5py
import numpy as np
import pytest
import tifffile
from conftest import DETECTOR_PATH, ellipse_points

from qoradfxm.core import fitting, io
from qoradfxm.core.results import FitResult, ResultsFrame, UnknownColumnsWarning


def test_fewer_than_five_points_are_refused():
    with pytest.raises(ValueError, match="at least 5"):
        FitResult.from_points([[0, 0], [1, 0], [0, 1], [1, 1]])


def test_identical_points_are_refused():
    with pytest.raises(ValueError, match="identical"):
        FitResult.from_points([[1.0, 1.0]] * 6)


def test_collinear_points_are_refused():
    # numpy's LinAlgError is a ValueError, which is what the GUI catches
    with pytest.raises(ValueError):
        FitResult.from_points([[i, 2 * i] for i in range(8)])


def test_nan_points_are_refused():
    points = ellipse_points()
    points[0][0] = np.nan
    with pytest.raises(ValueError):
        FitResult.from_points(points)


def test_points_that_are_not_pairs_are_refused():
    with pytest.raises(IndexError):
        FitResult.from_points([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])


def test_points_off_an_ellipse_report_a_larger_error_than_points_on_it():
    on_ellipse = FitResult.from_points(ellipse_points())
    rng = np.random.default_rng(0)
    scattered = np.asarray(ellipse_points()) + rng.normal(0.0, 8.0, (8, 2))
    off_ellipse = FitResult.from_points(scattered)
    assert on_ellipse.fit_error < 1e-6
    assert off_ellipse.fit_error > 100 * on_ellipse.fit_error


def test_a_non_elliptical_conic_is_refused():
    hyperbola = np.array([1.0, 0.0, -1.0, 0.0, 0.0, -1.0])  # x^2 - y^2 = 1
    with pytest.raises(ValueError, match="not an ellipse"):
        fitting.conic_to_geometry(hyperbola)


def test_unreadable_h5_raises_oserror(tmp_path):
    bad = tmp_path / "broken.h5"
    bad.write_bytes(b"not hdf5")
    with pytest.raises(OSError):
        io.list_frames(bad)


def test_h5_without_detector_frames_has_nothing_to_load(tmp_path):
    path = tmp_path / "empty.h5"
    with h5py.File(path, "w") as hf:
        hf.create_dataset("run/scan00001/other", data=np.zeros(3))
    assert io.list_frames(path) == []
    with pytest.raises(ValueError, match="No detector frames"):
        io.load_frame(path)


def test_a_frame_that_is_not_2d_is_refused(tmp_path):
    path = tmp_path / "cube.h5"
    with h5py.File(path, "w") as hf:
        hf.create_dataset(DETECTOR_PATH, data=np.zeros((3, 4, 5)))
    with pytest.raises(ValueError, match="not 2-D"):
        io.load_frame(path)
    with pytest.raises(ValueError, match="not 2-D"):
        io.load_dataset(path, DETECTOR_PATH)


def test_a_missing_dataset_path_raises(ring_h5):
    with pytest.raises(KeyError):
        io.load_dataset(ring_h5, "run/scan00001/det/camera/absent")


def test_unreadable_png_is_refused(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")
    with pytest.raises(ValueError, match="Could not read"):
        io.load_image_file(bad)


def test_a_multi_page_tif_stack_is_not_taken_for_one_image(tmp_path):
    stack = tmp_path / "stack.tif"
    data = np.arange(5 * 40 * 60, dtype=np.float32).reshape(5, 40, 60)
    tifffile.imwrite(stack, data, photometric="minisblack")
    with pytest.raises(ValueError, match="Unsupported image shape"):
        io.load_image_file(stack)


def test_csv_with_no_results_columns_is_refused(tmp_path):
    path = tmp_path / "other.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ResultsFrame.from_csv(str(path))


def test_csv_with_extra_columns_keeps_the_results_and_warns(tmp_path):
    path = tmp_path / "extra.csv"
    path.write_text("shot_id,center_x,note\nA,1.5,hand-picked\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="note"):
        frame = ResultsFrame.from_csv(str(path))
    assert frame.get_cell(0, "shot_id") == "A"
    assert frame.get_cell(0, "center_x") == 1.5
    assert "note" not in frame.df.columns


def test_a_colour_tif_is_still_converted_to_gray(tmp_path):
    path = tmp_path / "rgb.tif"
    tifffile.imwrite(path, np.full((8, 9, 3), 30, dtype=np.uint8), photometric="rgb")
    img = io.load_image_file(path)
    assert img.shape == (8, 9)
    assert float(img[0, 0]) == 30.0


def test_the_extra_column_warning_lists_the_dropped_columns(tmp_path):
    path = tmp_path / "extra.csv"
    path.write_text("shot_id,note,tag\nA,x,y\n", encoding="utf-8")
    with pytest.warns(UnknownColumnsWarning) as record:
        ResultsFrame.from_csv(str(path))
    assert record[0].message.columns == ["note", "tag"]
