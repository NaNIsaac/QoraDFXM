"""Control dock, analysis dock and the ring profile panel."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from .image_view import COLORMAPS
from .ring_panel import RingProfilePanel
from .widgets import CollapsibleSection


class ControlDockMixin:
    """Control dock, analysis dock and the ring profile panel."""

    def _build_control_dock(self) -> None:
        dock = self._control_dock = QtWidgets.QDockWidget("컨트롤", self)
        dock.setObjectName("ControlDock")
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
        )
        panel = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(panel)
        v.setSpacing(4)

        # --- Display section (collapsible)
        disp = QtWidgets.QWidget()
        dl = QtWidgets.QFormLayout(disp)
        dl.setContentsMargins(8, 4, 8, 4)

        self._log_chk = QtWidgets.QCheckBox("Log scale")
        # Restore the cross-session preference before wiring the handler (no
        # document exists yet; _make_dataset applies it to whatever is opened).
        self._log_chk.setChecked(
            self._settings.value("persistent_log", False, type=bool)
        )
        self._log_chk.toggled.connect(self._do_log)
        dl.addRow(self._log_chk)

        self._overmax_chk = QtWidgets.QCheckBox("Over-max Highlight")
        self._overmax_chk.setChecked(self._app_prefs.overmax)
        self._overmax_chk.toggled.connect(self._do_overmax)

        self._overmax_color_btn = QtWidgets.QPushButton()
        self._overmax_color_btn.setFixedWidth(28)
        self._overmax_color_btn.setFixedHeight(20)
        self._overmax_color = QtGui.QColor(self._app_prefs.overmax_color)
        self._update_overmax_btn_style()
        self._overmax_color_btn.clicked.connect(self._choose_overmax_color)

        overmax_row = QtWidgets.QHBoxLayout()
        overmax_row.setContentsMargins(0, 0, 0, 0)
        overmax_row.addWidget(self._overmax_chk)
        overmax_row.addWidget(self._overmax_color_btn)
        dl.addRow(overmax_row)

        self._cmap_combo = QtWidgets.QComboBox()
        self._cmap_combo.setIconSize(QtCore.QSize(96, 14))
        for name in COLORMAPS:
            self._cmap_combo.addItem(self._cmap_icon(name), name)
        with QtCore.QSignalBlocker(self._cmap_combo):
            self._cmap_combo.setCurrentText(self._app_prefs.colormap)
        self._cmap_combo.currentTextChanged.connect(self._do_colormap)
        dl.addRow("Colormap", self._cmap_combo)

        btn_auto = QtWidgets.QPushButton("Auto 레벨 (0.5–99.5%)")
        btn_auto.clicked.connect(self._do_autoscale)
        dl.addRow(btn_auto)

        # Histogram
        self._hist_chk = QtWidgets.QCheckBox("히스토그램 표시")
        self._hist_chk.setChecked(True)
        self._hist_chk.toggled.connect(self._do_hist_visible)
        hist_row = QtWidgets.QHBoxLayout()
        hist_row.setContentsMargins(0, 0, 0, 0)
        hist_row.addWidget(self._hist_chk)
        btn_detach = QtWidgets.QPushButton("창 분리")
        btn_detach.setToolTip("히스토그램을 별도 창으로 분리")
        btn_detach.clicked.connect(self._do_hist_detach)
        hist_row.addWidget(btn_detach)
        dl.addRow(hist_row)
        v.addWidget(CollapsibleSection("디스플레이", disp))

        # --- Scale section (collapsible)
        scale = QtWidgets.QWidget()
        sl = QtWidgets.QFormLayout(scale)
        sl.setContentsMargins(8, 4, 8, 4)

        self._scale_chk = QtWidgets.QCheckBox("실거리 사용 (기본: pixel)")
        self._scale_chk.setChecked(self._app_prefs.scale_on)
        self._scale_chk.toggled.connect(self._on_scale_changed)
        sl.addRow(self._scale_chk)

        self._px_size_spin = QtWidgets.QDoubleSpinBox()
        self._px_size_spin.setDecimals(6)
        self._px_size_spin.setRange(1e-6, 1e6)
        self._px_size_spin.setValue(self._app_prefs.px_size)
        self._px_size_spin.valueChanged.connect(self._on_scale_changed)
        sl.addRow("픽셀당 거리", self._px_size_spin)

        self._unit_combo = QtWidgets.QComboBox()
        self._unit_combo.setEditable(True)
        self._unit_combo.addItems(["µm", "nm", "mm", "Å"])
        self._unit_combo.setCurrentText(self._app_prefs.unit)
        self._unit_combo.currentTextChanged.connect(self._on_scale_changed)
        sl.addRow("단위", self._unit_combo)
        v.addWidget(CollapsibleSection("척도 (Scale bar)", scale))

        # --- Tool-specific area
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("color:#3a3a3a;")
        v.addWidget(line)
        self._tool_title = QtWidgets.QLabel("도구 옵션")
        self._tool_title.setStyleSheet(
            "color:#2dd4bf; font-weight:bold; font-size:11pt; padding:2px 4px;"
        )
        v.addWidget(self._tool_title)

        self._tool_stack = QtWidgets.QStackedWidget()
        self._stack_pages = {
            "view": self._build_view_page(),
            "distance": self._build_distance_page(),
            "line": self._build_line_page(),
            "ellipse": self._build_ellipse_page(),
        }
        for page in self._stack_pages.values():
            self._tool_stack.addWidget(page)
        v.addWidget(self._tool_stack, 1)

        dock.setWidget(panel)
        dock.setMinimumWidth(330)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    def _update_overmax_btn_style(self) -> None:
        self._overmax_color_btn.setStyleSheet(
            f"background-color: {self._overmax_color.name()}; border: 1px solid #555; border-radius: 3px;"
        )

    def _choose_overmax_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            self._overmax_color, self, "Over-max Highlight Color"
        )
        if color.isValid():
            self._overmax_color = color
            self._update_overmax_btn_style()
            self._edit_prefs(overmax_color=color.name())
            if v := self._cur_view():
                v.set_overmax_color(color)
                self._log(f"Over-max highlight color: {color.name()}")

    def _build_view_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        msg = QtWidgets.QLabel(
            "이동 / 확대 도구.\n\n"
            "• ✋ 이동: 좌드래그로 사진 위치 이동\n"
            "• 🔍 확대: 박스 드래그 / 스크롤 줌\n"
            "• 더블클릭: 기본 줌 복귀\n\n"
            "밝기·색·척도는 위 패널에서 조절합니다."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#999;")
        lay.addWidget(msg)
        lay.addStretch(1)
        return w

    def _build_distance_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(
            QtWidgets.QLabel(
                "점을 클릭해 구간 거리 측정 (링 간격).\n우클릭=가까운 점 삭제."
            )
        )

        self._dist_table = QtWidgets.QTableWidget(0, 3)
        self._dist_table.setHorizontalHeaderLabels(["구간", "거리", "누적"])
        self._dist_table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._dist_table, 1)

        self._dist_total = QtWidgets.QLabel("합계: –")
        self._dist_total.setStyleSheet("font-weight:bold;")
        lay.addWidget(self._dist_total)

        btn = QtWidgets.QPushButton("거리 초기화")
        btn.clicked.connect(self._do_clear_distance)
        lay.addWidget(btn)
        return w

    def _build_line_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(
            QtWidgets.QLabel(
                "라인을 드래그하면 강도 프로파일이\n하단 플롯에 표시됩니다."
            )
        )

        self._line_stats = QtWidgets.QFormLayout()
        self._line_len = QtWidgets.QLabel("–")
        self._line_min = QtWidgets.QLabel("–")
        self._line_max = QtWidgets.QLabel("–")
        self._line_mean = QtWidgets.QLabel("–")
        self._line_stats.addRow("길이", self._line_len)
        self._line_stats.addRow("min", self._line_min)
        self._line_stats.addRow("max", self._line_max)
        self._line_stats.addRow("mean", self._line_mean)
        box = QtWidgets.QGroupBox("프로파일 통계")
        box.setLayout(self._line_stats)
        lay.addWidget(box)
        lay.addStretch(1)
        return w

    def _build_ellipse_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(w)

        self._fit_shape = QtWidgets.QComboBox()
        self._fit_shape.addItems(["타원 (Ellipse)"])
        fl.addWidget(self._fit_shape)

        hint = QtWidgets.QLabel(
            "좌클릭=점 추가, 우클릭=가까운 점 삭제\n5점 이상에서 Fit."
        )
        hint.setStyleSheet("color:#888;")
        fl.addWidget(hint)

        row = QtWidgets.QHBoxLayout()
        btn_fit = QtWidgets.QPushButton("Fit")
        btn_fit.clicked.connect(self._do_fit)
        btn_clear = QtWidgets.QPushButton("Clear")
        btn_clear.clicked.connect(self._on_clear_fit)
        btn_save = QtWidgets.QPushButton("결과 저장")
        btn_save.clicked.connect(self._save_fit)
        row.addWidget(btn_fit)
        row.addWidget(btn_clear)
        row.addWidget(btn_save)
        fl.addLayout(row)

        self._results = QtWidgets.QPlainTextEdit()
        self._results.setReadOnly(True)
        self._results.setFont(QtGui.QFont("Consolas", 9))
        fl.addWidget(self._results, 1)
        return w

    def _build_analysis_dock(self) -> None:
        self._analysis_dock = QtWidgets.QDockWidget("분석 / 로그", self)
        self._analysis_dock.setObjectName("AnalysisDock")
        self._analysis_dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        tabs = self._analysis_tabs = QtWidgets.QTabWidget()

        self._profile_plot = pg.PlotWidget()
        self._profile_plot.setBackground("#202225")
        self._profile_plot.showGrid(x=True, y=True, alpha=0.18)
        self._profile_plot.setLabel("bottom", "거리 (px)")
        self._profile_plot.setLabel("left", "강도")
        for ax in ("bottom", "left"):
            axis = self._profile_plot.getAxis(ax)
            axis.setPen(pg.mkPen("#666", width=1))
            axis.setTextPen(pg.mkPen("#bbb"))
        self._profile_curve = self._profile_plot.plot(
            pen=pg.mkPen("#22d3ee", width=1.6)
        )
        tabs.addTab(self._profile_plot, "라인 프로파일")

        # Core measures the ring profile I(k); this only draws it.
        self._ring_panel = RingProfilePanel(source=self._ring_source)
        tabs.addTab(self._ring_panel, "링 프로파일")

        # The results table lives in its own resizable window (see _show_results_table),
        # not this cramped bottom dock. Build the table widget here though.
        self._build_results_table_widget()

        # Per-file operation log
        self._log_view = QtWidgets.QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QtGui.QFont("Consolas", 9))
        tabs.addTab(self._log_view, "로그")

        self._analysis_dock.setWidget(tabs)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self._analysis_dock)
        self._analysis_dock.hide()

    def _linear_image(self, doc):
        """Current image with the nonlinear display ops stripped (cached).

        A ring profile is a quantitative measurement, so it must run on linear
        intensity — but on the SAME geometry the user picked the ellipse on.
        """
        key = (doc.session_id, json.dumps(doc.ds.history.to_list(), sort_keys=True))
        cached = getattr(self, "_linear_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        img = doc.ds.linear_view().image
        self._linear_cache = (key, img)
        return img

    def _ring_source(self):
        """(linear image, live ellipse geometry) for the ring panel, or None."""
        doc = self._cur()
        if doc is None or doc.ds is None:
            return None
        rois = doc.rois_of_type("ellipse")
        if rois:
            geom = dict(rois[-1].geometry)  # the ROI the user can drag
        elif doc.ds.fit is not None and doc.ds.fit.geom:
            geom = dict(doc.ds.fit.geom)
        else:
            return None
        return self._linear_image(doc), geom

    def _ring_update(self) -> None:
        if getattr(self, "_ring_panel", None) is not None:
            self._ring_panel.request_update()

    def _log(self, message: str) -> None:
        """Append a log line to the active document session and refresh view."""
        doc = self._cur()
        if doc is None:
            return
        doc.add_log(message)
        self._refresh_log()

    def _refresh_log(self) -> None:
        doc = self._cur()
        self._log_view.setPlainText("\n".join(doc.logs) if doc else "")
        self._log_view.moveCursor(QtGui.QTextCursor.End)

    def _on_line_profile(self, axis, values, unit: str) -> None:
        self._profile_curve.setData(axis, values)
        self._profile_plot.setLabel("bottom", f"거리 ({unit})")
        self._profile_plot.setLabel("left", "강도")
        vals = np.asarray(values, dtype=float)
        if vals.size:
            self._line_len.setText(f"{axis[-1]:.2f} {unit}")
            self._line_min.setText(f"{vals.min():.4g}")
            self._line_max.setText(f"{vals.max():.4g}")
            self._line_mean.setText(f"{vals.mean():.4g}")

    def _on_distance(self, seg, cum, unit: str) -> None:
        self._dist_table.setRowCount(len(seg))
        for i, (s, c) in enumerate(zip(seg, cum, strict=False)):
            self._dist_table.setItem(
                i, 0, QtWidgets.QTableWidgetItem(f"{i + 1}→{i + 2}")
            )
            self._dist_table.setItem(
                i, 1, QtWidgets.QTableWidgetItem(f"{s:.2f} {unit}")
            )
            self._dist_table.setItem(
                i, 2, QtWidgets.QTableWidgetItem(f"{c:.2f} {unit}")
            )
        self._dist_total.setText(f"합계: {cum[-1]:.2f} {unit}" if cum else "합계: –")

    def _build_statusbar(self) -> None:
        self._status = self.statusBar()
        self._pos_label = QtWidgets.QLabel("커서: –")
        self._info_label = QtWidgets.QLabel("이미지 없음")
        self._status.addWidget(self._pos_label, 1)
        self._status.addPermanentWidget(self._info_label)

        # Right side: zoom controls.
        btn_out = QtWidgets.QToolButton()
        btn_out.setText("−")
        btn_out.setAutoRaise(True)
        btn_out.clicked.connect(
            lambda: self._cur_view() and self._cur_view().zoom_out()
        )
        btn_in = QtWidgets.QToolButton()
        btn_in.setText("+")
        btn_in.setAutoRaise(True)
        btn_in.clicked.connect(lambda: self._cur_view() and self._cur_view().zoom_in())
        btn_fit = QtWidgets.QToolButton()
        btn_fit.setText("⤢")
        btn_fit.setToolTip("화면에 맞춤 (fit)")
        btn_fit.setAutoRaise(True)
        btn_fit.clicked.connect(self._do_reset)

        self._zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._zoom_slider.setRange(10, 800)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.sliderMoved.connect(self._on_zoom_slider)
        self._zoom_label = QtWidgets.QLabel("100%")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        for wd in (btn_out, self._zoom_slider, btn_in, self._zoom_label, btn_fit):
            self._status.addPermanentWidget(wd)

    def _on_zoom_slider(self, val: int) -> None:
        if v := self._cur_view():
            v.set_zoom(float(val))

    def _on_zoom_changed(self, percent: float) -> None:
        self._zoom_label.setText(f"{percent:.0f}%")
        if not self._zoom_slider.isSliderDown():
            with QtCore.QSignalBlocker(self._zoom_slider):
                self._zoom_slider.setValue(int(max(10, min(800, percent))))

    def _set_tree_root(self, folder: Path) -> None:
        """Root the file tree AT this folder, not the whole disk."""
        self._fs_model.setRootPath(str(folder))
        self._tree.setRootIndex(self._fs_model.index(str(folder)))
        if hasattr(self, "_up_btn"):
            self._update_up_row()

    @staticmethod
    def _cmap_icon(name: str, w: int = 96, h: int = 14) -> QtGui.QIcon:
        """A horizontal gradient swatch previewing a colormap in the dropdown."""
        try:
            cm = pg.colormap.get(name, source="matplotlib")
        except Exception:
            cm = pg.colormap.get("gray", source="matplotlib")
        lut = cm.getLookupTable(0.0, 1.0, w, alpha=False)
        arr = np.ascontiguousarray(np.repeat(lut[np.newaxis, :, :], h, axis=0))
        qimg = QtGui.QImage(arr.data, w, h, 3 * w, QtGui.QImage.Format_RGB888)
        return QtGui.QIcon(QtGui.QPixmap.fromImage(qimg.copy()))

    @staticmethod
    def _under_temp(p: str | Path) -> bool:
        """True if a path lives inside the system temp/cache directory."""
        try:
            Path(p).resolve().relative_to(Path(tempfile.gettempdir()).resolve())
            return True
        except ValueError, OSError:
            return False
