"""Per-file document session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .image_view import ImageView
from .prefs import ViewPrefs


@dataclass
class DocumentSession:
    """Independent per-file session: image, ROI objects, logs, view settings."""

    file_path: Path
    kind: str  # 'image' | 'text'
    view: ImageView | None = None
    ds: object = None  # core.QoraDFXMDataset — raw + preproc history + fit
    frames: list = field(default_factory=list)
    frame: object = None
    structure: object = None
    preview: bool = False
    info: str = ""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    logs: list = field(default_factory=list)
    # roi_id -> AnalysisROI (Phase B multi-object management).
    roi_objects: dict = field(default_factory=dict)
    prefs: ViewPrefs = field(default_factory=ViewPrefs)  # how this doc is drawn

    def add_log(self, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{ts}] {message}")

    # --- ROI management ----------------------------------------------------
    def add_roi(self, roi) -> None:
        self.roi_objects[roi.roi_id] = roi

    def remove_roi(self, roi_id: str):
        return self.roi_objects.pop(roi_id, None)

    def get_roi(self, roi_id: str):
        return self.roi_objects.get(roi_id)

    def rois_of_type(self, roi_type: str) -> list:
        return [r for r in self.roi_objects.values() if r.roi_type == roi_type]
