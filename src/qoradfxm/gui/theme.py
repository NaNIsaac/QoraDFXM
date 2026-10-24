"""Qt style sheet built from the light and dark palettes."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .icons import AppIcons

_STYLE_TMPL = """
QMainWindow { background: %BASE%; }
QWidget { background: %WIDGET%; color: %TEXT%; font-size: 9pt; }
QToolTip { background: %SURF%; color: %TEXT%; border: 1px solid %BORDER2%; padding: 3px; }
QMenu { background: %SURF%; border: 1px solid %BORDER2%; }
QMenu::item:selected { background: %ACCBG%; }

QDockWidget { titlebar-close-icon: none; }
QDockWidget::title {
    background: %PANEL%; padding: 8px 12px; font-weight: bold; font-size: 9pt;
    color: %TEXT2%; border-bottom: 1px solid %BORDER%;
}

QGroupBox { border: 1px solid %BORDER%; border-radius: 6px; margin-top: 8px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: %DIM%; }

QPushButton { background: %BTN%; border: 1px solid %BORDER2%; border-radius: 5px; padding: 6px 11px; }
QPushButton:hover { background: %HOVER2%; border-color: %BORDER2%; }
QPushButton:pressed { background: %PANEL%; }

QTreeView, QTreeWidget, QTableWidget, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: %INPUT%; border: 1px solid %BORDER%; border-radius: 5px; padding: 3px;
    selection-background-color: %ACCBG%;
}
QComboBox::drop-down { border: none; width: 18px; }
QHeaderView::section { background: %SURF%; padding: 4px; border: none; color: %DIM%; }

QTabWidget::pane { border: 1px solid %BORDER%; border-radius: 6px; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: %PANEL%; color: %DIM%; padding: 6px 16px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    border: 1px solid transparent;
}
QTabBar::tab:hover { background: %HOVER%; color: %TEXT2%; }
QTabBar::tab:selected {
    background: %TABSEL%; color: %SELTEXT%; border-bottom: 2px solid %ACCENT%;
}

QStatusBar { background: %STATUSBG%; min-height: 24px; font-size: 8pt; color: %DIM%; }
QStatusBar { border-top: 1px solid %BORDER%; }
QStatusBar::item { border: none; }

QMainWindow::separator { background: %BORDER%; width: 4px; height: 4px; }
QMainWindow::separator:hover { background: %ACCENT%; }

QToolButton { border: 1px solid transparent; border-radius: 5px; padding: 3px 6px; color: %TEXT%; }
QToolButton:hover { background: %HOVER%; border-color: %BORDER2%; }
QToolButton:checked { background: %ACCBG%; color: %SELTEXT%; }
QScrollArea { border: 1px solid %BORDER%; }

QCheckBox {
    padding: 2px 0;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid %BORDER2%;
    border-radius: 3px;
    background: %INPUT%;
}

QCheckBox::indicator:hover {
    border-color: %ACCENT%;
}

QCheckBox::indicator:checked {
    width: 14px;
    height: 14px;
    background: %ACCENT%;
    border: 1px solid %ACCENT%;
    image: url("%CHECKMARK_ICON%");
    padding: 0px;
}
QLabel { background: transparent; }

QSlider::groove:horizontal { height: 4px; background: %HOVER2%; border-radius: 2px; }
QSlider::handle:horizontal { background: %ACCENT%; width: 12px; margin: -5px 0; border-radius: 6px; }

#Ribbon { background: %STATUSBG%; }
#Ribbon::pane { background: %RIBBON%; border: none; border-bottom: 1px solid %SHADOW%; }
#Ribbon QTabBar { background: %STATUSBG%; }
#Ribbon QTabBar::tab {
    background: transparent; color: %DIM%; padding: 7px 20px;
    margin: 0; border: 2px solid transparent;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}
#Ribbon QTabBar::tab:hover { color: %TEXT2%; background: %HOVER%; }
#Ribbon QTabBar::tab:selected {
    color: %SELTEXT%; background: %RIBBON%; border-top: 2px solid %ACCENT%;
    border-bottom: none;
}

.SectionHeader {
    background: %SURF%; border: none; border-left: 3px solid %ACCENT%;
    border-radius: 4px; padding: 6px 10px;
    text-align: left; font-weight: bold; color: %TEXT2%;
}
.SectionHeader:hover { background: %HOVER%; }

.RibbonBtn { background: transparent; border: 1px solid %TABSEL%; border-radius: 5px; }
.RibbonBtn:hover { background: %HOVER%; border-color: %BORDER2%; }
.RibbonBtn:checked { background: %ACCBG%; border-color: %ACCENT%; }
.RibbonBtn:pressed { background: %PANEL%; }

/* Theme-aware surfaces that used to be hard-coded (fixes Light mode) */
#RibbonPage { background: %RIBBON%; }
#RibbonGroupBox, #RibbonHolder { background: transparent; }
#SectionBody { border: 1px solid %BORDER%; border-top: none; border-radius: 0 0 5px 5px; }
QFrame#RibbonDiv { background: %BORDER%; }
QFrame#QSep { background: %BORDER%; }
QLabel#RibbonCap { color: %DIM%; background: transparent; }
QDockWidget { border: 1px solid %BORDER%; }
"""

_PALETTES = {
    "Dark": {
        "BASE": "#1b1b1d",
        "WIDGET": "#232326",
        "PANEL": "#202024",
        "SURF": "#26262a",
        "RIBBON": "#252526",
        "INPUT": "#191919",
        "BORDER": "#303036",
        "BORDER2": "#3a3a42",
        "BTN": "#2e2e33",
        "HOVER": "#2c2c32",
        "HOVER2": "#38383e",
        "TEXT": "#e4e4e7",
        "TEXT2": "#d4d4d8",
        "DIM": "#9a9aa2",
        "ACCBG": "#234844",
        "SELTEXT": "#ffffff",
        "STATUSBG": "#1a1a1d",
        "TABSEL": "#2b2b31",
        "SHADOW": "#141416",
        "ACCENT": "#00e5ff",
    },
    "Light": {
        "BASE": "#e5e5ea",
        "WIDGET": "#f1f1f4",
        "PANEL": "#e2e2e8",
        "SURF": "#ececef",
        "RIBBON": "#f7f7f9",
        "INPUT": "#ffffff",
        "BORDER": "#c6c6cf",
        "BORDER2": "#b2b2bd",
        "BTN": "#e9e9ef",
        "HOVER": "#dcdce3",
        "HOVER2": "#d2d2da",
        "TEXT": "#1c1c22",
        "TEXT2": "#2a2a32",
        "DIM": "#6a6a74",
        "ACCBG": "#c9edf3",
        "SELTEXT": "#0b1113",
        "STATUSBG": "#dcdce2",
        "TABSEL": "#f7f7f9",
        "SHADOW": "#b6b6be",
        "ACCENT": "#0891b2",
    },
}


def build_style(theme: str) -> str:
    toks = _PALETTES.get(theme, _PALETTES["Dark"])
    s = _STYLE_TMPL
    for k, v in toks.items():
        s = s.replace("%" + k + "%", v)

    # QSS can only reference a file, so write the check-mark icon to a temp PNG
    check_pix = AppIcons.get_pixmap(AppIcons.CHECK, size=12, color="#ffffff")
    tmp_check_path = Path(tempfile.gettempdir()) / "qoradfxm_qta_check.png"
    check_pix.save(str(tmp_check_path))

    s = s.replace("%CHECKMARK_ICON%", str(tmp_check_path).replace("\\", "/"))
    return s
