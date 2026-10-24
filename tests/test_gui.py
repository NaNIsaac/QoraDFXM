"""Head-less GUI behaviour — the wiring that keeps burning us, pinned down.

Every test here drives the real MainWindow on the offscreen platform with
synthetic files, so none of it depends on beamline data being present.
"""

from __future__ import annotations

import numpy as np
import pytest
import tifffile
from conftest import ellipse_points, make_ring_image

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture
def three_tifs(tmp_path):
    """Three distinguishable images in one folder."""
    paths = []
    for i in range(3):
        p = tmp_path / f"shot_{i:02d}.tif"
        tifffile.imwrite(p, (make_ring_image() * (i + 1)).astype(np.float32))
        paths.append(p)
    return paths


def kinds(doc) -> list[str]:
    return [op.kind for op in doc.ds.history]


# ---------------------------------------------------------------- branding
def test_logo_assets_ship_with_the_package():
    from qoradfxm.gui.icons import LOGO_FULL_PATH, LOGO_MARK_PATH

    assert LOGO_MARK_PATH.exists() and LOGO_FULL_PATH.exists()
    # inside the package, so an installed wheel still finds them
    assert LOGO_MARK_PATH.parent.parent.name == "gui"


def test_window_icon_uses_the_artwork_not_the_fallback(main_window):
    assert not main_window.windowIcon().isNull()
    assert main_window.windowIcon().availableSizes(), "a raster logo was expected"


def test_mark_stays_square_at_icon_sizes(qapp):
    from qoradfxm.gui.icons import logo_pixmap

    for size in (16, 22, 64):
        pm = logo_pixmap(size)
        assert (pm.width(), pm.height()) == (size, size)


def test_wordmark_keeps_its_aspect(qapp):
    from qoradfxm.gui.icons import wordmark_pixmap

    pm = wordmark_pixmap(64)
    assert pm.height() == 64
    assert pm.width() < pm.height() * 4  # the lockup is portrait-ish, not a banner


def test_wordmark_has_a_readable_variant_per_theme(qapp):
    """The navy wordmark disappears on a dark panel, so a light twin exists."""
    from PySide6 import QtGui

    from qoradfxm.gui.icons import wordmark_pixmap

    def mean_lightness(pm):
        img = pm.toImage().convertToFormat(QtGui.QImage.Format.Format_ARGB32)
        rows = img.height() * 3 // 4  # the text sits under the badge
        vals = [
            img.pixelColor(x, y).lightness()
            for y in range(rows, img.height())
            for x in range(0, img.width(), 4)
            if img.pixelColor(x, y).alpha() > 128
        ]
        return sum(vals) / max(1, len(vals))

    assert mean_lightness(wordmark_pixmap(160, on_dark=True)) > mean_lightness(
        wordmark_pixmap(160, on_dark=False)
    )


def test_quick_access_bar_is_actually_attached(main_window):
    """It was built and never installed, so the brand mark had nowhere to show."""
    from PySide6 import QtCore, QtWidgets

    ribbon = main_window.menuWidget()
    assert isinstance(ribbon, QtWidgets.QTabWidget)
    corner = ribbon.cornerWidget(QtCore.Qt.TopLeftCorner)
    assert corner is not None and corner.isVisible()
    marks = [
        lbl
        for lbl in corner.findChildren(QtWidgets.QLabel)
        if not lbl.pixmap().isNull()
    ]
    assert marks, "the brand mark should live in the quick-access bar"


# ----------------------------------------------------------- open / tabs
def test_opening_an_image_creates_a_document(main_window, ring_tif):
    main_window.open_path(ring_tif)
    doc = main_window._cur()
    assert doc.file_path == ring_tif
    assert doc.view.has_image()


def test_preview_tab_is_replaced_not_stacked(main_window, three_tifs):
    a, b, _ = three_tifs
    main_window._open_document(a, preview=True)
    tabs_after_first = main_window._tabs.count()
    main_window._open_document(b, preview=True)
    assert main_window._tabs.count() == tabs_after_first
    assert main_window._cur().file_path == b


def test_pinned_tab_survives_the_next_preview(main_window, three_tifs):
    a, b, _ = three_tifs
    main_window._open_document(a, preview=False)
    main_window._open_document(b, preview=True)
    assert main_window._tabs.count() == 2


# ------------------------------------------------- log across documents
def test_log_applies_to_documents_opened_later(main_window, three_tifs):
    """Regression: the checkbox said Log while a new image stayed linear."""
    a, b = three_tifs[0], three_tifs[1]
    main_window._open_document(a, preview=False)
    main_window._log_chk.setChecked(True)
    assert "log" in kinds(main_window._cur())

    main_window._open_document(b, preview=False)
    doc_b = main_window._cur()
    assert "log" in kinds(doc_b)
    assert main_window._log_chk.isChecked()
    assert doc_b.ds.image.max() == pytest.approx(1.0)


