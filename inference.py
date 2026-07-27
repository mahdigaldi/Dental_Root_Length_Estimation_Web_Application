from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from length_alt_utils import load_alt_model, predict_alt_length_mm


TOOTH_BY_CLASS = {0: "D", 1: "E"}


@dataclass
class Prediction:
    tooth_type: str
    det_tooth_type: str
    det_conf: float
    cls_conf: float
    pred_bin: int
    pred_length_mm: float
    pred_length_yolo_mm: Optional[float]
    pred_length_alt_mm: Optional[float]
    box: Tuple[int, int, int, int]
    line: Tuple[Tuple[int, int], Tuple[int, int]]

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["box"] = list(self.box)
        data["line"] = [list(self.line[0]), list(self.line[1])]
        return data


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img


def save_bgr(path: Path, image_bgr: np.ndarray) -> None:
    ok, enc = cv2.imencode(".png", image_bgr)
    if not ok:
        raise IOError("Failed to encode output image.")
    path.parent.mkdir(parents=True, exist_ok=True)
    enc.tofile(str(path))


def _normalize_gray(img: np.ndarray) -> np.ndarray:
    img = img.astype(np.float32)
    mn, mx = float(np.min(img)), float(np.max(img))
    if mx - mn < 1e-5:
        return np.zeros_like(img, dtype=np.uint8)
    return ((img - mn) / (mx - mn) * 255).astype(np.uint8)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return mask
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == idx).astype(np.uint8) * 255


