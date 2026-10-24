"""Main application window: folder browser, image view, controls."""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from ..core import QoraDFXMDataset, io
from ..core.history import History
from ..core.ops import GEOMETRIC_KINDS, CorrectionError
from ..core.results import MASTER_COLUMNS, ResultsFrame
from .constants import APP_NAME, APP_VERSION
from .control_dock import ControlDockMixin
from .document import DocumentSession
from .documents import DocumentsMixin
from .file_dock import FileDockMixin
from .icons import AppIcons, logo_icon, logo_pixmap, wordmark_pixmap
from .image_view import COLORMAPS, ImageView
from .models import COLUMN_LABELS, MasterTableModel
from .pipeline import PipelineMixin
from .prefs import ViewPrefs
from .results_table import ResultsTableMixin
from .results_window import DropTableView, ResultsWindow
from .ribbon import RibbonMixin
from .ring_panel import RingProfilePanel
from .roi import EllipseFitROI, LineProfileROI, RectRegionROI
from .settings_dialog import SettingsDialog
from .theme import build_style
from .widgets import CollapsibleSection, DropOverlay, FilterEdit

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "COLORMAPS",
    "COLUMN_LABELS",
    "GEOMETRIC_KINDS",
    "MASTER_COLUMNS",
    "AppIcons",
    "CollapsibleSection",
    "CorrectionError",
    "DocumentSession",
    "DropOverlay",
    "DropTableView",
    "EllipseFitROI",
    "FilterEdit",
    "History",
    "ImageView",
    "LineProfileROI",
    "MainWindow",
    "MasterTableModel",
    "QoraDFXMDataset",
    "RectRegionROI",
    "ResultsFrame",
    "ResultsWindow",
    "RingProfilePanel",
    "SettingsDialog",
    "ViewPrefs",
    "build_style",
    "logo_icon",
    "logo_pixmap",
    "wordmark_pixmap",
]