def test_turning_log_off_stops_applying_it(main_window, three_tifs):
    a, b = three_tifs[0], three_tifs[1]
    main_window._open_document(a, preview=False)
    main_window._log_chk.setChecked(True)
    main_window._log_chk.setChecked(False)
    main_window._open_document(b, preview=False)
    assert kinds(main_window._cur()) == []


def test_checkbox_follows_the_document_it_belongs_to(main_window, three_tifs):
    a, b = three_tifs[0], three_tifs[1]
    main_window._open_document(a, preview=False)
    main_window._log_chk.setChecked(True)  # a: log on
    main_window._open_document(b, preview=False)
    main_window._log_chk.setChecked(False)  # b: log off
    main_window._tabs.setCurrentIndex(
        main_window._tabs.indexOf(
            main_window._docs
            and next(w for w, d in main_window._docs.items() if d.file_path == a)
        )
    )
    assert main_window._log_chk.isChecked(), "switching back must show a's own state"


# ---------------------------------------------------------- preprocessing
def test_geometric_op_resizes_the_displayed_image(main_window, ring_tif):
    main_window.open_path(ring_tif)
    doc = main_window._cur()
    before = doc.view.image_shape()
    main_window._preproc_add(doc, "scale", {"sx": 0.5, "sy": 1.0})
    assert doc.view.image_shape() == (before[0], before[1] // 2)


def test_preproc_ops_are_per_document(main_window, three_tifs):
    a, b = three_tifs[0], three_tifs[1]
    main_window._open_document(a, preview=False)
    main_window._preproc_add(main_window._cur(), "sqrt")
    main_window._open_document(b, preview=False)
    assert "sqrt" not in kinds(main_window._cur())


# ------------------------------------------------------- ring profile tab
def test_ring_panel_measures_the_active_ellipse(main_window, ring_tif):
    from qoradfxm.gui.roi import EllipseFitROI

    main_window.open_path(ring_tif)
    doc = main_window._cur()
    doc.ds = doc.ds.fit_ellipse(ellipse_points())
    main_window.add_roi(EllipseFitROI(doc.ds.fit.geom, points=ellipse_points()))
    main_window._ring_panel.refresh()

    prof = main_window._ring_panel.profile
    assert prof is not None
    assert prof.peak()[0] == pytest.approx(1.3, abs=0.01)


def test_ring_panel_ignores_a_document_without_an_ellipse(main_window, ring_tif):
    main_window.open_path(ring_tif)
    main_window._ring_panel.refresh()
    assert main_window._ring_panel.profile is None


def test_ring_panel_measures_linear_data_even_with_log_on(main_window, ring_tif):
    from qoradfxm.gui.roi import EllipseFitROI

    main_window.open_path(ring_tif)
    doc = main_window._cur()
    doc.ds = doc.ds.fit_ellipse(ellipse_points())
    main_window.add_roi(EllipseFitROI(doc.ds.fit.geom, points=ellipse_points()))
    main_window._ring_panel.refresh()
    linear_peak = main_window._ring_panel.profile.peak()

    main_window._log_chk.setChecked(True)
    main_window._ring_panel.refresh()
    assert main_window._ring_panel.profile.peak() == pytest.approx(linear_peak)


# ------------------------------------------------------ explorer ".." row
def test_up_row_moves_the_tree_to_the_parent(main_window, tmp_path):
    child = tmp_path / "run01"
    child.mkdir()
    main_window._set_tree_root(child)
    assert main_window._tree_root() == child

    main_window._up_btn.click()
    assert main_window._tree_root() == tmp_path


def test_up_row_selects_the_folder_it_came_from(main_window, tmp_path, pump):
    child = tmp_path / "run01"
    child.mkdir()
    main_window._set_tree_root(child)
    main_window._go_up_dir()
    pump(200)
    from pathlib import Path

    current = main_window._fs_model.filePath(main_window._tree.currentIndex())
    assert Path(current) == child  # Qt hands back forward slashes on Windows


def test_backspace_goes_up(main_window, tmp_path, pump):
    from PySide6 import QtCore, QtGui, QtWidgets

    child = tmp_path / "run01"
    child.mkdir()
    main_window._set_tree_root(child)
    main_window._tree.setFocus()
    QtWidgets.QApplication.sendEvent(
        main_window._tree,
        QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_Backspace, QtCore.Qt.NoModifier
        ),
    )
    pump(200)
    assert main_window._tree_root() == tmp_path


