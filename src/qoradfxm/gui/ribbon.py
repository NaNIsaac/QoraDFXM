"""Ribbon UI, keyboard shortcuts and the tab bar commands."""

from __future__ import annotations

from typing import ClassVar

from PySide6 import QtCore, QtGui, QtWidgets

from .constants import APP_NAME
from .icons import AppIcons, logo_pixmap
from .image_view import COLORMAPS


class RibbonMixin:
    """Ribbon UI, keyboard shortcuts and the tab bar commands."""

    def _act(self, text: str, slot, tip: str = "", checkable: bool = False):
        a = QtGui.QAction(text, self, checkable=checkable)
        if tip:
            a.setToolTip(tip)
        if checkable:
            a.triggered.connect(lambda _=False: slot())
        else:
            a.triggered.connect(slot)
        return a

    @staticmethod
    def _rbtn(action, big: bool = True) -> QtWidgets.QToolButton:
        b = QtWidgets.QToolButton()
        b.setDefaultAction(action)
        b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        b.setAutoRaise(True)
        b.setProperty("class", "RibbonBtn")
        b.setIconSize(QtCore.QSize(26, 26))
        b.setMinimumWidth(62)
        b.setMinimumHeight(62)  # uniform height for 1- or 2-line labels
        return b

    def _ribbon_group(self, title: str, inner: QtWidgets.QLayout) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("RibbonGroupBox")
        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 2)
        v.setSpacing(3)
        holder = QtWidgets.QWidget()
        holder.setObjectName("RibbonHolder")
        holder.setLayout(inner)
        v.addWidget(holder, 1)
        cap = QtWidgets.QLabel(title)
        cap.setObjectName("RibbonCap")
        cap.setAlignment(QtCore.Qt.AlignCenter)
        cap.setStyleSheet("font-size:8pt; border:none;")
        v.addWidget(cap)
        return box

    @staticmethod
    def _vdiv() -> QtWidgets.QWidget:
        f = QtWidgets.QFrame()
        f.setObjectName("RibbonDiv")
        f.setFixedWidth(1)
        f.setContentsMargins(0, 8, 0, 8)
        return f

    def _ribbon_page(self, groups: list[QtWidgets.QWidget]) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        page.setObjectName("RibbonPage")
        h = QtWidgets.QHBoxLayout(page)
        h.setContentsMargins(6, 3, 6, 3)
        h.setSpacing(2)
        for i, g in enumerate(groups):
            if i:
                h.addWidget(self._vdiv())
            h.addWidget(g)
        h.addStretch(1)
        return page

    def _build_ribbon(self) -> None:
        # Actions (reused across ribbon tabs).
        self._act_folder = self._act("📁\n폴더", self._open_folder, "폴더 열기")
        self._act_file = self._act("📂\n파일", self._open_file, "파일 열기")
        self._act_shot = self._act(
            "📷\n스크린샷", self._screenshot, "PNG 저장 +클립보드"
        )
        self._act_reset = self._act("⤢\n기본 줌", self._do_reset, "전체 보기 복귀")
        self._act_clear = self._act(
            "🧹\n초기화", self._on_clear_fit, "측정/피팅 초기화"
        )
        self._act_autolevel = self._act(
            "📊\nAuto", self._do_autoscale, "Auto 레벨 0.5–99.5%"
        )
        self._act_fit = self._act("화면 맞춤", self._do_reset, "Fit to Window")

        # Tool actions (exclusive).
        self._tool_group = QtGui.QActionGroup(self)
        self._tool_group.setExclusive(True)
        tools = [
            ("select", "⬉\n선택", "선택/이동: ROI 클릭 선택·드래그, ESC로 복귀"),
            ("pan", "✋\n이동", "손바닥: 좌드래그 이동"),
            ("zoom", "🔍\n확대", "박스 드래그 / 스크롤 줌"),
            ("distance", "📏\n거리", "점 찍어 구간 거리 (링 간격)"),
            ("line", "〰\n라인", "빈 곳 클릭 → 라인 생성, 드래그로 프로파일"),
            ("ellipse", "⬭\n타원 피팅", "점 찍어 타원 피팅 (우측 패널에서 Fit)"),
            ("rect", "▭\n구역", "빈 곳 클릭 → 사각 ROI 구역 생성"),
        ]
        self._tool_actions: dict[str, QtGui.QAction] = {}
        for name, label, tip in tools:
            act = QtGui.QAction(label, self, checkable=True)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, n=name: self._set_tool(n))
            self._tool_group.addAction(act)
            self._tool_actions[name] = act
        self._tool_actions["select"].setChecked(True)

        # PNG icons (theme-tinted)
        self._act_folder.setText("폴더")
        self._set_action_icon(self._act_folder, AppIcons.FOLDER)
        self._act_shot.setText("스크린샷")
        self._set_action_icon(self._act_shot, AppIcons.CAMERA)
        self._act_reset.setText("기본 줌")
        self._set_action_icon(self._act_reset, AppIcons.DEFAULT_ZOOM)
        self._set_action_icon(self._act_fit, AppIcons.DEFAULT_ZOOM)

        for tname, (lbl, icn) in {
            "pan": ("이동", AppIcons.HAND),
            "zoom": ("확대", AppIcons.ZOOM_IN),
            "distance": ("거리", AppIcons.RULER),
            "line": ("라인", AppIcons.LINE),
            "ellipse": ("타원 피팅", AppIcons.OVAL),
        }.items():
            self._tool_actions[tname].setText(lbl)
            self._set_action_icon(self._tool_actions[tname], icn)

        # ESC always returns to Select mode
        esc = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape), self)
        esc.activated.connect(self._tool_actions["select"].trigger)
        # Delete removes selected ROI
        dsc = QtGui.QShortcut(QtGui.QKeySequence.Delete, self)
        dsc.activated.connect(self._delete_selected_roi)
        self._install_shortcuts()

        # Scan / Det selectors.
        self._scan_combo = QtWidgets.QComboBox()
        self._scan_combo.setMinimumWidth(120)
        self._scan_combo.currentIndexChanged.connect(self._on_frame_selected)
        self._det_combo = QtWidgets.QComboBox()
        self._det_combo.setMinimumWidth(120)
        self._det_combo.currentIndexChanged.connect(self._on_frame_selected)

        # Panel-visibility toggles
        tog_file = self._file_dock.toggleViewAction()
        tog_file.setText("📂\n좌측 패널")
        tog_ctrl = self._control_dock.toggleViewAction()
        tog_ctrl.setText("🎛\n우측 속성창")
        tog_ana = self._analysis_dock.toggleViewAction()
        tog_ana.setText("📉\n하단 프로파일")

        # View-control actions.
        self._act_zoom100 = self._act("💯\n100%", self._do_zoom100, "100% 확대")
        self._grid_chk_act = QtGui.QAction("▦\nGrid", self, checkable=True)
        self._grid_chk_act.setToolTip("눈금(Grid) 표시 On/Off")
        self._grid_chk_act.toggled.connect(self._do_grid)

        # Ribbon quick colormap
        self._ribbon_cmap = QtWidgets.QComboBox()
        self._ribbon_cmap.setIconSize(QtCore.QSize(72, 12))
        for name in COLORMAPS:
            self._ribbon_cmap.addItem(self._cmap_icon(name, 72, 12), name)
        self._cmap_syncing = False
        self._ribbon_cmap.currentTextChanged.connect(self._on_ribbon_cmap)

        ribbon = QtWidgets.QTabWidget()
        ribbon.setObjectName("Ribbon")
        ribbon.setFixedHeight(140)
        ribbon.setDocumentMode(True)

        # Home
        g_file = self._ribbon_group(
            "파일 관리",
            self._row(
                self._rbtn(self._act_folder),
                self._rbtn(self._act_file),
                self._rbtn(self._act_shot),
            ),
        )
        g_frame = self._ribbon_group("프레임", self._frame_row())
        g_edit = self._ribbon_group(
            "편집", self._row(self._rbtn(self._act_reset), self._rbtn(self._act_clear))
        )
        ribbon.addTab(self._ribbon_page([g_file, g_frame, g_edit]), "홈")

        # Analyze
        g_meas = self._ribbon_group(
            "측정 / 피팅 도구",
            self._row(
                self._rbtn(self._tool_actions["distance"]),
                self._rbtn(self._tool_actions["line"]),
                self._rbtn(self._tool_actions["ellipse"]),
                self._rbtn(self._tool_actions["rect"]),
            ),
        )
        ribbon.addTab(self._ribbon_page([g_meas]), "분석")

        # Data / Table — table is a first-class feature, not just a fit sink.
        self._act_show_table = self._act(
            "표 보기", self._show_results_table, "결과 표 창 열기"
        )
        self._act_new_row = self._act(
            "빈 줄 추가", self._new_table_row, "빈 줄 추가 후 직접 입력"
        )
        self._act_populate = self._act(
            "파일 목록 불러오기",
            self._populate_shots,
            "현재 파일의 프레임마다 한 줄씩 생성",
        )
        self._act_exclude = self._act(
            "제외 표시", self._toggle_exclude, "선택한 줄 제외/포함 전환"
        )
        self._act_del_row = self._act(
            "줄 삭제", self._del_selected_row, "선택한 줄 삭제"
        )
        self._act_clear_table = self._act(
            "전체 비우기", self._clear_table, "모든 줄 삭제"
        )
        self._act_import_csv = self._act(
            "CSV 불러오기", self._import_csv, "CSV 파일 → 표"
        )
        self._act_export_csv = self._act("CSV 저장", self._export_csv, "표 → CSV 파일")
        self._set_action_icon(self._act_show_table, AppIcons.FILE)
        self._set_action_icon(self._act_new_row, AppIcons.CHECK)
        self._set_action_icon(self._act_import_csv, AppIcons.FOLDER)
        self._set_action_icon(self._act_export_csv, AppIcons.DOWNLOAD)
        self._set_action_icon(self._act_exclude, AppIcons.WARNING)
        g_tbl = self._ribbon_group(
            "결과 표",
            self._row(
                self._rbtn(self._act_show_table),
                self._rbtn(self._act_new_row),
                self._rbtn(self._act_populate),
            ),
        )
        g_clean = self._ribbon_group(
            "정리",
            self._row(
                self._rbtn(self._act_exclude),
                self._rbtn(self._act_del_row),
                self._rbtn(self._act_clear_table),
            ),
        )
        g_io = self._ribbon_group(
            "가져오기 / 내보내기",
            self._row(
                self._rbtn(self._act_import_csv),
                self._rbtn(self._act_export_csv),
            ),
        )
        ribbon.addTab(self._ribbon_page([g_tbl, g_clean, g_io]), "데이터")

        # View
        g_panels = self._ribbon_group(
            "패널 표시",
            self._row(
                self._toggle_btn(tog_file),
                self._toggle_btn(tog_ctrl),
                self._toggle_btn(tog_ana),
            ),
        )
        cmap_holder = QtWidgets.QVBoxLayout()
        cmap_holder.setContentsMargins(0, 0, 0, 0)
        cmap_holder.addWidget(self._ribbon_cmap)
        cmap_holder.addWidget(
            QtWidgets.QLabel("Colormap", alignment=QtCore.Qt.AlignCenter)
        )
        disp_row = self._row(
            self._rbtn(self._act_autolevel), self._toggle_btn(self._grid_chk_act)
        )
        disp_row.addLayout(cmap_holder)
        g_disp = self._ribbon_group("디스플레이", disp_row)
        g_viewport = self._ribbon_group(
            "뷰 포트",
            self._row(self._rbtn(self._act_fit), self._rbtn(self._act_zoom100)),
        )
        ribbon.addTab(self._ribbon_page([g_panels, g_disp, g_viewport]), "보기 (View)")

        # Tools
        g_tools = self._ribbon_group(
            "탐색 / 선택",
            self._row(
                self._rbtn(self._tool_actions["select"]),
                self._rbtn(self._tool_actions["pan"]),
                self._rbtn(self._tool_actions["zoom"]),
            ),
        )
        ribbon.addTab(self._ribbon_page([g_tools]), "도구")

        # Quick-access (top-left)
        qa = QtWidgets.QWidget()
        qh = QtWidgets.QHBoxLayout(qa)
        qh.setContentsMargins(6, 0, 6, 0)
        qh.setSpacing(1)
        brand = QtWidgets.QLabel()
        brand.setPixmap(logo_pixmap(22))
        brand.setToolTip(APP_NAME)
        qh.addWidget(brand)
        qh.addWidget(self._qsep())

        qh.addWidget(self._quick_btn(AppIcons.FOLDER, self._open_file, "파일 열기"))
        qh.addWidget(self._quick_btn(AppIcons.CAMERA, self._screenshot, "스크린샷"))
        qh.addWidget(self._qsep())
        qh.addWidget(
            self._quick_btn(AppIcons.PAN, lambda: self._set_tool("pan"), "이동 도구")
        )
        qh.addWidget(
            self._quick_btn(
                AppIcons.ZOOM_OUT,
                lambda: self._cur_view() and self._cur_view().zoom_out(),
                "축소",
            )
        )
        qh.addWidget(
            self._quick_btn(
                AppIcons.ZOOM_IN,
                lambda: self._cur_view() and self._cur_view().zoom_in(),
                "확대",
            )
        )
        qh.addWidget(
            self._quick_btn(AppIcons.DEFAULT_ZOOM, self._do_reset, "화면에 맞춤")
        )

        glob = QtWidgets.QWidget()
        gh = QtWidgets.QHBoxLayout(glob)
        gh.setContentsMargins(6, 0, 6, 0)
        gh.setSpacing(4)
        gh.addWidget(QtWidgets.QLabel("🌐"))
        self._lang_combo = QtWidgets.QComboBox()
        self._lang_combo.addItems(["KO", "EN"])
        self._lang_combo.setCurrentText(
            self._settings.value("lang_short", "KO", type=str)
        )
        self._lang_combo.currentTextChanged.connect(
            lambda s: self._settings.setValue("lang_short", s)
        )
        gh.addWidget(self._lang_combo)
        act_set = self._mini(self._act("⚙", self._open_settings, "환경설정"))
        gh.addWidget(act_set)
        ribbon.setCornerWidget(qa, QtCore.Qt.TopLeftCorner)
        ribbon.setCornerWidget(glob, QtCore.Qt.TopRightCorner)

        self.setMenuWidget(ribbon)

    @staticmethod
    def _row(*widgets) -> QtWidgets.QHBoxLayout:
        h = QtWidgets.QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        for wd in widgets:
            h.addWidget(wd)
        return h

    def _frame_row(self) -> QtWidgets.QVBoxLayout:
        v = QtWidgets.QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        r1 = QtWidgets.QHBoxLayout()
        r1.addWidget(QtWidgets.QLabel("Scan"))
        r1.addWidget(self._scan_combo)
        r2 = QtWidgets.QHBoxLayout()
        r2.addWidget(QtWidgets.QLabel(" Det"))
        r2.addWidget(self._det_combo)
        v.addLayout(r1)
        v.addLayout(r2)
        return v

    def _toggle_btn(self, action) -> QtWidgets.QToolButton:
        b = QtWidgets.QToolButton()
        b.setDefaultAction(action)
        b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        b.setCheckable(True)
        b.setAutoRaise(True)
        b.setProperty("class", "RibbonBtn")
        b.setMinimumWidth(62)
        b.setMinimumHeight(62)
        return b

    def _mini(self, action) -> QtWidgets.QToolButton:
        b = QtWidgets.QToolButton()
        b.setDefaultAction(action)
        b.setAutoRaise(True)
        return b

    def _quick_btn(self, icon_name: str, slot, tip: str) -> QtWidgets.QToolButton:
        b = QtWidgets.QToolButton()
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        self._icon_buttons[b] = icon_name
        b.setIcon(AppIcons.get(icon_name, self._icon_color))
        b.setIconSize(QtCore.QSize(18, 18))
        return b

    @staticmethod
    def _qsep() -> QtWidgets.QFrame:
        f = QtWidgets.QFrame()
        f.setObjectName("QSep")
        f.setFixedWidth(1)
        return f

    _TOOL_PAGE: ClassVar[dict[str, tuple[str, str]]] = {
        "select": ("view", "선택 / 이동"),
        "pan": ("view", "이동 / 확대"),
        "zoom": ("view", "이동 / 확대"),
        "distance": ("distance", "거리 측정"),
        "line": ("line", "라인 프로파일"),
        "ellipse": ("ellipse", "타원 피팅 (Ellipse Fit)"),
        "rect": ("view", "사각 ROI 구역"),
    }

    def _set_tool(self, name: str) -> None:
        self._current_tool = name
        if v := self._cur_view():
            v.set_tool(name)
        if (p := self._cur_prefs()) is not None and p.tool != name:
            self._edit_prefs(tool=name)
            self._log(f"도구: {name}")
        page_key, title = self._TOOL_PAGE.get(name, ("view", "도구 옵션"))
        self._tool_stack.setCurrentWidget(self._stack_pages[page_key])
        self._tool_title.setText(title)
        # The bottom profile plot only makes sense for the line tool.
        if name == "line":
            self._analysis_dock.show()
        else:
            self._analysis_dock.hide()

    #: (key sequence, handler name, what it does) — also the help table's source.
    SHORTCUTS: ClassVar[tuple[tuple[str, str, str], ...]] = (
        ("Ctrl+O", "_open_file", "파일 열기"),
        ("Ctrl+Shift+O", "_open_folder", "폴더 열기"),
        ("Ctrl+W", "_close_current_tab", "탭 닫기"),
        ("Ctrl+S", "_export_processed", "처리된 이미지 저장"),
        ("Ctrl+Shift+S", "_export_csv", "결과 표 CSV 저장"),
        ("Ctrl+Tab", "_next_tab", "다음 탭"),
        ("Ctrl+Shift+Tab", "_prev_tab", "이전 탭"),
        ("Ctrl+0", "_do_reset", "화면에 맞춤"),
        ("Ctrl+1", "_do_zoom100", "100% 줌"),
        ("Ctrl++", "_zoom_in", "확대"),
        ("Ctrl+=", "_zoom_in", "확대 (= 키)"),
        ("Ctrl+-", "_zoom_out", "축소"),
    )

    def _install_shortcuts(self) -> None:
        for keys, handler, _label in self.SHORTCUTS:
            sc = QtGui.QShortcut(QtGui.QKeySequence(keys), self)
            sc.activated.connect(getattr(self, handler))

    def _zoom_in(self) -> None:
        if v := self._cur_view():
            v.zoom_in()

    def _zoom_out(self) -> None:
        if v := self._cur_view():
            v.zoom_out()

    def _close_current_tab(self) -> None:
        if self._tabs.count():
            self._on_tab_close(self._tabs.currentIndex())

    def _step_tab(self, delta: int) -> None:
        n = self._tabs.count()
        if n > 1:
            self._tabs.setCurrentIndex((self._tabs.currentIndex() + delta) % n)

    def _next_tab(self) -> None:
        self._step_tab(1)

    def _prev_tab(self) -> None:
        self._step_tab(-1)
