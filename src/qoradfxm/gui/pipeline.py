"""Preprocessing chain, ROI handling and the pipeline object tree."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..core.history import History
from ..core.ops import GEOMETRIC_KINDS, CorrectionError
from .document import DocumentSession
from .roi import EllipseFitROI, LineProfileROI, RectRegionROI


class PipelineMixin:
    """Preprocessing chain, ROI handling and the pipeline object tree."""

    # The recipe is Core state: doc.ds.history (immutable). The sidebar object tree
    # shows and edits it; Dark/Flat sources come from the file tree's context menu.
    # The GUI performs NO pixel math — Core computes doc.ds.image.

    def _cur_preproc(self):
        doc = self._cur()
        return list(doc.ds.history) if (doc and doc.ds) else []

    def _preproc_add(self, doc, op_type: str, source: dict | None = None) -> None:
        """Append an op to a document's Core recipe. `source` carries the
        reference location ({"dataset_path": ...}/{"file_path": ...})."""
        if doc is None or doc.ds is None:
            self._status.showMessage("이미지 문서를 먼저 여세요", 4000)
            return
        if op_type in ("sub_bg", "divide") and not source:
            self._status.showMessage(
                "구조/파일 탭에서 소스를 우클릭해 지정하세요", 5000
            )
            return
        if not self._set_recipe(doc, doc.ds.add_op(op_type, **(source or {}))):
            return
        self._log(f"전처리 추가: {doc.ds.history[-1].label()}  [{doc.file_path.name}]")
        if op_type in GEOMETRIC_KINDS:
            # The pixel grid moved: anything picked on the old grid is stale.
            self._status.showMessage(
                "기하 변형 적용 — 좌표계가 바뀌었으니 ROI/타원피팅은 다시 지정하세요",
                6000,
            )
        self._after_preproc_change(doc)

    def _preproc_remove_at(self, doc, idx: int) -> None:
        if doc is None or doc.ds is None:
            return
        ops = list(doc.ds.history)
        if not 0 <= idx < len(ops):
            return
        del ops[idx]
        if self._set_recipe(doc, doc.ds.set_history(History(tuple(ops)))):
            self._after_preproc_change(doc)

    def _preproc_move_at(self, doc, idx: int, delta: int) -> None:
        if doc is None or doc.ds is None:
            return
        ops = list(doc.ds.history)
        j = idx + delta
        if not (0 <= idx < len(ops) and 0 <= j < len(ops)):
            return
        ops[idx], ops[j] = ops[j], ops[idx]
        if self._set_recipe(doc, doc.ds.set_history(History(tuple(ops)))):
            self._after_preproc_change(doc)

    def _set_recipe(self, doc, new_ds) -> bool:
        """Adopt ``new_ds`` only if Core can replay it. A dark/flat reference
        that is missing or the wrong shape keeps the previous recipe."""
        try:
            _ = new_ds.image
        except CorrectionError as exc:
            self._status.showMessage(f"전처리 실패: {exc}", 8000)
            self._log(f"전처리 실패: {exc}  [{doc.file_path.name}]")
            return False
        doc.ds = new_ds
        return True

    def _after_preproc_change(self, doc) -> None:
        """Push Core's recomputed image to the active view + refresh object tree
        and the Log checkbox (which is now driven by the recipe)."""
        if doc is self._cur() and doc.view is not None:
            doc.view.update_processed(doc.ds.image)
            with QtCore.QSignalBlocker(self._log_chk):
                self._log_chk.setChecked(doc.ds.log_scale)
            self._inspector_fill()
            self._ring_update()  # recipe changed → the measured image changed
        self._rebuild_object_tree()

    def _do_overmax(self, b) -> None:
        self._edit_prefs(overmax=bool(b))
        if v := self._cur_view():
            v.set_overmax(bool(b))

    def _do_colormap(self, name) -> None:
        self._edit_prefs(colormap=name)
        if v := self._cur_view():
            v.set_colormap(name)
        if not self._cmap_syncing and hasattr(self, "_ribbon_cmap"):
            self._cmap_syncing = True
            self._ribbon_cmap.setCurrentText(name)
            self._cmap_syncing = False

    def _on_ribbon_cmap(self, name) -> None:
        if self._cmap_syncing:
            return
        self._cmap_syncing = True
        self._cmap_combo.setCurrentText(name)  # drives _do_colormap
        self._cmap_syncing = False

    def _do_zoom100(self) -> None:
        if v := self._cur_view():
            v.set_zoom(100.0)

    def _do_grid(self, on) -> None:
        if v := self._cur_view():
            v.set_grid(on)

    def _do_autoscale(self) -> None:
        if v := self._cur_view():
            v.autoscale_levels()
            self._log("Auto 레벨")

    def _do_clear_distance(self) -> None:
        if v := self._cur_view():
            v.clear_distance()

    def _do_fit(self) -> None:
        v = self._cur_view()
        doc = self._cur()
        if v is None or doc is None:
            return
        geom = v.fit_ellipse()  # draws the static preview + returns geometry
        if geom is None:
            return
        pts = v.picked_points()
        # Delegate the fit to Core: record it on the dataset.
        if doc.ds is not None:
            doc.ds = doc.ds.fit_ellipse(pts)
            self._register_shot(doc)
            rec = doc.ds.to_record()
            # If this shot ALREADY has a row (from populate/drop), update it in
            # place (Phase 2). Otherwise DON'T auto-add — the user picks fields
            # in the shot inspector and commits one row deliberately.
            prev = self._master.index_of(rec["shot_id"])
            if prev is not None:
                if str(self._master.status_at(prev)) == "EXCLUDE":
                    rec["status"] = "EXCLUDE"  # manual exclude survives re-fitting
                r, _ = self._master.upsert_row(rec)
                self._results_table.selectRow(r)
                self._status.showMessage(f"피팅 완료 → 행 {r + 1} 갱신", 4000)
            else:
                self._status.showMessage(
                    "피팅 완료 → 샷 정보 탭에서 [표에 한 줄 추가]", 5000
                )
            self._inspector_fill()
        v.clear_fit()  # replace the static preview with a managed ROI object
        name = self._next_roi_name(doc, "ellipse", "Ellipse")
        self.add_roi(EllipseFitROI(geom, points=pts, name=name))

    @staticmethod
    def _next_roi_name(doc: DocumentSession, roi_type: str, prefix: str) -> str:
        return f"{prefix}_{len(doc.rois_of_type(roi_type)) + 1}"

    def add_roi(self, roi) -> None:
        """Add an ROI to the active canvas and register it in the session."""
        doc = self._cur()
        v = self._cur_view()
        if doc is None or v is None:
            return
        doc.add_roi(roi)  # register BEFORE canvas add (rebuild reads the session)
        v.add_roi_item(roi)
        if roi.roi_type == "ellipse":
            # Dragging / resizing the ellipse re-measures the ring profile.
            roi.sigRegionChanged.connect(self._ring_update)
            self._ring_update()
        doc.add_log(f"ROI 추가: {roi.name} [{roi.roi_id}]")
        self._refresh_log()

    def remove_roi(self, roi_id: str) -> None:
        # Works for any open document (multi-root pipeline), not just the active.
        owned = self._roi_owner_doc(roi_id) if hasattr(self, "_roi_owner") else None
        if owned is not None:
            _, doc, view, _ = owned
        else:
            doc, view = self._cur(), self._cur_view()
        if doc is None:
            return
        roi = doc.remove_roi(roi_id)
        if roi is not None and view is not None:
            view.remove_roi_item(roi)
            doc.add_log(f"ROI 삭제: {roi.name} [{roi_id}]")
            self._refresh_log()

    def add_line_roi(self, positions=None) -> LineProfileROI:
        """Create + register a line-profile ROI (used by later phases/tools)."""
        doc = self._cur()
        v = self._cur_view()
        if positions is None and v is not None and v.has_image():
            h, w = v.image_shape()
            positions = [[w * 0.2, h * 0.5], [w * 0.8, h * 0.5]]
        roi = LineProfileROI(positions, name=self._next_roi_name(doc, "line", "Line"))
        self.add_roi(roi)
        return roi

    def _on_line_drawn(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Two-click line finished -> spawn a line-profile ROI."""
        doc = self._cur()
        v = self._cur_view()
        if doc is None or v is None:
            return
        roi = LineProfileROI(
            [[x0, y0], [x1, y1]], name=self._next_roi_name(doc, "line", "Line")
        )
        self.add_roi(roi)
        v.set_active_line(roi)
        v.select_roi(roi)
        self._analysis_dock.show()

    def _on_rect_drawn(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Drag-drawn rectangle finished -> spawn a region ROI."""
        doc = self._cur()
        v = self._cur_view()
        if doc is None or v is None:
            return
        px, py = min(x0, x1), min(y0, y1)
        sw, sh = abs(x1 - x0), abs(y1 - y0)
        roi = RectRegionROI(
            [px, py], [sw, sh], name=self._next_roi_name(doc, "rect", "Region")
        )
        self.add_roi(roi)
        v.select_roi(roi)

    def _build_object_tree(self) -> QtWidgets.QTreeWidget:
        self._obj_updating = False
        self._roi_items: dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._roi_owner: dict[str, QtWidgets.QWidget] = {}
        tree = QtWidgets.QTreeWidget()
        self._obj_tree = tree
        tree.setColumnCount(3)
        tree.setHeaderLabels(["오브젝트", "👁", "🔒"])
        hdr = tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        tree.setColumnWidth(1, 30)
        tree.setColumnWidth(2, 30)
        tree.setRootIsDecorated(True)

        tree.itemChanged.connect(self._on_obj_item_changed)
        tree.itemClicked.connect(self._on_obj_item_clicked)
        tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._on_obj_context_menu)
        dele = QtGui.QShortcut(QtGui.QKeySequence.Delete, tree)
        dele.setContext(QtCore.Qt.WidgetShortcut)
        dele.activated.connect(self._on_obj_delete)
        return tree

    @staticmethod
    def _set_eye_lock(item, visible: bool, locked: bool) -> None:
        item.setText(1, "👁" if visible else "—")
        item.setForeground(
            1, QtGui.QBrush(QtGui.QColor("#4ade80" if visible else "#777"))
        )
        item.setTextAlignment(1, QtCore.Qt.AlignCenter)
        item.setText(2, "🔒" if locked else "")
        item.setTextAlignment(2, QtCore.Qt.AlignCenter)

    @staticmethod
    def _roi_icon(roi_type: str) -> QtGui.QIcon:
        pm = QtGui.QPixmap(14, 14)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        if roi_type == "ellipse":
            p.setPen(QtGui.QPen(QtGui.QColor("#ff375f"), 1.6))
            p.drawEllipse(1, 3, 12, 8)
        elif roi_type == "rect":
            p.setPen(QtGui.QPen(QtGui.QColor("#4ade80"), 1.6))
            p.drawRect(2, 3, 10, 8)
        else:  # line
            p.setPen(QtGui.QPen(QtGui.QColor("#facc15"), 2))
            p.drawLine(2, 11, 12, 3)
        p.end()
        return QtGui.QIcon(pm)

    _ROLE_ROI = QtCore.Qt.UserRole
    _ROLE_DOC = QtCore.Qt.UserRole + 1
    _ROLE_PREPROC_IDX = QtCore.Qt.UserRole + 2  # op index; group node = -1

    def _add_obj_item(self, roi, root, widget) -> None:
        item = QtWidgets.QTreeWidgetItem([roi.name, "", ""])
        item.setIcon(0, self._roi_icon(roi.roi_type))
        item.setData(0, self._ROLE_ROI, roi.roi_id)
        item.setFlags(
            QtCore.Qt.ItemIsEnabled
            | QtCore.Qt.ItemIsSelectable
            | QtCore.Qt.ItemIsEditable
        )
        self._set_eye_lock(item, roi.visible, roi.locked)
        root.addChild(item)
        self._roi_items[roi.roi_id] = item
        self._roi_owner[roi.roi_id] = widget

    def _rebuild_object_tree(self) -> None:
        # ParaView-style: EVERY open image is a source (root); ROIs are children.
        self._obj_updating = True
        self._obj_tree.clear()
        self._roi_items = {}
        self._roi_owner = {}
        active = self._tabs.currentWidget()
        bold = QtGui.QFont()
        bold.setBold(True)
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            doc = self._docs.get(widget)
            if doc is None or doc.kind != "image":
                continue
            name = doc.file_path.name
            if doc.frame is not None:
                name += f"  ·  {doc.frame}"
            root = QtWidgets.QTreeWidgetItem([f"🖼  {name}", ""])
            root.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            root.setData(0, self._ROLE_DOC, widget)
            if widget is active:
                root.setFont(0, bold)
            self._obj_tree.addTopLevelItem(root)
            self._add_preproc_group(root, doc, widget)
            for roi in doc.roi_objects.values():
                self._add_obj_item(roi, root, widget)
            root.setExpanded(True)
        self._obj_updating = False

    def _add_preproc_group(self, root, doc, widget) -> None:
        chain = list(doc.ds.history) if doc.ds is not None else []
        grp = QtWidgets.QTreeWidgetItem([f"⚙ 전처리  ({len(chain)})", "", ""])
        grp.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        grp.setData(0, self._ROLE_DOC, widget)
        grp.setData(0, self._ROLE_PREPROC_IDX, -1)
        grp.setForeground(0, QtGui.QBrush(QtGui.QColor("#9aa0a6")))
        root.addChild(grp)
        for i, op in enumerate(chain):
            it = QtWidgets.QTreeWidgetItem([f"{i + 1}. {op.label()}", "", ""])
            it.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            it.setData(0, self._ROLE_DOC, widget)
            it.setData(0, self._ROLE_PREPROC_IDX, i)
            it.setForeground(0, QtGui.QBrush(QtGui.QColor("#c7cbd1")))
            grp.addChild(it)
        grp.setExpanded(True)

    def _on_roi_added(self, roi) -> None:
        self._rebuild_object_tree()

    def _on_roi_removed(self, roi_id: str) -> None:
        self._rebuild_object_tree()

    def _roi_owner_doc(self, roi_id: str):
        """(widget, doc, view, roi) for a roi_id across all open documents."""
        widget = self._roi_owner.get(roi_id)
        doc = self._docs.get(widget) if widget else None
        if doc is None:
            return None
        roi = doc.get_roi(roi_id)
        if roi is None:
            return None
        return widget, doc, doc.view, roi

    def _on_obj_item_changed(self, item, col) -> None:
        if self._obj_updating or col != 0:
            return
        rid = item.data(0, self._ROLE_ROI)
        if rid is None:
            return
        owned = self._roi_owner_doc(rid)
        if owned is None:
            return
        _, _, _, roi = owned
        name = item.text(0).strip()
        if name and name != roi.name:
            roi.rename(name)

    def _on_obj_item_clicked(self, item, col) -> None:
        rid = item.data(0, self._ROLE_ROI)
        if rid is None:
            # Root (image) item -> switch to that document tab.
            widget = item.data(0, self._ROLE_DOC)
            if widget is not None:
                self._tabs.setCurrentWidget(widget)
            return
        owned = self._roi_owner_doc(rid)
        if owned is None:
            return
        widget, _, view, roi = owned
        if col == 1:  # 👁 toggle visibility
            roi.set_visible(not roi.visible)
            self._obj_updating = True
            self._set_eye_lock(item, roi.visible, roi.locked)
            self._obj_updating = False
            return
        if col == 2:  # 🔒 toggle lock
            roi.set_locked(not roi.locked)
            self._obj_updating = True
            self._set_eye_lock(item, roi.visible, roi.locked)
            self._obj_updating = False
            return
        # col 0 = focus/select: switch to the owning tab first, then highlight.
        if widget is not self._tabs.currentWidget():
            self._tabs.setCurrentWidget(widget)
        view.select_roi(roi)

    def _on_obj_delete(self) -> None:
        item = self._obj_tree.currentItem()
        if item is None:
            return
        idx = item.data(0, self._ROLE_PREPROC_IDX)
        if idx is not None and idx >= 0:
            doc = self._docs.get(item.data(0, self._ROLE_DOC))
            if doc is not None:
                self._preproc_remove_at(doc, idx)
            return
        rid = item.data(0, self._ROLE_ROI)
        if rid:
            self.remove_roi(rid)

    def _add_gamma(self, doc) -> None:
        g, ok = QtWidgets.QInputDialog.getDouble(
            self, "감마 값", "γ (예: 0.5 = 밝게, 2.0 = 어둡게):", 0.5, 0.01, 10.0, 2
        )
        if ok:
            self._preproc_add(doc, "gamma", {"gamma": float(g)})

    def _add_scale(self, doc) -> None:
        """Ask for separate x and y scale factors (equal values scale uniformly)."""
        sx, ok = QtWidgets.QInputDialog.getDouble(
            self, "크기·비율 변형", "가로 배율 sx (1.0 = 그대로):", 1.0, 0.01, 20.0, 3
        )
        if not ok:
            return
        sy, ok = QtWidgets.QInputDialog.getDouble(
            self, "크기·비율 변형", "세로 배율 sy:", sx, 0.01, 20.0, 3
        )
        if ok:
            self._preproc_add(doc, "scale", {"sx": float(sx), "sy": float(sy)})

    def _add_rotate(self, doc) -> None:
        ang, ok = QtWidgets.QInputDialog.getDouble(
            self, "회전", "각도 (도, + = 반시계):", 0.0, -360.0, 360.0, 2
        )
        if ok:
            self._preproc_add(doc, "rotate", {"angle": float(ang), "expand": True})

    def _on_obj_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self._obj_tree.itemAt(pos)
        if item is None:
            return
        idx = item.data(0, self._ROLE_PREPROC_IDX)
        doc = self._docs.get(item.data(0, self._ROLE_DOC))
        if doc is None:
            return
        menu = QtWidgets.QMenu(self)
        if idx == -1:  # preprocessing group node
            menu.addAction("Log (adaptive) 추가", lambda: self._preproc_add(doc, "log"))
            menu.addAction(
                "Log (pure) 추가", lambda: self._preproc_add(doc, "pure_log")
            )
            menu.addAction("제곱근 (√) 추가", lambda: self._preproc_add(doc, "sqrt"))
            menu.addAction("감마 (γ) 추가…", lambda: self._add_gamma(doc))
            menu.addAction(
                "정규화 (/max) 추가", lambda: self._preproc_add(doc, "normalize")
            )
            menu.addSeparator()
            geo = menu.addMenu("기하 변형")
            geo.addAction("크기·비율 변형…", lambda: self._add_scale(doc))
            geo.addAction("회전…", lambda: self._add_rotate(doc))
            geo.addAction(
                "좌우 뒤집기", lambda: self._preproc_add(doc, "flip", {"axis": "h"})
            )
            geo.addAction(
                "상하 뒤집기", lambda: self._preproc_add(doc, "flip", {"axis": "v"})
            )
            menu.addSeparator()
            hint = menu.addAction("Dark/Flat: 구조·파일 탭에서 우클릭")
            hint.setEnabled(False)
        elif idx is not None and idx >= 0:  # an op step
            menu.addAction("↑ 위로", lambda: self._preproc_move_at(doc, idx, -1))
            menu.addAction("↓ 아래로", lambda: self._preproc_move_at(doc, idx, 1))
            menu.addSeparator()
            menu.addAction("삭제", lambda: self._preproc_remove_at(doc, idx))
        else:
            return
        menu.exec(self._obj_tree.viewport().mapToGlobal(pos))

    def _delete_selected_roi(self) -> None:
        """Delete key: remove the ROI selected on the active canvas."""
        v = self._cur_view()
        if v is None:
            return
        roi = v.selected_roi()
        if roi is not None:
            self.remove_roi(roi.roi_id)

    def _on_roi_selected(self, roi) -> None:
        self._obj_updating = True
        if roi is None:
            self._obj_tree.setCurrentItem(None)
        else:
            it = self._roi_items.get(roi.roi_id)
            if it is not None:
                self._obj_tree.setCurrentItem(it)
        self._obj_updating = False
        if roi is not None and roi.roi_type == "line":
            self._analysis_dock.show()

    def _do_hist_visible(self, b) -> None:
        if v := self._cur_view():
            v.set_histogram_visible(b)

    def _do_hist_detach(self) -> None:
        if v := self._cur_view():
            v.detach_histogram()
            with QtCore.QSignalBlocker(self._hist_chk):
                self._hist_chk.setChecked(False)
                self._hist_chk.setEnabled(False)
