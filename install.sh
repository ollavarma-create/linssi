#!/usr/bin/env bash
# Linssi — hardware-aware installer
# Creates .venv (main app) and .venv-face (face recognition, isolated)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " Linssi — hardware-aware installer"
echo "========================================"
echo ""

# ── GPU detection ─────────────────────────────────────────────────────────────
detect_compute_major() {
    command -v nvidia-smi &>/dev/null || { echo 0; return; }
    local cap
    cap=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null \
          | head -1 | tr -d ' ')
    [ -z "$cap" ] && { echo 0; return; }
    echo "${cap%%.*}"
}

COMPUTE_MAJOR=$(detect_compute_major)

if [ "$COMPUTE_MAJOR" -eq 0 ]; then
    GPU_DESC="No NVIDIA GPU — CPU only"
    MAIN_PYTHON="python3.11"
    FACE_BACKEND="insightface-cpu"
    REQUIREMENTS="requirements.txt"
elif [ "$COMPUTE_MAJOR" -ge 7 ]; then
    GPU_DESC="Volta+ GPU (sm_${COMPUTE_MAJOR}.x) — CUDA"
    MAIN_PYTHON="python3.12"
    FACE_BACKEND="facenet-gpu"
    REQUIREMENTS="requirements-volta.txt"
else
    # Pascal (sm_61) and older: GPU onnxruntime is unreliable (cuDNN/libnvrtc issues)
    # Use CPU onnxruntime — stable, no system CUDA library dependencies
    GPU_DESC="Pascal GPU (sm_${COMPUTE_MAJOR}.x) — CPU inference (GPU onnxruntime unreliable)"
    MAIN_PYTHON="python3.11"
    FACE_BACKEND="insightface-cpu"
    REQUIREMENTS="requirements.txt"
fi

echo "GPU:          $GPU_DESC"
echo "Main Python:  $MAIN_PYTHON"
echo "Face backend: $FACE_BACKEND"
echo ""

# ── Validate Python ───────────────────────────────────────────────────────────
require_python() {
    local py="$1"
    if ! command -v "$py" &>/dev/null; then
        echo "ERROR: $py not found. Install it first:"
        echo "  Ubuntu/Mint:  sudo apt install $py ${py}-venv"
        echo "  Fedora:       sudo dnf install $py"
        exit 1
    fi
    echo "  $py -> $($py --version)"
}

echo "Checking Python..."
require_python "$MAIN_PYTHON"
echo ""

# ── Create venvs ──────────────────────────────────────────────────────────────
echo "Creating .venv (main app)..."
"$MAIN_PYTHON" -m venv .venv --clear

echo "Creating .venv-face (face worker)..."
"$MAIN_PYTHON" -m venv .venv-face --clear
echo ""

# ── Main app dependencies ─────────────────────────────────────────────────────
echo "Installing main app dependencies ($REQUIREMENTS)..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r "$REQUIREMENTS" -q
echo "  Done."
echo ""

# ── Face recognition dependencies ────────────────────────────────────────────
echo "Installing face recognition backend ($FACE_BACKEND) into .venv-face..."
.venv-face/bin/pip install --upgrade pip -q
.venv-face/bin/pip install numpy opencv-python-headless Pillow -q

if [ "$FACE_BACKEND" = "facenet-gpu" ]; then
    echo "  Installing facenet-pytorch + torch (CUDA)..."
    .venv-face/bin/pip install torch torchvision \
        --index-url https://download.pytorch.org/whl/cu121 -q
    .venv-face/bin/pip install facenet-pytorch -q
else
    # CPU onnxruntime — no cuDNN, no libnvrtc, guaranteed to work
    echo "  Installing insightface + onnxruntime (CPU)..."
    .venv-face/bin/pip install onnxruntime insightface -q
fi

echo "  Done."
echo ""

# ── Write backend config for face_recognizer.py ──────────────────────────────
cat > .venv-face-config <<EOF
FACE_BACKEND=${FACE_BACKEND}
COMPUTE_MAJOR=${COMPUTE_MAJOR}
EOF

echo "========================================"
echo " Installation complete!"
echo ""
echo " Run the app:"
echo "   source .venv/bin/activate"
echo "   python -m src.main --gui"
echo ""
echo " Or:"
echo "   .venv/bin/python -m src.main --gui"
echo "========================================"
