"""Document and tab system, file logic, fit logic and cursor readout."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..core import QoraDFXMDataset, io
from .document import DocumentSession
from .image_view import ImageView
from .prefs import ViewPrefs


class DocumentsMixin:
    """Document and tab system, file logic, fit logic and cursor readout."""

    # =================================================== document / tab system
    def _make_image_view(self) -> ImageView:
        v = ImageView()
        v.cursorMoved.connect(self._on_cursor)
        v.fitReported.connect(self._on_fit_reported)
        v.lineProfileChanged.connect(self._on_line_profile)
        v.distanceChanged.connect(self._on_distance)
        v.zoomChanged.connect(self._on_zoom_changed)
        v.histogramReattached.connect(self._sync_hist_chk)
        v.roiAdded.connect(self._on_roi_added)
        v.roiRemoved.connect(self._on_roi_removed)
        v.roiSelected.connect(self._on_roi_selected)
        v.lineDrawn.connect(self._on_line_drawn)
        v.rectDrawn.connect(self._on_rect_drawn)
        return v

    def _sync_hist_chk(self) -> None:
        v = self._cur_view()
        with QtCore.QSignalBlocker(self._hist_chk):
            if v is None:
                self._hist_chk.setEnabled(False)
            elif v.is_histogram_detached():
                self._hist_chk.setChecked(False)
                self._hist_chk.setEnabled(False)
            else:
                self._hist_chk.setEnabled(True)
                self._hist_chk.setChecked(v.histogram_visible())

    def _sync_panel_from(self, prefs: ViewPrefs) -> None:
        """Reflect a document's prefs in the shared control panel (no signals)."""
        widgets = [
            self._log_chk,
            self._overmax_chk,
            self._cmap_combo,
            self._scale_chk,
            self._px_size_spin,
            self._unit_combo,
        ]
        if hasattr(self, "_ribbon_cmap"):
            widgets.append(self._ribbon_cmap)
        blockers = [QtCore.QSignalBlocker(x) for x in widgets]
        doc = self._cur()
        # Log is Core state (an op in the recipe), never a copy kept here.
        self._log_chk.setChecked(bool(doc and doc.ds and doc.ds.log_scale))
        self._overmax_chk.setChecked(prefs.overmax)
        self._overmax_color = QtGui.QColor(prefs.overmax_color)
        self._update_overmax_btn_style()
        self._cmap_combo.setCurrentText(prefs.colormap)
        if hasattr(self, "_ribbon_cmap"):
            self._ribbon_cmap.setCurrentText(prefs.colormap)
        self._scale_chk.setChecked(prefs.scale_on)
        self._px_size_spin.setValue(prefs.px_size)
        self._unit_combo.setCurrentText(prefs.unit)
        del blockers
        if prefs.tool in self._tool_actions:
            self._tool_actions[prefs.tool].setChecked(True)

    def _cur_prefs(self) -> ViewPrefs | None:
        doc = self._cur()
        return doc.prefs if doc and doc.kind == "image" else None

    def _edit_prefs(self, **changes) -> ViewPrefs | None:
        """Change a display preference: the current document AND the default.

        A panel widget is not a store — it edits both scopes through here, so
        the active view, the document, and newly opened documents agree.
        """
        self._app_prefs = self._app_prefs.copy(**changes)
        self._app_prefs.save(self._settings)
        doc = self._cur()
        if doc is None or doc.kind != "image":
            return None
        doc.prefs = doc.prefs.copy(**changes)
        return doc.prefs

    def open_path(self, path: Path) -> None:
        """Public entry used by the launcher (``qoradfxm gui FILE ...``)."""
        self._open_document(Path(path))

    def _open_document(self, path: Path, preview: bool = False) -> None:
        path = Path(path)
        for w, d in self._docs.items():
            if d.file_path == path:
                if not preview and d.preview:
                    self._pin_tab(w)
                self._tabs.setCurrentWidget(w)
                return
        if preview:
            self._close_preview()
        suf = path.suffix.lower()
        try:
            if suf in io.H5_SUFFIXES:
                self._open_h5(path)
            elif suf in io.TEXT_SUFFIXES:
                self._open_text(path)
            elif suf in io.IMAGE_SUFFIXES:
                self._open_image_file(path)
            else:
                try:
                    self._open_image_file(path)
                except Exception:
                    self._open_text(path)
        except Exception as exc:
            self._status.showMessage(f"열기 실패: {path.name} — {exc}", 6000)
            return
        w = self._tabs.currentWidget()
        if w in self._docs:
            self._docs[w].preview = preview
            self._style_tab(w)
        if not self._under_temp(path):
            self._settings.setValue("last_file", str(path))
            self._settings.setValue("last_dir", str(path.parent))

    def _close_preview(self) -> None:
        for w, d in list(self._docs.items()):
            if d.preview:
                self._docs.pop(w, None)
                self._tabs.removeTab(self._tabs.indexOf(w))
                w.deleteLater()
                break

    def _pin_tab(self, w: QtWidgets.QWidget) -> None:
        if w in self._docs:
            self._docs[w].preview = False
            self._style_tab(w)

    def _reveal_in_tree(self, path: Path) -> None:
        """Scroll the file sidebar to the given file (matches the active tab)."""
        if self._suppress_reveal:
            return
        root_path = self._fs_model.filePath(self._tree.rootIndex())
        if root_path:
            try:
                path.relative_to(Path(root_path))
                inside = True
            except ValueError:
                inside = False
            if not inside:
                self._set_tree_root(path.parent)

        def do(retry: int = 0) -> None:
            idx = self._fs_model.index(str(path))
            if not idx.isValid():
                return
            self._tree.scrollTo(idx, QtWidgets.QAbstractItemView.PositionAtCenter)
            self._tree.setCurrentIndex(idx)
            if retry == 0:
                QtCore.QTimer.singleShot(150, lambda: do(1))

        do()

    def _style_tab(self, w: QtWidgets.QWidget) -> None:
        """Dim cue for preview tabs; normal for pinned."""
        i = self._tabs.indexOf(w)
        if i < 0 or w not in self._docs:
            return
        doc = self._docs[w]
        self._tabs.tabBar().setTabTextColor(
            i, QtGui.QColor("#8a8a8a") if doc.preview else QtGui.QColor("#e6e6e6")
        )
        self._tabs.setTabToolTip(
            i,
            f"{doc.file_path}\n(미리보기 — 더블클릭으로 고정)"
            if doc.preview
            else str(doc.file_path),
        )

    def _add_tab(
        self, widget: QtWidgets.QWidget, doc: DocumentSession, title: str
    ) -> None:
        self._docs[widget] = doc
        idx = self._tabs.addTab(widget, title)
        self._tabs.setTabToolTip(idx, str(doc.file_path))
        self._tabs.setCurrentWidget(widget)

    def _open_h5(self, path: Path) -> None:
        root = io.read_structure(path)
        frames = io.list_frames(path)
        view = self._make_image_view()
        doc = DocumentSession(
            file_path=path,
            kind="image",
            view=view,
            frames=frames,
            frame=frames[0] if frames else None,
            structure=root,
            info=path.name,
            prefs=self._new_doc_prefs(),
        )
        if frames:
            img = io.load_frame(path, frames[0])
            doc.ds = self._make_dataset(path, img, str(frames[0]))
            self._register_shot(doc)
            view.set_image(doc.ds.image)
            doc.info = self._img_info(path, str(frames[0]), img)
            doc.add_log(f"열기: {path.name} ({frames[0]})")
        else:
            view.show_error(
                "QoraDFXM 프레임 없음\n구조 탭에서 2D 데이터셋을 더블클릭하세요"
            )
            doc.add_log(f"열기: {path.name} (프레임 없음)")
        self._add_tab(view, doc, path.name)

    def _open_image_file(self, path: Path) -> None:
        img = io.load_image_file(path)
        view = self._make_image_view()
        doc = DocumentSession(
            file_path=path,
            kind="image",
            view=view,
            ds=self._make_dataset(path, img, ""),
            info=self._img_info(path, path.suffix.lstrip("."), img),
            prefs=self._new_doc_prefs(),
        )
        view.set_image(doc.ds.image)
        doc.add_log(f"열기: {path.name}  {img.shape[1]}×{img.shape[0]}")
        self._add_tab(view, doc, path.name)

    def _make_dataset(self, path, img, label: str):
        """Wrap a freshly loaded frame in a Core QoraDFXMDataset.

        Log scale is a display preference that spans files, but it is stored as
        an op in the per-document recipe — so a new document has to be given
        one, otherwise the checkbox would say Log while the image is linear.
        """
        stem = Path(path).stem
        shot = f"{stem}:{label}" if label else stem
        ds = QoraDFXMDataset.from_array(img, source_path=path, meta={"shot_id": shot})
        if getattr(self, "_log_chk", None) is not None and self._log_chk.isChecked():
            ds = ds.apply_log()
        return ds

    def _open_text(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".json":
            try:
                text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            except Exception:
                pass
        editor = QtWidgets.QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setFont(QtGui.QFont("Consolas", 10))
        editor.setPlainText(text)
        doc = DocumentSession(file_path=path, kind="text", info=path.name)
        doc.add_log(f"열기: {path.name} (텍스트)")
        self._add_tab(editor, doc, path.name)

    @staticmethod
    def _img_info(path: Path, sub: str, img) -> str:
        return (
            f"{path.name}  |  {sub}  |  {img.shape[1]}×{img.shape[0]}  |  "
            f"min {img.min():.3g}  max {img.max():.3g}"
        )

    def _on_tab_close(self, index: int) -> None:
        w = self._tabs.widget(index)
        self._docs.pop(w, None)
        self._tabs.removeTab(index)
        w.deleteLater()

    def _on_tab_changed(self, *_) -> None:
        doc = self._cur()
        self._refresh_log()
        if doc is None:
            self._update_window_title()
            self._info_label.setText("파일을 열어보세요")
            self._struct_tree.clear()
            with (
                QtCore.QSignalBlocker(self._scan_combo),
                QtCore.QSignalBlocker(self._det_combo),
            ):
                self._scan_combo.clear()
                self._det_combo.clear()
            return

        self._current_file = doc.file_path
        self._update_window_title()
        self._info_label.setText(doc.info or doc.file_path.name)
        self._reveal_in_tree(doc.file_path)

        if doc.kind != "image":
            self._struct_tree.clear()
            with (
                QtCore.QSignalBlocker(self._scan_combo),
                QtCore.QSignalBlocker(self._det_combo),
            ):
                self._scan_combo.clear()
                self._det_combo.clear()
            return

        if doc.structure is not None:
            self._populate_structure(doc.structure)
        else:
            self._struct_tree.clear()

        self._frames = doc.frames
        with (
            QtCore.QSignalBlocker(self._scan_combo),
            QtCore.QSignalBlocker(self._det_combo),
        ):
            self._scan_combo.clear()
            self._det_combo.clear()
            if doc.frames:
                self._scan_combo.addItems(sorted({f.scan for f in doc.frames}))
                cur = doc.frame
                if cur is not None:
                    self._scan_combo.setCurrentText(cur.scan)
                self._populate_dets(self._scan_combo.currentText())
                if cur is not None:
                    self._det_combo.setCurrentText(cur.detector)

        # Log is NOT mirrored here — it lives in doc.ds.history, and
        # _sync_panel_from reads the checkbox back from the recipe.
        self._sync_panel_from(doc.prefs)
        doc.prefs.apply_to(doc.view)
        self._sync_hist_chk()
        self._rebuild_object_tree()
        self._inspector_fill()

    def _screenshot(self) -> None:
        """Save image + scale bar + an info strip as PNG, and copy to clipboard."""
        view = self._cur_view()
        if view is None or not view.has_image():
            self._status.showMessage("먼저 이미지를 여세요.", 3000)
            return
        pix = view.grab()

        lo, hi = view.get_levels()
        scale_txt = (
            f"{self._px_size_spin.value():g} {self._unit_combo.currentText()}/px"
            if self._scale_chk.isChecked()
            else "pixel"
        )
        info = (
            f"{self._info_label.text()}   |   levels [{lo:.4g}, {hi:.4g}]"
            f"   |   scale: {scale_txt}"
        )

        strip_h = 30
        out = QtGui.QImage(
            pix.width(), pix.height() + strip_h, QtGui.QImage.Format_ARGB32
        )
        out.fill(QtGui.QColor("#232323"))
        p = QtGui.QPainter(out)
        p.drawPixmap(0, 0, pix)
        p.setPen(QtGui.QColor("#e6e6e6"))
        p.setFont(QtGui.QFont("Arial", 9))
        p.drawText(
            QtCore.QRect(10, pix.height(), pix.width() - 20, strip_h),
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft,
            info,
        )
        p.end()

        QtWidgets.QApplication.clipboard().setImage(out)

        default = "screenshot.png"
        if self._current_file is not None:
            default = f"{self._current_file.stem}_shot.png"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "스크린샷 저장", default, "PNG (*.png)"
        )
        if path:
            out.save(path)
            self._status.showMessage(f"저장됨(+클립보드 복사): {path}", 4000)
        else:
            self._status.showMessage("클립보드에 복사됨.", 3000)

    def _on_scale_changed(self, *_) -> None:
        prefs = self._edit_prefs(
            scale_on=self._scale_chk.isChecked(),
            px_size=self._px_size_spin.value(),
            unit=self._unit_combo.currentText(),
        )
        view = self._cur_view()
        if view is None or prefs is None:
            return
        if prefs.scale_on:
            view.set_scale(prefs.px_size, prefs.unit)
        else:
            view.set_scale_pixels()

    def _on_fit_reported(self, text: str) -> None:
        self._results.setPlainText(text)
        if text.startswith("ELLIPSE FIT RESULT"):
            self._log("타원 피팅 완료")

    # -------------------------------------------------------- file logic
    def _dialog_start_dir(self) -> str:
        start = self._settings.value("last_dir", "", type=str)
        if not start or not Path(start).is_dir():
            start = str(Path.home())
        return start

    def _open_folder(self) -> None:
        start = self._dialog_start_dir()
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "폴더 선택", start)
        if path:
            self._set_tree_root(Path(path))
            self._settings.setValue("last_dir", path)

    def _open_file(self) -> None:
        start = self._dialog_start_dir()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "파일 선택",
            start,
            "지원 파일 (*.h5 *.hdf5 *.tif *.tiff *.png *.jpg *.jpeg *.bmp *.json *.txt);;"
            "모든 파일 (*.*)",
        )
        if path:
            self._open_document(Path(path))

    def _tree_path(self, index: QtCore.QModelIndex) -> Path | None:
        path = Path(self._fs_model.filePath(index))
        if path.is_file() and path.suffix.lower() in self._SUPPORTED:
            return path
        return None

    def _on_tree_preview(self, index: QtCore.QModelIndex) -> None:
        if p := self._tree_path(index):
            # user clicked in the tree: item already visible, skip re-scroll
            self._suppress_reveal = True
            try:
                self._open_document(p, preview=True)
            finally:
                self._suppress_reveal = False

    def _has_preview_tab(self) -> bool:
        return any(d.preview for d in self._docs.values())

    def _on_tree_current_changed(self, current, _previous) -> None:
        """Keyboard navigation re-previews, but never opens on its own.

        If nothing is in preview (every tab pinned, or none open) moving the
        selection must stay silent — otherwise arrow keys would spam tabs.
        """
        if not self._has_preview_tab() or self._tree_path(current) is None:
            return
        self._preview_timer.start()

    def _preview_current_tree_item(self) -> None:
        p = self._tree_path(self._tree.currentIndex())
        if p is None or not self._has_preview_tab():
            return
        self._suppress_reveal = True
        try:
            self._open_document(p, preview=True)
        finally:
            self._suppress_reveal = False
        # Opening a document activates its tab; give the arrows back to the tree.
        self._tree.setFocus(QtCore.Qt.OtherFocusReason)

    def _on_tree_open(self, index: QtCore.QModelIndex) -> None:
        # A folder dives in: it becomes the tree root. The ">" chevron still
        # expands in place, so both ways of browsing stay available.
        folder = Path(self._fs_model.filePath(index))
        if self._fs_model.isDir(index):
            self._set_tree_root(folder)
            self._settings.setValue("last_dir", str(folder))
            return
        if p := self._tree_path(index):
            self._suppress_reveal = True
            try:
                self._open_document(p, preview=False)
            finally:
                self._suppress_reveal = False

    def _populate_structure(self, root: io.H5Node) -> None:
        self._struct_tree.clear()

        def add(parent, node: io.H5Node) -> None:
            if node.is_group:
                kind, shape, dtype = "group", "", ""
            else:
                kind, shape, dtype = "dataset", str(node.shape), node.dtype or ""
            item = QtWidgets.QTreeWidgetItem([node.name, kind, shape, dtype])
            item.setData(0, QtCore.Qt.UserRole, node)
            if node.attrs:
                tip = "\n".join(f"{k} = {v}" for k, v in node.attrs.items())
                item.setToolTip(0, tip)
            if parent is None:
                self._struct_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in node.children or []:
                add(item, child)

        for child in root.children or []:
            add(None, child)
        self._struct_tree.expandToDepth(1)
        for c in range(4):
            self._struct_tree.resizeColumnToContents(c)

    def _on_struct_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._struct_tree.itemAt(pos)
        if item is None:
            return
        node: io.H5Node | None = item.data(0, QtCore.Qt.UserRole)
        doc = self._cur()
        if node is None or node.is_group or doc is None or doc.kind != "image":
            return
        src = {"dataset_path": node.path}
        menu = QtWidgets.QMenu(self)
        menu.addAction(
            "→ Dark 소스로 빼기 추가",
            lambda: self._preproc_add(doc, "sub_bg", src),
        )
        menu.addAction(
            "→ Flat 소스로 나누기 추가",
            lambda: self._preproc_add(doc, "divide", src),
        )
        menu.exec(self._struct_tree.viewport().mapToGlobal(pos))

    def _on_struct_activated(self, item: QtWidgets.QTreeWidgetItem, _col: int) -> None:
        node: io.H5Node | None = item.data(0, QtCore.Qt.UserRole)
        doc = self._cur()
        if node is None or node.is_group or doc is None or doc.kind != "image":
            return
        try:
            img = io.load_dataset(doc.file_path, node.path)
        except Exception as exc:
            self._status.showMessage(f"이 데이터셋은 2D로 볼 수 없음: {exc}", 5000)
            return
        doc.ds = self._make_dataset(doc.file_path, img, node.path)
        doc.view.set_image(doc.ds.image)
        doc.frame = None
        doc.info = self._img_info(doc.file_path, node.path, img)
        doc.prefs.apply_to(doc.view)
        self._pin_tab(self._tabs.currentWidget())
        self._rebuild_object_tree()
        doc.add_log(f"데이터셋 열기: {node.path}")
        self._refresh_log()
        self._info_label.setText(doc.info)

    def _populate_dets(self, scan: str) -> None:
        dets = [f.detector for f in self._frames if f.scan == scan]
        self._det_combo.clear()
        self._det_combo.addItems(dets)

    def _on_frame_selected(self, *_) -> None:
        doc = self._cur()
        if doc is None or doc.kind != "image" or not doc.frames:
            return
        scan = self._scan_combo.currentText()
        expected = [f.detector for f in doc.frames if f.scan == scan]
        if [
            self._det_combo.itemText(i) for i in range(self._det_combo.count())
        ] != expected:
            with QtCore.QSignalBlocker(self._det_combo):
                self._populate_dets(scan)
        det = self._det_combo.currentText()
        if not scan or not det:
            return
        frame = io.FramePath(scan=scan, detector=det)
        try:
            img = io.load_frame(doc.file_path, frame)
        except Exception as exc:
            self._status.showMessage(f"로드 실패: {exc}", 5000)
            return
        doc.ds = self._make_dataset(doc.file_path, img, str(frame))
        doc.frame = frame
        self._register_shot(doc)
        doc.view.set_image(doc.ds.image)
        doc.info = self._img_info(doc.file_path, str(frame), img)
        doc.prefs.apply_to(doc.view)
        self._pin_tab(self._tabs.currentWidget())
        self._rebuild_object_tree()
        doc.add_log(f"프레임 전환: {frame}")
        self._refresh_log()
        self._remember()
        self._info_label.setText(doc.info)
        self._results.clear()

    # --------------------------------------------------------- fit logic
    def _on_clear_fit(self) -> None:
        if v := self._cur_view():
            v.clear_fit()
            v.clear_distance()
        self._results.clear()

    def _save_fit(self) -> None:
        view = self._cur_view()
        if view is None:
            self._status.showMessage("이미지 탭이 아닙니다.", 3000)
            return
        geom = view.last_geometry()
        if geom is None:
            self._status.showMessage("저장할 피팅 결과 없음. 먼저 Fit 실행.", 4000)
            return
        default = "ellipse.json"
        if self._current_file is not None:
            default = f"{self._current_file.stem}_ellipse.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "피팅 결과 저장", default, "JSON (*.json);;텍스트 (*.txt)"
        )
        if not path:
            return
        payload = {
            "source_file": str(self._current_file) if self._current_file else None,
            "scan": self._scan_combo.currentText(),
            "detector": self._det_combo.currentText(),
            "points": view.picked_points().tolist(),
            "geometry": geom,
        }
        p = Path(path)
        if p.suffix.lower() == ".txt":
            p.write_text(self._results.toPlainText(), encoding="utf-8")
        else:
            p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._status.showMessage(f"저장됨: {p}", 4000)

    # ------------------------------------------------------------ cursor
    def _on_cursor(self, x: float, y: float, val: float) -> None:
        if np.isnan(val):
            self._pos_label.setText(f"커서:  x={x:.1f}  y={y:.1f}  (범위 밖)")
        else:
            self._pos_label.setText(f"커서:  x={x:.1f}  y={y:.1f}  값={val:.4g}")
