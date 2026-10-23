"""Results table, shot inspector and ribbon-driven data table."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import ClassVar

from PySide6 import QtCore, QtWidgets

from ..core import io
from ..core.results import MASTER_COLUMNS, ResultsFrame
from .icons import AppIcons
from .models import COLUMN_LABELS
from .results_window import DropTableView, ResultsWindow

logger = logging.getLogger(__name__)


class ResultsTableMixin:
    """Results table, shot inspector and ribbon-driven data table."""

    # ----------------------------------------------------- results table
    def _build_results_table_widget(self) -> None:
        """The QTableView itself (hosted later by the standalone ResultsWindow)."""
        self._results_table = DropTableView()
        self._results_table.setModel(self._master)
        self._results_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._results_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self._results_table.horizontalHeader().setStretchLastSection(True)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.setSortingEnabled(False)
        # Phase 2: single click a row -> switch to that shot (double-click edits).
        self._results_table.clicked.connect(self._on_result_row_clicked)
        # Drag files from the sidebar / OS onto the table -> auto rows.
        self._results_table.filesDropped.connect(self._add_dropped_files)
        self._results_window = None

    # ------------------------------------------------- Phase 2: shot ↔ row
    def _shot_id_for_frame(self, path: Path, frame) -> str:
        return f"{Path(path).stem}:{frame}"

    def _register_shot(self, doc) -> None:
        """Remember how to reload a shot_id (file + frame) for row-click nav."""
        if doc is None or doc.ds is None or doc.frame is None:
            return
        self._shot_map[doc.ds.meta["shot_id"]] = (doc.file_path, doc.frame)

    def _populate_shots(self) -> None:
        """One pending row per detector frame in the current h5."""
        doc = self._cur()
        if doc is None or not doc.frames:
            self._status.showMessage("프레임이 있는 HDF5를 먼저 여세요", 4000)
            return
        added = 0
        for f in doc.frames:
            sid = self._shot_id_for_frame(doc.file_path, f)
            self._shot_map[sid] = (doc.file_path, f)
            if self._master.index_of(sid) is None:
                self._master.add_row({"shot_id": sid, "status": "대기"})
                added += 1
        self._show_results_table()
        self._results_table.resizeColumnsToContents()
        self._log(f"샷 목록 채움: {added}개 추가 (총 {self._master.rowCount()})")

    def _on_result_row_clicked(self, index: QtCore.QModelIndex) -> None:
        if not index.isValid():
            return
        sid = self._master.shot_id_at(index.row())
        if sid:
            self._goto_shot(str(sid))

    def _goto_shot(self, shot_id: str) -> None:
        if (entry := self._shot_map.get(shot_id)) is None:
            self._status.showMessage(f"샷 매핑 없음: {shot_id}", 4000)
            return
        path, frame = entry
        self._open_document(path)  # opens or switches to the tab
        doc = self._cur()
        if doc is None or frame is None:
            return
        with (
            QtCore.QSignalBlocker(self._scan_combo),
            QtCore.QSignalBlocker(self._det_combo),
        ):
            self._scan_combo.setCurrentText(frame.scan)
            self._populate_dets(frame.scan)
            self._det_combo.setCurrentText(frame.detector)
        self._on_frame_selected()

    def _toggle_exclude(self) -> None:
        sel = self._results_table.selectionModel()
        if sel is None or not sel.selectedRows():
            self._status.showMessage("행을 선택하세요", 3000)
            return
        r = sel.selectedRows()[0].row()
        cur = str(self._master.status_at(r) or "")
        new = "OK" if cur == "EXCLUDE" else "EXCLUDE"
        self._master.set_status(r, new)
        self._log(f"상태 변경: 행 {r + 1} → {new}")

    # ------------------------------------------- shot inspector (sidebar)
    _INSP_HINT_COLS: ClassVar[set[str]] = {
        "center_x",
        "center_y",
        "major_axis",
        "minor_axis",
        "angle_deg",
        "fit_error",
        "points_json",
    }

    def _build_shot_inspector(self) -> QtWidgets.QWidget:
        """Editable key/value view of the CURRENT shot → commit as one table row."""
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)
        v.addWidget(QtWidgets.QLabel("현재 샷 정보 — 체크한 항목만 표에 담김"))

        self._insp = QtWidgets.QTableWidget(len(MASTER_COLUMNS), 2)
        self._insp.setHorizontalHeaderLabels(["항목", "값"])
        self._insp.verticalHeader().setVisible(False)
        self._insp.horizontalHeader().setStretchLastSection(True)
        self._insp.setColumnWidth(0, 96)
        self._insp.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.SelectedClicked
        )
        for i, key in enumerate(MASTER_COLUMNS):
            name = QtWidgets.QTableWidgetItem(COLUMN_LABELS.get(key, key))
            name.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            name.setCheckState(QtCore.Qt.Checked)
            name.setData(QtCore.Qt.UserRole, key)
            self._insp.setItem(i, 0, name)
            self._insp.setItem(i, 1, QtWidgets.QTableWidgetItem(""))
        v.addWidget(self._insp, 1)

        row = QtWidgets.QHBoxLayout()
        b_fill = QtWidgets.QPushButton("샷에서 채우기")
        b_fill.clicked.connect(self._inspector_fill)
        b_add = QtWidgets.QPushButton("표에 한 줄 추가")
        b_add.setIcon(AppIcons.get(AppIcons.CHECK, self._icon_color))
        b_add.clicked.connect(self._inspector_commit)
        row.addWidget(b_fill)
        row.addWidget(b_add)
        v.addLayout(row)
        return w

    def _inspector_fill(self) -> None:
        """Pull the current shot's derivable values into the inspector."""
        if not hasattr(self, "_insp"):
            return
        doc = self._cur()
        ds = doc.ds if doc else None
        for i, key in enumerate(MASTER_COLUMNS):
            name_it = self._insp.item(i, 0)
            val_it = self._insp.item(i, 1)
            text, present = "", False
            if ds is not None:
                text, present = self._shot_field(ds, key)
            val_it.setText(text)
            # keep identity/flags always ticked; tick derived fields only if real
            if key in self._INSP_HINT_COLS:
                name_it.setCheckState(
                    QtCore.Qt.Checked if present else QtCore.Qt.Unchecked
                )

    def _shot_field(self, ds, key: str) -> tuple[str, bool]:
        fit = ds.fit
        match key:
            case "shot_id":
                return str(ds.meta.get("shot_id", "")), True
            case "status":
                sid = ds.meta.get("shot_id", "")
                r = self._master.index_of(sid)
                cur = str(self._master.status_at(r)) if r is not None else ""
                return (cur or "OK" if fit else "대기"), True
            case "bg_applied":
                return ("Y" if ds.bg_applied else "N"), True
            case "log_scale":
                return ("Y" if ds.log_scale else "N"), True
            case "points_json":
                if fit:
                    return json.dumps(fit.points), True
                return "", False
            case _ if fit is not None:
                return f"{getattr(fit, key):.4g}", True
            case _:
                return "", False

    def _inspector_commit(self) -> None:
        """Build one row from the checked inspector fields and upsert it."""
        row: dict = {}
        for i, key in enumerate(MASTER_COLUMNS):
            if self._insp.item(i, 0).checkState() != QtCore.Qt.Checked:
                continue
            text = self._insp.item(i, 1).text().strip()
            if key in ("bg_applied", "log_scale"):
                row[key] = text.lower() in ("y", "true", "1", "yes")
            elif key in self._INSP_HINT_COLS - {"points_json"}:
                try:
                    row[key] = float(text) if text else None
                except ValueError:
                    self._status.showMessage(f"'{COLUMN_LABELS[key]}' 숫자 아님", 4000)
                    return
            else:
                row[key] = text
        if not row.get("shot_id"):
            self._status.showMessage("샷 이름(shot_id)은 필수입니다", 4000)
            return
        r, created = self._master.upsert_row(row)
        self._show_results_table()
        self._results_table.selectRow(r)
        self._log(f"샷 정보 → 표 {'추가' if created else '갱신'}: 행 {r + 1}")

    # ------------------------------------------- data table (ribbon-driven)
    def _show_results_table(self) -> None:
        """Open the standalone, resizable results-table window (lazy)."""
        if self._results_window is None:
            actions = [
                self._act_populate,
                self._act_new_row,
                None,
                self._act_exclude,
                self._act_del_row,
                self._act_clear_table,
                None,
                self._act_import_csv,
                self._act_export_csv,
            ]
            self._results_window = ResultsWindow(
                self._results_table, actions, self._settings, self
            )
        self._results_window.show_raise()

    def _add_dropped_files(self, paths: list) -> None:
        """Files dragged onto the table → basic-info rows (filename/frames)."""
        added = 0
        unreadable: list[str] = []
        for raw in paths:
            p = Path(raw)
            if p.is_dir() or p.suffix.lower() not in self._SUPPORTED:
                continue
            if p.suffix.lower() in io.H5_SUFFIXES:
                # one row per detector frame in the h5
                try:
                    frames = io.list_frames(p)
                except OSError as exc:
                    logger.warning("cannot read %s: %s", p, exc)
                    self._log(f"드롭 실패: {p.name} — {exc}")
                    unreadable.append(p.name)
                    continue
                if frames:
                    for f in frames:
                        sid = self._shot_id_for_frame(p, f)
                        self._shot_map[sid] = (p, f)
                        if self._master.index_of(sid) is None:
                            self._master.add_row({"shot_id": sid, "status": "대기"})
                            added += 1
                    continue
            # image file (or frame-less h5): one row keyed by filename
            sid = p.stem
            self._shot_map[sid] = (p, None)
            if self._master.index_of(sid) is None:
                self._master.add_row({"shot_id": sid, "status": "대기"})
                added += 1
        self._results_table.resizeColumnsToContents()
        self._log(f"드롭 → {added}개 행 추가")
        if unreadable:
            self._status.showMessage(
                f"읽을 수 없는 h5 {len(unreadable)}개 건너뜀: {', '.join(unreadable)}",
                8000,
            )
        else:
            self._status.showMessage(f"드롭한 파일에서 {added}개 행 추가", 4000)

    def _new_table_row(self) -> None:
        """Append a blank row for manual data entry (cells are editable)."""
        self._show_results_table()
        r = self._master.add_row({"status": "manual"})
        self._results_table.selectRow(r)
        self._results_table.edit(self._master.index(r, 0))

    def _clear_table(self) -> None:
        if self._master.rowCount() == 0:
            return
        ok = QtWidgets.QMessageBox.question(
            self, "표 비우기", f"{self._master.rowCount()}개 행을 모두 삭제할까요?"
        )
        if ok == QtWidgets.QMessageBox.Yes:
            self._master.clear()
            self._log("결과 표 비움")

    def _import_csv(self) -> None:
        start = self._dialog_start_dir()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "CSV 불러오기", start, "CSV 파일 (*.csv)"
        )
        if not path:
            return
        try:
            self._master.set_results(ResultsFrame.from_csv(path))
        except Exception as exc:
            self._status.showMessage(f"CSV 불러오기 실패: {exc}", 6000)
            return
        self._show_results_table()
        self._results_table.resizeColumnsToContents()
        self._log(f"CSV 불러옴: {path} ({self._master.rowCount()}행)")

    def _del_selected_row(self) -> None:
        sel = self._results_table.selectionModel()
        if sel is None or not sel.selectedRows():
            return
        self._master.remove_row(sel.selectedRows()[0].row())

    def _export_processed(self) -> None:
        """Save the active tab's processed image: TIFF keeps the float data,
        PNG/JPG keeps what you see (colormap + levels)."""
        doc = self._cur()
        view = self._cur_view()
        if doc is None or view is None or not view.has_image():
            self._status.showMessage("먼저 이미지를 여세요.", 3000)
            return

        start = self._dialog_start_dir()
        default = str(Path(start) / f"{doc.file_path.stem}_processed.tif")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "처리된 이미지 저장",
            default,
            "TIFF - 원본 데이터 (*.tif *.tiff);;PNG - 보이는 대로 (*.png);;"
            "JPEG - 보이는 대로 (*.jpg)",
        )
        if not path:
            return

        try:
            if Path(path).suffix.lower() in (".tif", ".tiff"):
                img = doc.ds.image if doc.ds is not None else view.display_array()
                if img is None:
                    self._status.showMessage("저장할 이미지 없음", 4000)
                    return
                io.save_tif(img, path)
            else:
                view.save_display(path)
        except Exception as exc:
            self._status.showMessage(f"이미지 저장 실패: {exc}", 6000)
            return

        self._settings.setValue("last_dir", str(Path(path).parent))
        self._status.showMessage(f"이미지 저장: {path}", 5000)
        self._log(f"처리 이미지 내보내기: {path}")

    def _export_csv(self) -> None:
        if self._master.rowCount() == 0:
            self._status.showMessage("내보낼 데이터 없음", 4000)
            return
        start = self._dialog_start_dir()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "CSV 내보내기",
            str(Path(start) / "qoradfxm_results.csv"),
            "CSV 파일 (*.csv)",
        )
        if not path:
            return
        try:
            self._master.to_csv(path)
        except Exception as exc:
            self._status.showMessage(f"CSV 저장 실패: {exc}", 6000)
            return
        self._status.showMessage(f"CSV 저장: {path}", 5000)
        self._log(f"CSV 내보내기: {path}")