def test_up_row_is_disabled_when_every_drive_is_listed(main_window):
    main_window._fs_model.setRootPath("")
    main_window._tree.setRootIndex(main_window._fs_model.index(""))
    main_window._update_up_row()
    assert main_window._tree_root() is None
    assert not main_window._up_btn.isEnabled()

    main_window._go_up_dir()  # must be a no-op, not a crash
    assert main_window._tree_root() is None


def test_up_row_from_a_drive_root_lists_the_drives(main_window, tmp_path):
    from pathlib import Path

    root = Path(tmp_path.anchor or "/")
    main_window._set_tree_root(root)
    main_window._go_up_dir()
    assert main_window._tree_root() is None


# --------------------------------------------------------- explorer filter
@pytest.fixture
def mixed_folder(tmp_path):
    for name in ("shockwave_01.tif", "shockwave_02.tif", "alignment_01.tif"):
        tifffile.imwrite(tmp_path / name, np.zeros((4, 4), np.float32))
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    return tmp_path


def listing(main_window) -> list[str]:
    from pathlib import Path

    model, root = main_window._fs_model, main_window._tree.rootIndex()
    return sorted(
        Path(model.filePath(model.index(r, 0, root))).name
        for r in range(model.rowCount(root))
    )


UNFILTERED = [
    "alignment_01.tif",
    "notes.txt",
    "shockwave_01.tif",
    "shockwave_02.tif",
    "sub",
]
FILTERED = ["shockwave_01.tif", "shockwave_02.tif", "sub"]


def rows_sorted_by_name(main_window) -> bool:
    """Whether QFileSystemModel has finished its delayed sort of the folder.

    Rows first appear in directory order; a zero-delay timer then sorts them and
    moves persistent indexes. Linux returns directory order unsorted, so an index
    taken before the sort can end up on the last row (Windows and macOS list
    alphabetically already).
    """
    model, root = main_window._fs_model, main_window._tree.rootIndex()
    paths = [
        model.filePath(model.index(r, 0, root)) for r in range(model.rowCount(root))
    ]
    return paths == sorted(paths)


def listing_state(main_window) -> str:
    """What the explorer shows and why, for a failure message.

    An empty listing with a valid root means QFileSystemModel never populated the
    folder; a full one with the wrong names means the filter was not applied.
    """
    model, root = main_window._fs_model, main_window._tree.rootIndex()
    return (
        f"listing={listing(main_window)} rowCount={model.rowCount(root)} "
        f"canFetchMore={model.canFetchMore(root)} root={model.filePath(root)!r} "
        f"rootPath={model.rootPath()!r} nameFilters={model.nameFilters()} "
        f"text={main_window._filter_edit.text()!r} "
        f"timer_active={main_window._filter_timer.isActive()}"
    )


def wait_for_listing(main_window, wait_until, want: list[str]) -> None:
    wait_until(lambda: listing(main_window) == want, lambda: listing_state(main_window))


def test_filter_narrows_the_listing(main_window, mixed_folder, wait_until):
    main_window._set_tree_root(mixed_folder)
    wait_for_listing(main_window, wait_until, UNFILTERED)

    main_window._filter_edit.setText("shock")
    wait_for_listing(main_window, wait_until, FILTERED)


def test_filter_keeps_folders_visible(main_window, mixed_folder, wait_until):
    """Otherwise you could not browse while a filter is active."""
    main_window._set_tree_root(mixed_folder)
    main_window._filter_edit.setText("shock")
    wait_for_listing(main_window, wait_until, FILTERED)  # "sub" survives the filter


def test_clearing_the_filter_restores_everything(main_window, mixed_folder, wait_until):
    main_window._set_tree_root(mixed_folder)
    wait_for_listing(main_window, wait_until, UNFILTERED)
    main_window._filter_edit.setText("shock")
    wait_for_listing(main_window, wait_until, FILTERED)
    main_window._filter_edit.clear()
    wait_for_listing(main_window, wait_until, UNFILTERED)


def test_filter_survives_changing_folder(main_window, mixed_folder, wait_until):
    (mixed_folder / "sub" / "shockwave_09.tif").parent.mkdir(exist_ok=True)
    tifffile.imwrite(
        mixed_folder / "sub" / "shockwave_09.tif", np.zeros((4, 4), np.float32)
    )
    tifffile.imwrite(mixed_folder / "sub" / "other.tif", np.zeros((4, 4), np.float32))
    main_window._set_tree_root(mixed_folder)
    main_window._filter_edit.setText("shock")
    wait_for_listing(main_window, wait_until, FILTERED)
    main_window._set_tree_root(mixed_folder / "sub")
    wait_for_listing(main_window, wait_until, ["shockwave_09.tif"])


