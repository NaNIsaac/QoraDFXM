"""Small reusable widgets of the main window."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .icons import AppIcons


class CollapsibleSection(QtWidgets.QWidget):
    """A titled section whose body folds away when the header is clicked."""

    def __init__(self, title: str, body: QtWidgets.QWidget, expanded: bool = True):
        super().__init__()
        self._body = body
        self._header = QtWidgets.QToolButton()
        self._header.setText(f"  {title}")
        self._header.setCheckable(True)
        self._header.setChecked(expanded)
        self._header.setProperty("class", "SectionHeader")
        self._header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._header.setArrowType(
            QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow
        )
        self._header.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._header.toggled.connect(self._on_toggle)

        self._body.setObjectName("SectionBody")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(0)
        lay.addWidget(self._header)
        lay.addWidget(self._body)
        self._body.setVisible(expanded)

    def _on_toggle(self, on: bool) -> None:
        self._body.setVisible(on)
        self._header.setArrowType(QtCore.Qt.DownArrow if on else QtCore.Qt.RightArrow)


class DropOverlay(QtWidgets.QWidget):
    """Full-window translucent overlay shown while dragging files in."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0,0,0,0.65);")

        self._card = QtWidgets.QFrame()
        self._card.setObjectName("DropCard")

        self._icon_label = QtWidgets.QLabel()
        self._icon_label.setAlignment(QtCore.Qt.AlignCenter)

        self._text_label = QtWidgets.QLabel()
        self._text_label.setAlignment(QtCore.Qt.AlignCenter)

        card_lay = QtWidgets.QVBoxLayout(self._card)
        card_lay.setContentsMargins(60, 40, 60, 40)
        card_lay.setSpacing(16)
        card_lay.addWidget(self._icon_label, 0, QtCore.Qt.AlignCenter)
        card_lay.addWidget(self._text_label, 0, QtCore.Qt.AlignCenter)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addStretch(1)
        lay.addWidget(self._card, 0, QtCore.Qt.AlignCenter)
        lay.addStretch(1)
        self.hide()

    def set_ok(self, ok: bool) -> None:
        color_hex = "#4da3ff" if ok else "#ff5252"

        icon_key = AppIcons.DOWNLOAD if ok else AppIcons.WARNING
        pixmap = AppIcons.get_pixmap(icon_key, size=56, color=color_hex)
        self._icon_label.setPixmap(pixmap)

        if ok:
            text = (
                "<span style='font-size: 15pt; font-weight: bold; color: #ffffff;'>"
                "여기에 파일 또는 폴더를 떨어뜨리세요</span><br><br>"
                "<span style='font-size: 10pt; color: #b0b0b8;'>"
                "지원 형식: .h5  .tif  .png  .jpg  .json ...</span>"
            )
        else:
            text = (
                "<span style='font-size: 14pt; font-weight: bold; color: #ff5252;'>"
                "지원하지 않는 파일 형식입니다</span>"
            )
        self._text_label.setText(text)

        self._card.setStyleSheet(f"""
            QFrame#DropCard {{
                border: 2px dashed {color_hex};
                border-radius: 16px;
                background: rgba(30, 30, 35, 0.85);
            }}
        """)

    def cover(self) -> None:
        self.setGeometry(self.parent().rect())
        self.raise_()
        self.show()


class FilterEdit(QtWidgets.QLineEdit):
    """Explorer filter box: Escape clears it and hands focus back to the tree.

    The window binds Escape to "select tool", and a window-level shortcut wins
    over the focused widget — so the box has to claim the key first by
    accepting the ShortcutOverride, which is Qt's way of saying "this is mine
    while I have focus".
    """

    escaped = QtCore.Signal()

    def event(self, ev) -> bool:
        if (
            ev.type() == QtCore.QEvent.ShortcutOverride
            and ev.key() == QtCore.Qt.Key_Escape
        ):
            ev.accept()
            return True
        return super().event(ev)

    def keyPressEvent(self, event) -> None:
        if event.key() == QtCore.Qt.Key_Escape:
            self.clear()
            self.escaped.emit()
            return
        super().keyPressEvent(event)
