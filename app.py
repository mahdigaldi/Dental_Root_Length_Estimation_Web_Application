from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, url_for
from werkzeug.utils import secure_filename

from inference import DentalWebPredictor


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
OUTPUT_DIR = BASE_DIR / "static" / "outputs"
MODEL_DIR = BASE_DIR / "models"
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

predictor = DentalWebPredictor(model_dir=MODEL_DIR, device=os.environ.get("DENTAL_DEVICE", "cpu"))


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image file was uploaded."}), 400

    file = request.files["image"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({"error": "Upload a valid image file."}), 400

    method = request.form.get("method", "ensemble").strip().lower()
    if method not in {"yolo", "alt", "ensemble"}:
        return jsonify({"error": "Invalid method. Use yolo, alt, or ensemble."}), 400
    try:
        ensemble_alpha = float(request.form.get("ensemble_alpha", "0.60"))
        det_conf = float(request.form.get("det_conf", "0.25"))
    except ValueError:
        return jsonify({"error": "Numeric parameters are invalid."}), 400

    ensemble_alpha = min(1.0, max(0.0, ensemble_alpha))
    det_conf = min(0.95, max(0.05, det_conf))

    safe_name = secure_filename(file.filename)
    run_id = uuid.uuid4().hex[:12]
    upload_path = UPLOAD_DIR / f"{run_id}_{safe_name}"
    output_path = OUTPUT_DIR / f"{run_id}_overlay.png"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file.save(upload_path)

    try:
        predictions, warnings = predictor.predict(
            image_path=upload_path,
            output_path=output_path,
            method=method,
            ensemble_alpha=ensemble_alpha,
            det_conf=det_conf,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "overlay_url": url_for("static", filename=f"outputs/{output_path.name}"),
            "input_url": url_for("static", filename=f"uploads/{upload_path.name}"),
            "predictions": [item.to_dict() for item in predictions],
            "warnings": warnings,
            "method": method,
            "ensemble_alpha": ensemble_alpha,
        }
    )


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=debug, use_reloader=False)
