#!/usr/bin/env bash
# One-time setup for aarvan-video-kit. Safe to run again: prints READY when everything is in place.
set -e
cd "$(dirname "$0")"
EFFECTS_REPO=https://github.com/Vibha-Ramprakash/claude-video-effects.git
EFFECTS_COMMIT=93140a976dcd1c78bda8819fa432ca7b4f260bf7

command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo "NEED_FFMPEG: install ffmpeg (Ubuntu/WSL: sudo apt install ffmpeg, Mac: brew install ffmpeg)"; exit 1; }

# 1) vendored effects pack (MIT) + its face/person models, pinned to a tested commit
if [ ! -f vendor/claude-video-effects/scripts/fx.py ]; then
  mkdir -p vendor
  git clone -q "$EFFECTS_REPO" vendor/claude-video-effects
fi
if [ "$(git -C vendor/claude-video-effects rev-parse HEAD)" != "$EFFECTS_COMMIT" ]; then   # upgrade older installs
  git -C vendor/claude-video-effects fetch -q origin && git -C vendor/claude-video-effects checkout -q "$EFFECTS_COMMIT"
fi

# 2) python packages: a local .venv when possible, otherwise the system python
PY=python3
if [ -x .venv/bin/python ]; then PY=.venv/bin/python
elif python3 -m venv .venv >/dev/null 2>&1; then PY=.venv/bin/python; $PY -m pip install -q --upgrade pip
fi
if ! $PY -c "import numpy, cv2, PIL, scipy, soundfile, mediapipe" 2>/dev/null; then
  $PY -m pip install -q -r requirements.txt 2>/dev/null || $PY -m pip install -q --break-system-packages -r requirements.txt
fi
$PY -c "import numpy, cv2, PIL, scipy, soundfile, mediapipe; print('READY')"
