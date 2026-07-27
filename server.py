from __future__ import annotations

import os

from waitress import serve

from app import app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    serve(app, host="127.0.0.1", port=port, threads=2, channel_timeout=600)