def estimate_apex_and_germ(crop_gray: np.ndarray) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    h, w = crop_gray.shape[:2]
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(_normalize_gray(crop_gray))
    blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = _largest_component(mask)

    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return (w // 2, max(2, int(h * 0.15))), (w // 2, int(h * 0.85))

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    center_x = (w - 1) / 2.0
    sigma = max(8.0, 0.22 * w)
    weight_x = np.exp(-0.5 * ((np.arange(w, dtype=np.float32) - center_x) / sigma) ** 2)
    weighted = dist * weight_x[None, :]
    core = weighted > (0.35 * float(weighted.max() + 1e-9))
    if np.count_nonzero(core) < 20:
        core = dist > (0.25 * float(dist.max() + 1e-9))

    cy, cx = np.where(core)
    if len(cy) < 10:
        cy, cx = np.where(mask > 0)

    weights = weighted[cy, cx].astype(np.float64)
    w_sum = float(weights.sum()) if weights.sum() > 0 else 1.0
    mean_x = float((weights * cx).sum() / w_sum)
    mean_y = float((weights * cy).sum() / w_sum)
    dx = cx - mean_x
    dy = cy - mean_y
    cov = np.array(
        [
            [float((weights * dx * dx).sum() / w_sum), float((weights * dx * dy).sum() / w_sum)],
            [float((weights * dx * dy).sum() / w_sum), float((weights * dy * dy).sum() / w_sum)],
        ]
    )
    eigvals, eigvecs = np.linalg.eigh(cov)
    vx, vy = eigvecs[:, int(np.argmax(eigvals))]
    if vy < 0:
        vx, vy = -vx, -vy

    points = np.column_stack(np.where(mask > 0)).astype(np.float64)
    px = points[:, 1] - mean_x
    py = points[:, 0] - mean_y
    t = px * vx + py * vy
    perp = np.abs(-vy * px + vx * py)
    radius = max(4.0, float(np.percentile(dist[mask > 0], 70)))
    corridor = perp <= (1.2 * radius)
    t_sel = t[corridor] if np.count_nonzero(corridor) >= 2 else t

    t_min, t_max = float(np.min(t_sel)), float(np.max(t_sel))
    apex = (int(round(mean_x + t_min * vx)), int(round(mean_y + t_min * vy)))
    germ = (int(round(mean_x + t_max * vx)), int(round(mean_y + t_max * vy)))
    apex = (max(0, min(w - 1, apex[0])), max(0, min(h - 1, apex[1])))
    germ = (max(0, min(w - 1, germ[0])), max(0, min(h - 1, germ[1])))
    return (germ, apex) if apex[1] > germ[1] else (apex, germ)


class DentalWebPredictor:
    def __init__(self, model_dir: Path, device: str = "cpu") -> None:
        self.model_dir = model_dir
        self.device = device
        self.det_model: Optional[YOLO] = None
        self.cls_models: Dict[str, YOLO] = {}
        self.centers: Dict[str, np.ndarray] = {}
        self.yolo_calibration: Optional[Dict] = None
        self.alt_pack: Optional[Dict] = None
        self.alt_calibration: Optional[Dict] = None

    def load(self) -> None:
        with (self.model_dir / "length_bin_mapping.json").open("r", encoding="utf-8") as f:
            mapping = json.load(f)
        self.centers = {
            "D": np.array(mapping["D"]["centers"], dtype=np.float64),
            "E": np.array(mapping["E"]["centers"], dtype=np.float64),
        }
        with (self.model_dir / "length_calibration.json").open("r", encoding="utf-8") as f:
            self.yolo_calibration = json.load(f)
        with (self.model_dir / "alt_calibration.json").open("r", encoding="utf-8") as f:
            self.alt_calibration = json.load(f)

        self.det_model = YOLO(str(self.model_dir / "detector_best.pt"))
        self.cls_models = {
            "D": YOLO(str(self.model_dir / "cls_d_best.pt")),
            "E": YOLO(str(self.model_dir / "cls_e_best.pt")),
        }
        self.alt_pack = load_alt_model(self.model_dir / "alt_length_model.joblib")

    def _apply_calibration(self, value: float, tooth: str, calibration: Optional[Dict]) -> float:
        if calibration is None or tooth not in calibration:
            return value
        params = calibration[tooth]
        return float(float(params.get("a", 1.0)) * value + float(params.get("b", 0.0)))

    def _predict_yolo(self, crop_gray: np.ndarray, tooth: str, cls_imgsz: int = 224) -> Tuple[float, int, float]:
        model = self.cls_models[tooth]
        crop_bgr = cv2.cvtColor(crop_gray, cv2.COLOR_GRAY2BGR)
        out = model.predict(source=crop_bgr, imgsz=cls_imgsz, device=self.device, verbose=False)[0]
        probs = out.probs.data.detach().cpu().numpy().astype(np.float64)
        n = min(len(probs), len(self.centers[tooth]))
        probs = probs[:n]
        centers = self.centers[tooth][:n]
        probs = probs / probs.sum() if probs.sum() > 0 else np.ones_like(probs) / len(probs)
        pred_bin = int(np.argmax(probs))
        pred = float(np.sum(probs * centers))
        pred = self._apply_calibration(pred, tooth, self.yolo_calibration)
        return pred, pred_bin, float(probs[pred_bin])

    def _predict_alt(self, crop_gray: np.ndarray, tooth: str, box: Tuple[int, int, int, int]) -> float:
        if self.alt_pack is None:
            raise RuntimeError("Alternative model is not loaded.")
        x1, y1, x2, y2 = box
        pred, _ = predict_alt_length_mm(self.alt_pack, tooth, crop_gray, x2 - x1, y2 - y1)
        return self._apply_calibration(pred, tooth, self.alt_calibration)

    def predict(
        self,
        image_path: Path,
        output_path: Path,
        method: str = "ensemble",
        ensemble_alpha: float = 0.60,
        det_conf: float = 0.25,
        det_iou: float = 0.50,
        det_imgsz: int = 768,
    ) -> Tuple[List[Prediction], List[str]]:
        if self.det_model is None:
            self.load()
        if method not in {"yolo", "alt", "ensemble"}:
            raise ValueError("method must be yolo, alt, or ensemble")

        gray = read_gray(image_path)
        image_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h, w = gray.shape[:2]
        result = self.det_model.predict(
            source=image_bgr,
            imgsz=det_imgsz,
            conf=det_conf,
            iou=det_iou,
            device=self.device,
            verbose=False,
        )[0]

        boxes: List[Dict] = []
        if result.boxes is not None and len(result.boxes):
            xyxy = result.boxes.xyxy.detach().cpu().numpy()
            cls = result.boxes.cls.detach().cpu().numpy()
            conf = result.boxes.conf.detach().cpu().numpy()
            for idx in range(len(xyxy)):
                cid = int(cls[idx])
                if cid not in TOOTH_BY_CLASS:
                    continue
                x1, y1, x2, y2 = [int(round(v)) for v in xyxy[idx].tolist()]
                boxes.append(
                    {
                        "class_id": cid,
                        "tooth": TOOTH_BY_CLASS[cid],
                        "conf": float(conf[idx]),
                        "box": (max(0, x1), max(0, y1), min(w, x2), min(h, y2)),
                    }
                )

        predictions: List[Prediction] = []
        warnings: List[str] = []
        if not boxes:
            warnings.append("No tooth detected.")

        boxes.sort(key=lambda item: item["box"][0])
        colors = {"D": (70, 150, 255), "E": (60, 220, 130)}

        for item in boxes:
            tooth = item["tooth"]
            x1, y1, x2, y2 = item["box"]
            crop = gray[y1:y2, x1:x2]
            if crop.size == 0:
                warnings.append(f"Empty crop for tooth {tooth}.")
                continue

            yolo_pred, pred_bin, cls_conf = self._predict_yolo(crop, tooth)
            alt_pred = self._predict_alt(crop, tooth, (x1, y1, x2, y2))
            if method == "yolo":
                final_pred = yolo_pred
            elif method == "alt":
                final_pred = alt_pred
            else:
                final_pred = float(ensemble_alpha * yolo_pred + (1.0 - ensemble_alpha) * alt_pred)

            apex, germ = estimate_apex_and_germ(crop)
            apex_img = (x1 + apex[0], y1 + apex[1])
            germ_img = (x1 + germ[0], y1 + germ[1])
            color = colors[tooth]

            cv2.rectangle(image_bgr, (x1, y1), (x2, y2), color, 2)
            cv2.line(image_bgr, apex_img, germ_img, color, 2)
            cv2.circle(image_bgr, apex_img, 4, color, -1)
            cv2.circle(image_bgr, germ_img, 4, color, -1)
            cv2.putText(
                image_bgr,
                f"{tooth}: {final_pred:.2f} mm",
                (x1, max(22, y1 - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
                cv2.LINE_AA,
            )

            predictions.append(
                Prediction(
                    tooth_type=tooth,
                    det_tooth_type=tooth,
                    det_conf=float(item["conf"]),
                    cls_conf=cls_conf,
                    pred_bin=pred_bin,
                    pred_length_mm=final_pred,
                    pred_length_yolo_mm=yolo_pred,
                    pred_length_alt_mm=alt_pred,
                    box=(x1, y1, x2, y2),
                    line=(apex_img, germ_img),
                )
            )

        save_bgr(output_path, image_bgr)
        return predictions, warnings
