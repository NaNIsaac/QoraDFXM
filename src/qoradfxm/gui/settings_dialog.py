"""Preferences dialog."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .constants import APP_NAME, APP_VERSION
from .icons import wordmark_pixmap
from .image_view import COLORMAPS


class SettingsDialog(QtWidgets.QDialog):
    """Sidebar-tabbed preferences: General / Display / Shortcuts."""

    def __init__(self, parent, settings: QtCore.QSettings):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("환경설정")
        self.setMinimumSize(560, 420)

        nav = QtWidgets.QListWidget()
        nav.setFixedWidth(140)
        nav.addItems(["일반", "디스플레이", "단축키"])
        stack = QtWidgets.QStackedWidget()
        stack.addWidget(self._general_page())
        stack.addWidget(self._display_page())
        stack.addWidget(self._shortcuts_page())
        nav.currentRowChanged.connect(stack.setCurrentIndex)
        nav.setCurrentRow(0)

        body = QtWidgets.QHBoxLayout()
        body.addWidget(nav)
        body.addWidget(stack, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        root = QtWidgets.QVBoxLayout(self)
        root.addLayout(body, 1)
        root.addWidget(buttons)

    def _general_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(w)

        # Brand header: logo + name.
        brand = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        dark = self._settings.value("theme", "Dark", type=str) == "Dark"
        logo.setPixmap(wordmark_pixmap(72, on_dark=dark))  # room for the lockup here
        brand.addWidget(logo)
        title = QtWidgets.QLabel(
            f"<b style='font-size:15pt'>{APP_NAME}</b>"
            f"<br><span style='color:#888'>v{APP_VERSION}</span>"
        )
        brand.addWidget(title, 1)
        outer.addLayout(brand)
        outer.addSpacing(8)

        form_w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(form_w)
        outer.addWidget(form_w)
        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItems(["한국어 (KO)", "English (EN)"])
        self.lang_combo.setCurrentText(
            self._settings.value("lang", "한국어 (KO)", type=str)
        )
        self.lang_combo.currentTextChanged.connect(
            lambda s: self._settings.setValue("lang", s)
        )
        f.addRow("언어", self.lang_combo)

        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.setCurrentText(self._settings.value("theme", "Dark", type=str))
        _parent = self.parent()
        if hasattr(_parent, "apply_theme"):
            self.theme_combo.currentTextChanged.connect(_parent.apply_theme)
        f.addRow("테마", self.theme_combo)

        note = QtWidgets.QLabel("언어 전환은 설정 저장 후 반영 예정.")
        note.setStyleSheet("color:#888;")
        f.addRow(note)
        outer.addStretch(1)
        return w

    def _display_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(w)
        self.def_cmap = QtWidgets.QComboBox()
        self.def_cmap.addItems(COLORMAPS)
        self.def_cmap.setCurrentText(self._settings.value("def_cmap", "gray", type=str))
        f.addRow("기본 Colormap", self.def_cmap)
        self.def_unit = QtWidgets.QComboBox()
        self.def_unit.setEditable(True)
        self.def_unit.addItems(["µm", "nm", "mm", "Å"])
        self.def_unit.setCurrentText(self._settings.value("def_unit", "µm", type=str))
        f.addRow("기본 Scalebar 단위", self.def_unit)
        return w

    def _shortcuts_page(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        table = QtWidgets.QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["기능", "단축키"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().hide()
        rows = [
            ("이동(Select) 모드", "Esc"),
            ("기본 줌 복귀", "더블클릭"),
            ("점 삭제(가까운)", "우클릭"),
            ("스크린샷", "—"),
        ]
        table.setRowCount(len(rows))
        for i, (a, b) in enumerate(rows):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(a))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(b))
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        lay.addWidget(table)
        return w

    def result_values(self) -> dict:
        return {
            "lang": self.lang_combo.currentText(),
            "theme": self.theme_combo.currentText(),
            "def_cmap": self.def_cmap.currentText(),
            "def_unit": self.def_unit.currentText(),
        }
