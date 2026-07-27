from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import joblib
import numpy as np


FEATURE_NAMES: List[str] = [
    "bbox_w_px",
    "bbox_h_px",
    "bbox_area_px",
    "bbox_aspect_hw",
    "gray_mean",
    "gray_std",
    "gray_p10",
    "gray_p25",
    "gray_p50",
    "gray_p75",
    "gray_p90",
    "grad_mean",
    "grad_std",
    "lap_var",
    "mask_area_ratio",
    "mask_centroid_x",
    "mask_centroid_y",
    "mask_height_ratio",
    "mask_width_ratio",
    "axis_len_px",
    "axis_len_norm_h",
    "dist_core_ratio",
]


def _normalize_gray(img: np.ndarray) -> np.ndarray:
    x = img.astype(np.float32)
    mn, mx = float(np.min(x)), float(np.max(x))
    if mx - mn < 1e-6:
        return np.zeros_like(img, dtype=np.uint8)
    return ((x - mn) / (mx - mn) * 255.0).astype(np.uint8)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return mask
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == idx).astype(np.uint8) * 255


def _major_axis_len_px(mask: np.ndarray) -> float:
    ys, xs = np.where(mask > 0)
    if len(xs) < 4:
        return 0.0
    pts = np.column_stack([xs.astype(np.float64), ys.astype(np.float64)])
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    axis = eigvecs[:, int(np.argmax(eigvals))]
    proj = centered @ axis
    return float(np.max(proj) - np.min(proj))


def extract_handcrafted_features(crop_gray: np.ndarray, bbox_w_px: int, bbox_h_px: int) -> np.ndarray:
    h, w = crop_gray.shape[:2]
    bbox_w = float(max(1, int(bbox_w_px)))
    bbox_h = float(max(1, int(bbox_h_px)))
    norm = _normalize_gray(crop_gray)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(norm)

    p10, p25, p50, p75, p90 = [float(v) for v in np.percentile(enhanced, [10, 25, 50, 75, 90])]
    gx = cv2.Sobel(enhanced, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(enhanced, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)

    _, mask = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    mask = _largest_component(mask)

    ys, xs = np.where(mask > 0)
    if len(xs) > 0:
        cx = float(np.mean(xs) / max(1, w - 1))
        cy = float(np.mean(ys) / max(1, h - 1))
        y_span = float((np.max(ys) - np.min(ys) + 1) / max(1, h))
        x_span = float((np.max(xs) - np.min(xs) + 1) / max(1, w))
    else:
        cx, cy, y_span, x_span = 0.5, 0.5, 0.0, 0.0

    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    maxd = float(np.max(dist))
    core_ratio = (
        float(np.count_nonzero(dist > (0.35 * maxd)) / max(1, np.count_nonzero(mask)))
        if maxd > 1e-6
        else 0.0
    )
    axis_len = _major_axis_len_px(mask)

    return np.array(
        [
            bbox_w,
            bbox_h,
            bbox_w * bbox_h,
            bbox_h / max(1.0, bbox_w),
            float(np.mean(enhanced)),
            float(np.std(enhanced)),
            p10,
            p25,
            p50,
            p75,
            p90,
            float(np.mean(grad)),
            float(np.std(grad)),
            float(cv2.Laplacian(enhanced, cv2.CV_32F, ksize=3).var()),
            float(np.count_nonzero(mask) / max(1, h * w)),
            cx,
            cy,
            y_span,
            x_span,
            axis_len,
            axis_len / max(1.0, bbox_h),
            core_ratio,
        ],
        dtype=np.float64,
    )


def load_alt_model(model_path: Path) -> Dict:
    pack = joblib.load(model_path)
    if "models" not in pack:
        raise ValueError(f"Invalid alternative model file: {model_path}")
    return pack


def predict_alt_length_mm(
    model_pack: Dict,
    tooth_type: str,
    crop_gray: np.ndarray,
    bbox_w_px: int,
    bbox_h_px: int,
) -> Tuple[float, str]:
    model = model_pack["models"][tooth_type]
    feats = extract_handcrafted_features(crop_gray, bbox_w_px, bbox_h_px)
    pred = float(model.predict(feats.reshape(1, -1))[0])
    model_name = str(model_pack.get("selected_model_name", {}).get(tooth_type, "alt"))
    return pred, model_name
