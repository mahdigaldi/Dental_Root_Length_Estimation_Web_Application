# Dental Length Web App

This folder is a standalone Flask web package for the dental tooth-length project.
Upload only the `web` folder to a Python-capable host. The original local project is not required on the server.

## What It Does

- Uploads a dental radiography image.
- Detects D/E teeth with YOLO.
- Estimates root length in millimeters with `yolo`, `alt`, or `ensemble`.
- Draws the tooth box and a straight apex-to-germ line.
- Shows the annotated output image and prediction table in the browser.

## Included Model Files

The app expects these files in `web/models`:

- `detector_best.pt`
- `cls_d_best.pt`
- `cls_e_best.pt`
- `length_bin_mapping.json`
- `length_calibration.json`
- `alt_length_model.joblib`
- `alt_calibration.json`

## Local Test

```powershell
cd web
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## IIS on Windows Server

For IIS deployment, use:

- `web.config`
- `server.py`
- `README_IIS_FA.md`

The active IIS setup uses HttpPlatformHandler + Waitress. Follow the Persian step-by-step guide in `README_IIS_FA.md`.

## VPS Deployment

```bash
cd web
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/gunicorn -w 1 -b 0.0.0.0:8000 wsgi:application
```

Put Nginx/Apache in front of port `8000` and point your domain to it.

## cPanel Python App

1. Upload the whole `web` folder.
2. In cPanel, create a Python application and set the app root to `web`.
3. Set the startup file to `passenger_wsgi.py`.
4. Install packages from `requirements.txt`.
5. Restart the Python application.

## Important Hosting Notes

- This is not a static HTML site; it needs Python hosting because YOLO inference runs on the server.
- CPU hosting works, but first prediction can be slow while models load.
- Keep upload size reasonable. The app currently limits requests to 16 MB.
- For public deployment, put HTTPS and normal server-level upload limits in front of the app.