class MainWindow(
    DocumentsMixin,
    ResultsTableMixin,
    ControlDockMixin,
    FileDockMixin,
    RibbonMixin,
    PipelineMixin,
    QtWidgets.QMainWindow,
):
    _SUPPORTED = io.H5_SUFFIXES + io.IMAGE_SUFFIXES + io.TEXT_SUFFIXES
    # What the explorer lists; the filter box narrows these further.
    _FILE_GLOBS = tuple(f"*{suf}" for suf in _SUPPORTED)

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(logo_icon())
        self.resize(1500, 950)

        self._current_file: Path | None = None
        self._suppress_reveal = False
        self._pending_fit: dict | None = None
        self._shot_map: dict[str, tuple] = {}  # shot_id -> (file_path, FramePath)
        self._master = MasterTableModel(parent=self)
        self._frames: list[io.FramePath] = []
        self._settings = QtCore.QSettings("QoraDFXM", "ImageAnalyzer")
        # Defaults for documents opened from now on (see gui/prefs.py).
        self._app_prefs = ViewPrefs.load(self._settings)
        self._theme = self._settings.value("theme", "Dark", type=str)
        self._icon_actions: dict[QtGui.QAction, str] = {}
        self._icon_buttons: dict[QtWidgets.QToolButton, str] = {}
        self._icon_color = "#d4d4d8" if self._theme == "Dark" else "#33333a"
        self.setStyleSheet(build_style(self._theme))

        # Central area: VSCode-style document tabs, one per open file/frame.
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        bar = self._tabs.tabBar()
        bar.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        bar.installEventFilter(self)  # middle-click closes, as everywhere else
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.tabBarDoubleClicked.connect(
            lambda i: self._pin_tab(self._tabs.widget(i))
        )
        self.setCentralWidget(self._tabs)
        self._docs: dict[QtWidgets.QWidget, dict] = {}
        self._current_tool = "select"
        self._cmap_syncing = False
        self.apply_theme(self._theme)

        self._build_file_dock()
        self._build_control_dock()
        self._build_analysis_dock()
        self._build_ribbon()
        self._build_statusbar()

        # Drag & drop of files/folders anywhere on the window.
        self.setAcceptDrops(True)
        self._overlay = DropOverlay(self)

        self._restore_layout()
        self._restore_session()

    def _restore_layout(self) -> None:
        """Come back the size you left, with the docks where you put them."""
        geom = self._settings.value("win_geometry")
        state = self._settings.value("win_state")
        if geom:
            self.restoreGeometry(geom)
        if state:
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        self._settings.setValue("win_geometry", self.saveGeometry())
        self._settings.setValue("win_state", self.saveState())
        super().closeEvent(event)

    def _update_window_title(self) -> None:
        doc = self._cur()
        self.setWindowTitle(f"{doc.file_path.name} — {APP_NAME}" if doc else APP_NAME)

    def _new_doc_prefs(self) -> ViewPrefs:
        """What a newly opened document starts with: the app-scoped defaults."""
        return self._app_prefs.copy(tool=getattr(self, "_current_tool", "select"))

    def _urls_have_supported(self, urls) -> bool:
        for u in urls:
            p = Path(u.toLocalFile())
            if p.is_dir() or p.suffix.lower() in self._SUPPORTED:
                return True
        return False

    def _gather_supported(self, paths: list[Path]) -> list[Path]:
        files: list[Path] = []
        for p in paths:
            if p.is_dir():
                files += sorted(
                    f
                    for f in p.rglob("*")
                    if f.is_file() and f.suffix.lower() in self._SUPPORTED
                )
            elif p.is_file() and p.suffix.lower() in self._SUPPORTED:
                files.append(p)
        return files

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            self._overlay.set_ok(self._urls_have_supported(e.mimeData().urls()))
            self._overlay.cover()
            e.acceptProposedAction()

    def dragMoveEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragLeaveEvent(self, e) -> None:
        self._overlay.hide()

    def dropEvent(self, e) -> None:
        self._overlay.hide()
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls()]
        files = self._gather_supported(paths)
        if not files:
            self._status.showMessage("지원하지 않는 파일 형식입니다.", 4000)
            return
        # A dropped folder becomes the file-tree root for convenient browsing.
        for p in paths:
            if p.is_dir():
                self._set_tree_root(p)
                break
        for f in files:
            self._open_document(f, preview=False)
        self._status.showMessage(f"{len(files)}개 파일 열림.", 3000)
        e.acceptProposedAction()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self._overlay.isVisible():
            self._overlay.setGeometry(self.rect())

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self, self._settings)
        dlg.exec()
        vals = dlg.result_values()
        for k, v in vals.items():
            self._settings.setValue(k, v)
        # The dialog edits the app-scoped defaults; re-read them, then let the
        # panel push the new colormap through the normal handler.
        self._app_prefs = ViewPrefs.load(self._settings)
        self._cmap_combo.setCurrentText(vals["def_cmap"])
        self._status.showMessage("설정 저장됨.", 3000)

    def _cur(self) -> DocumentSession | None:
        return self._docs.get(self._tabs.currentWidget())

    def _cur_view(self) -> ImageView | None:
        doc = self._cur()
        if doc and doc.kind == "image":
            return doc.view
        return None

    def _set_action_icon(self, action: QtGui.QAction, icon_name: str) -> None:
        self._icon_actions[action] = icon_name
        action.setIcon(AppIcons.get(icon_name, self._icon_color))

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self._icon_color = "#d4d4d8" if theme == "Dark" else "#33333a"
        self.setStyleSheet(build_style(theme))

        for act, name in self._icon_actions.items():
            act.setIcon(AppIcons.get(name, self._icon_color))
        for btn, name in self._icon_buttons.items():
            btn.setIcon(AppIcons.get(name, self._icon_color))

        dark = theme == "Dark"
        for doc in self._docs.values():
            if doc.kind == "image" and doc.view is not None:
                doc.view.apply_theme(dark)
        if hasattr(self, "_profile_plot"):
            self._profile_plot.setBackground("#202225" if dark else "#f4f4f6")
            for ax in ("bottom", "left"):
                a = self._profile_plot.getAxis(ax)
                a.setPen(pg.mkPen("#666" if dark else "#9a9aa2"))
                a.setTextPen(pg.mkPen("#bbb" if dark else "#333"))
        self._settings.setValue("theme", theme)

    # Dispatch wrappers act on the ACTIVE tab's view AND update its session.
    def _do_reset(self) -> None:
        if v := self._cur_view():
            v.reset_zoom()

    def _do_log(self, b) -> None:
        doc = self._cur()
        if doc is None or doc.ds is None:
            return
        # Log is just another op in the Core pipeline (appended last / removed).
        if b and not doc.ds.log_scale:
            new_ds = doc.ds.apply_log()
        elif not b and doc.ds.log_scale:
            ops = [op for op in doc.ds.history if op.kind != "log"]
            new_ds = doc.ds.set_history(History(tuple(ops)))
        else:
            new_ds = doc.ds
        if not self._set_recipe(doc, new_ds):
            return
        self._settings.setValue("persistent_log", b)
        self._log(f"Log scale {'ON' if b else 'OFF'}")
        self._after_preproc_change(doc)

    def _restore_session(self) -> None:
        """Reopen at the previously used folder / file."""
        last_dir = self._settings.value("last_dir", "", type=str)
        if last_dir and Path(last_dir).exists() and not self._under_temp(last_dir):
            self._set_tree_root(Path(last_dir))
        elif self._under_temp(last_dir):
            self._settings.remove("last_dir")

        last_file = self._settings.value("last_file", "", type=str)
        if last_file and Path(last_file).is_file() and not self._under_temp(last_file):
            self._open_document(Path(last_file))
        else:
            if self._under_temp(last_file):
                self._settings.remove("last_file")
            self._on_tab_changed()

    def _remember(self) -> None:
        if self._current_file is not None and not self._under_temp(self._current_file):
            self._settings.setValue("last_file", str(self._current_file))
            self._settings.setValue("last_dir", str(self._current_file.parent))