def test_escape_clears_the_filter_and_returns_to_the_tree(
    main_window, mixed_folder, wait_until
):
    from PySide6 import QtCore
    from PySide6.QtTest import QTest

    main_window._set_tree_root(mixed_folder)
    main_window._filter_edit.setFocus()
    main_window._filter_edit.setText("shock")
    wait_for_listing(main_window, wait_until, FILTERED)
    QTest.keyClick(main_window._filter_edit, QtCore.Qt.Key_Escape)
    wait_for_listing(main_window, wait_until, UNFILTERED)
    assert main_window._filter_edit.text() == ""


def test_ctrl_f_focuses_the_filter(main_window):
    main_window._focus_filter()
    # hasFocus() needs an active window, which an offscreen test never has
    assert main_window.focusWidget() is main_window._filter_edit
    assert main_window._file_dock.isVisible()


def test_double_clicking_a_folder_reroots_the_tree(main_window, tmp_path, pump):
    child = tmp_path / "run01"
    child.mkdir()
    (child / "deep").mkdir()
    main_window._set_tree_root(tmp_path)
    pump(200)

    main_window._on_tree_open(main_window._fs_model.index(str(child)))
    assert main_window._tree_root() == child
    assert main_window._settings.value("last_dir") == str(child)


def test_expanding_a_folder_leaves_the_root_alone(main_window, tmp_path, pump):
    """The chevron still browses in place — only opening dives in."""
    child = tmp_path / "run01"
    child.mkdir()
    main_window._set_tree_root(tmp_path)
    pump(200)

    index = main_window._fs_model.index(str(child))
    main_window._tree.expand(index)
    pump(200)
    assert main_window._tree.isExpanded(index)
    assert main_window._tree_root() == tmp_path


def test_diving_in_and_back_out_returns_where_you_were(main_window, tmp_path, pump):
    child = tmp_path / "run01"
    child.mkdir()
    main_window._set_tree_root(tmp_path)
    main_window._on_tree_open(main_window._fs_model.index(str(child)))
    main_window._go_up_dir()
    pump(200)
    assert main_window._tree_root() == tmp_path


# ------------------------------------------------ explorer arrow-key preview
def test_arrow_keys_move_the_preview(main_window, three_tifs, pump, wait_until):
    from PySide6 import QtCore, QtGui, QtWidgets

    folder = three_tifs[0].parent
    tree, model = main_window._tree, main_window._fs_model
    model.setRootPath(str(folder))
    tree.setRootIndex(model.index(str(folder)))
    wait_until(
        lambda: (
            model.rowCount(tree.rootIndex()) >= len(three_tifs)
            and rows_sorted_by_name(main_window)
        ),
        lambda: listing_state(main_window),
    )
    start = model.index(str(three_tifs[0]))

    tree.setCurrentIndex(start)
    main_window._on_tree_preview(start)
    pump(200)
    first = main_window._cur().file_path
    assert first == three_tifs[0]

    tree.setFocus()
    QtWidgets.QApplication.sendEvent(
        tree,
        QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_Down, QtCore.Qt.NoModifier
        ),
    )
    wait_until(
        lambda: main_window._cur().file_path != first,
        lambda: f"still on {first}; {listing_state(main_window)}",
    )
    assert main_window._cur().preview is True
    assert main_window._tabs.count() == 1, "navigation must not stack tabs"


def test_arrow_keys_do_nothing_without_a_preview_tab(
    main_window, three_tifs, pump, wait_until
):
    from PySide6 import QtCore, QtGui, QtWidgets

    folder = three_tifs[0].parent
    tree, model = main_window._tree, main_window._fs_model
    model.setRootPath(str(folder))
    tree.setRootIndex(model.index(str(folder)))
    wait_until(
        lambda: (
            model.rowCount(tree.rootIndex()) >= len(three_tifs)
            and rows_sorted_by_name(main_window)
        ),
        lambda: listing_state(main_window),
    )

    main_window._open_document(three_tifs[0], preview=False)  # pinned
    pinned = main_window._cur().file_path
    tree.setCurrentIndex(model.index(str(three_tifs[0])))
    tree.setFocus()
    QtWidgets.QApplication.sendEvent(
        tree,
        QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, QtCore.Qt.Key_Down, QtCore.Qt.NoModifier
        ),
    )
    pump(400)
    assert main_window._cur().file_path == pinned
    assert main_window._tabs.count() == 1
