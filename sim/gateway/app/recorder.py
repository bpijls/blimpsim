"""Writes camera frames and their ground truth to disk as a COCO dataset.

    <datasets_dir>/<name>/images/000000.jpg ...
    <datasets_dir>/<name>/annotations.json   (written when recording stops)
"""
import json
import re
from pathlib import Path

NAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
FILE_PATTERN = r"^\d{6}\.jpg$"
ANNOTATIONS = "annotations.json"


class RecorderError(Exception):
    pass


class Recorder:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self._name: str | None = None
        self._every = 1
        self._max_frames = 0
        self._seen = 0
        self._images: list[dict] = []
        self._annotations: list[dict] = []

    def status(self) -> dict | None:
        if self._name is None:
            return None
        return {"name": self._name, "frames": len(self._images), "max_frames": self._max_frames}

    def start(self, name: str, every: int, max_frames: int) -> None:
        if self._name is not None:
            raise RecorderError(f"already recording '{self._name}'")
        if (self.root / name).exists():
            raise RecorderError(f"dataset '{name}' already exists")
        (self.root / name / "images").mkdir(parents=True)
        self._name, self._every, self._max_frames = name, every, max_frames
        self._seen = 0
        self._images, self._annotations = [], []

    def add(self, meta: dict, jpeg: bytes) -> None:
        """Called for every camera frame; a no-op unless a recording is running."""
        labels = meta.get("labels")
        if self._name is None or labels is None:
            return
        self._seen += 1
        if (self._seen - 1) % self._every:
            return
        image_id = len(self._images)
        file_name = f"{image_id:06d}.jpg"
        (self.root / self._name / "images" / file_name).write_bytes(jpeg)
        camera = labels["camera"]
        self._images.append(
            {
                "id": image_id,
                "file_name": file_name,
                "width": camera["width"],
                "height": camera["height"],
                "t": labels["t"],
                "camera": camera,
            }
        )
        for person in labels["people"]:
            x, y, w, h = person["bbox"]
            self._annotations.append(
                {
                    "id": len(self._annotations),
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [x, y, w, h],
                    "area": round(w * h, 1),
                    "iscrowd": 0,
                    "track_id": person["id"],
                    "visibility": person["visibility"],
                }
            )
        if len(self._images) >= self._max_frames:
            self.stop()

    def stop(self) -> dict | None:
        if self._name is None:
            return None
        coco = {
            "images": self._images,
            "annotations": self._annotations,
            "categories": [{"id": 1, "name": "person"}],
        }
        (self.root / self._name / ANNOTATIONS).write_text(json.dumps(coco))
        summary = {
            "name": self._name,
            "frames": len(self._images),
            "annotations": len(self._annotations),
        }
        self._name = None
        return summary

    def list(self) -> list[dict]:
        out = []
        if not self.root.exists():
            return out
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir():
                continue
            out.append(
                {
                    "name": folder.name,
                    "frames": len(list((folder / "images").glob("*.jpg"))),
                    "recording": folder.name == self._name,
                }
            )
        return out

    def path(self, name: str, *parts: str) -> Path | None:
        """A file inside a dataset, or None if the name is malformed or it is missing."""
        if not re.match(NAME_PATTERN, name):
            return None
        if parts[0] == "images" and (len(parts) != 2 or not re.match(FILE_PATTERN, parts[1])):
            return None
        if parts[0] != "images" and parts != (ANNOTATIONS,):
            return None
        path = self.root.joinpath(name, *parts)
        return path if path.is_file() else None
