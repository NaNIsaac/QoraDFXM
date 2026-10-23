"""File explorer dock: tree, name filter and context menu."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..core import io
from .icons import AppIcons
from .widgets import FilterEdit


class FileDockMixin:
    """File explorer dock: tree, name filter and context menu."""

    # --------------------------------------------------------- file dock
    def _build_file_dock(self) -> None:
        dock = self._file_dock = QtWidgets.QDockWidget("탐색기 (Explorer)", self)
        dock.setObjectName("FileDock")
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
        )
        tabs = QtWidgets.QTabWidget()

        self._fs_model = QtWidgets.QFileSystemModel()
        self._fs_model.setNameFilters(list(self._FILE_GLOBS))
        self._fs_model.setNameFilterDisables(False)
        self._fs_model.setRootPath("")

        self._tree = QtWidgets.QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setRootIndex(self._fs_model.index(""))
        for col in (1, 2, 3):  # hide size / type / date
            self._tree.hideColumn(col)
        self._tree.setHeaderHidden(True)
        self._tree.setDragEnabled(True)  # drag files onto the results table
        self._tree.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self._tree.clicked.connect(self._on_tree_preview)
        self._tree.doubleClicked.connect(self._on_tree_open)
        self._tree.activated.connect(self._on_tree_open)  # Enter = 확정 열기
        # Arrow keys move the preview with the selection (VS Code style), but
        # only while something IS previewing — see _on_tree_current_changed.
        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)  # coalesce a held-down arrow key
        self._preview_timer.timeout.connect(self._preview_current_tree_item)
        self._tree.selectionModel().currentChanged.connect(
            self._on_tree_current_changed
        )

        self._tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)

        tabs.addTab(self._build_files_page(), "파일")

        # HDF5 structure viewer
        self._struct_tree = QtWidgets.QTreeWidget()
        self._struct_tree.setColumnCount(4)
        self._struct_tree.setHeaderLabels(["이름", "종류", "shape", "dtype"])
        self._struct_tree.setAlternatingRowColors(True)
        self._struct_tree.itemDoubleClicked.connect(self._on_struct_activated)
        self._struct_tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._struct_tree.customContextMenuRequested.connect(
            self._on_struct_context_menu
        )
        tabs.addTab(self._struct_tree, "구조")

        tabs.addTab(self._build_object_tree(), "오브젝트")
        tabs.addTab(self._build_shot_inspector(), "샷 정보")

        dock.setWidget(tabs)
        dock.setMinimumWidth(280)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

    def _build_files_page(self) -> QtWidgets.QWidget:
        """The tree plus a filter box and a ".." row (the model has neither)."""
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._filter_edit = FilterEdit()
        self._filter_edit.escaped.connect(self._tree.setFocus)
        self._filter_edit.setPlaceholderText("이름 필터  (Ctrl+F)")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setToolTip(
            "현재 폴더에서 이름이 맞는 파일만 표시합니다 (Esc: 지우기)"
        )
        self._filter_edit.textChanged.connect(lambda _=None: self._filter_timer.start())
        lay.addWidget(self._filter_edit)

        # Typing is coalesced: each change re-evaluates the whole listing.
        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(120)
        self._filter_timer.timeout.connect(self._apply_name_filter)

        find = QtGui.QShortcut(QtGui.QKeySequence.Find, self)
        find.activated.connect(self._focus_filter)

        self._up_btn = QtWidgets.QToolButton()
        self._up_btn.setText("..")
        self._up_btn.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogToParent)
        )
        self._up_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._up_btn.setAutoRaise(True)
        self._up_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._up_btn.setStyleSheet(
            "QToolButton { text-align: left; padding: 4px 6px; }"
        )
        self._up_btn.clicked.connect(self._go_up_dir)
        lay.addWidget(self._up_btn)
        lay.addWidget(self._tree)

        # Backspace = go up. An event filter rather than a QShortcut: the tree
        # owns the key while it has focus, and it stays testable head-less.
        self._tree.installEventFilter(self)

        self._update_up_row()
        return page

    def eventFilter(self, obj, event) -> bool:
        if (
            obj is getattr(self, "_tree", None)
            and event.type() == QtCore.QEvent.KeyPress
            and event.key() == QtCore.Qt.Key_Backspace
        ):
            self._go_up_dir()
            return True
        if (
            obj is self._tabs.tabBar()
            and event.type() == QtCore.QEvent.MouseButtonRelease
            and event.button() == QtCore.Qt.MiddleButton
        ):
            index = obj.tabAt(event.position().toPoint())
            if index >= 0:
                self._on_tab_close(index)
                return True
        return super().eventFilter(obj, event)

    def _on_tab_context_menu(self, pos: QtCore.QPoint) -> None:
        bar = self._tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0:
            return
        doc = self._docs.get(self._tabs.widget(index))
        menu = QtWidgets.QMenu(self)
        menu.addAction("닫기", lambda: self._on_tab_close(index))
        menu.addAction("다른 탭 모두 닫기", lambda: self._close_other_tabs(index))
        menu.addAction("모두 닫기", self._close_all_tabs)
        if doc is not None:
            menu.addSeparator()
            path = doc.file_path
            menu.addAction(
                "경로 복사",
                lambda: QtWidgets.QApplication.clipboard().setText(str(path)),
            )
            menu.addAction(
                "탐색기에서 보기", lambda: self._reveal_in_file_manager(path)
            )
            menu.addAction(
                "이 폴더를 탐색기 루트로", lambda: self._set_tree_root(path.parent)
            )
        menu.exec(bar.mapToGlobal(pos))

    def _close_other_tabs(self, keep: int) -> None:
        keep_widget = self._tabs.widget(keep)
        for i in reversed(range(self._tabs.count())):
            if self._tabs.widget(i) is not keep_widget:
                self._on_tab_close(i)

    def _close_all_tabs(self) -> None:
        for i in reversed(range(self._tabs.count())):
            self._on_tab_close(i)

    # ------------------------------------------------------- 이름 필터
    def _focus_filter(self) -> None:
        self._file_dock.show()
        self._filter_edit.setFocus(QtCore.Qt.ShortcutFocusReason)
        self._filter_edit.selectAll()

    def _apply_name_filter(self) -> None:
        """Narrow the listing to names containing the typed text.

        QFileSystemModel filters on wildcards, so the text is folded into each
        supported-extension glob; folders always stay visible, which is what
        makes the filter usable while browsing.
        """
        text = self._filter_edit.text().strip()
        if not text:
            self._fs_model.setNameFilters(list(self._FILE_GLOBS))
            return
        stem = text.replace("*", "")
        self._fs_model.setNameFilters([f"*{stem}{glob}" for glob in self._FILE_GLOBS])

    def _tree_root(self) -> Path | None:
        """The folder the tree is rooted at, or None when showing every drive."""
        path = self._fs_model.filePath(self._tree.rootIndex())
        return Path(path) if path else None

    def _update_up_row(self) -> None:
        root = self._tree_root()
        self._up_btn.setEnabled(root is not None)
        self._up_btn.setToolTip(
            "상위 폴더로 (Backspace)"
            if root is None
            else f"상위 폴더로: {root.parent if root.parent != root else '드라이브 목록'}"
            "   (Backspace)"
        )

    def _go_up_dir(self) -> None:
        root = self._tree_root()
        if root is None:
            return  # already at the top: the whole filesystem is listed
        parent = root.parent
        if parent == root:  # C:\ etc — step out to the list of drives
            self._fs_model.setRootPath("")
            self._tree.setRootIndex(self._fs_model.index(""))
            self._update_up_row()
            return
        self._set_tree_root(parent)
        # Land on the folder we came out of, so the way back is one keypress.
        self._select_in_tree_when_loaded(root)
        self._settings.setValue("last_dir", str(parent))

    def _select_in_tree_when_loaded(self, path: Path) -> None:
        """Select a path, waiting for QFileSystemModel to populate if needed."""

        def select() -> bool:
            index = self._fs_model.index(str(path))
            if not index.isValid():
                return False
            self._tree.setCurrentIndex(index)
            self._tree.scrollTo(index)
            return True

        if select():
            return

        def on_loaded(loaded: str) -> None:
            if Path(loaded) == path.parent and select():
                self._fs_model.directoryLoaded.disconnect(on_loaded)

        self._fs_model.directoryLoaded.connect(on_loaded)

    # -------------------------------------------------- 파일 트리 컨텍스트 메뉴
    def _on_tree_context_menu(self, pos: QtCore.QPoint) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return

        file_path_str = self._fs_model.filePath(index)
        path = Path(file_path_str)

        menu = QtWidgets.QMenu(self)

        # 1. 파일 열기 (파일일 경우만)
        if path.is_file():
            icn_file = AppIcons.get(AppIcons.FILE, self._icon_color)
            act_open = menu.addAction(icn_file, "파일 열기")
            act_open.triggered.connect(lambda: self._open_document(path, preview=False))

            # 전처리 소스 지정 (이미지 파일만) — 현재 문서 체인에 추가
            if path.suffix.lower() in io.IMAGE_SUFFIXES:
                src = {"file_path": str(path)}
                a_dark = menu.addAction("→ Dark 소스로 빼기 추가")
                a_dark.triggered.connect(
                    lambda: self._preproc_add(self._cur(), "sub_bg", src)
                )
                a_flat = menu.addAction("→ Flat 소스로 나누기 추가")
                a_flat.triggered.connect(
                    lambda: self._preproc_add(self._cur(), "divide", src)
                )
            menu.addSeparator()

        # 2. 파일 탐색기에서 열기
        icn_folder = AppIcons.get(AppIcons.FOLDER, self._icon_color)
        act_explorer = menu.addAction(icn_folder, "파일 탐색기에서 열기")
        act_explorer.triggered.connect(lambda: self._show_in_file_manager(path))

        # 3. 경로 복사
        icn_copy = AppIcons.get(AppIcons.COPY, self._icon_color)
        act_copy_path = menu.addAction(icn_copy, "경로 복사")
        act_copy_path.triggered.connect(lambda: self._copy_path_to_clipboard(path))

        # 메뉴 출력
        menu.exec_(self._tree.viewport().mapToGlobal(pos))

    def _show_in_file_manager(self, path: Path) -> None:
        """시스템 파일 탐색기(Windows Explorer 등)에서 해당 파일/폴더를 엽니다."""
        abs_path = path.resolve()
        if abs_path.is_file():
            # Windows의 경우 파일 선택 상태로 탐색기 열기 지원
            import platform

            if platform.system() == "Windows":
                import subprocess

                subprocess.run(["explorer", "/select,", str(abs_path)], check=False)
                return
            target_url = QtCore.QUrl.fromLocalFile(str(abs_path.parent))
        else:
            target_url = QtCore.QUrl.fromLocalFile(str(abs_path))

        QtGui.QDesktopServices.openUrl(target_url)

    def _copy_path_to_clipboard(self, path: Path) -> None:
        """클립보드에 파일/폴더 절대 경로를 복사합니다."""
        abs_path = str(path.resolve())
        QtWidgets.QApplication.clipboard().setText(abs_path)
        self._status.showMessage(f"경로 복사됨: {abs_path}", 3000)
