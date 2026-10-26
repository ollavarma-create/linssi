#!/usr/bin/env bash
# Creates .venv for Linssi Viewer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAIN_PYTHON="${MAIN_PYTHON:-python3}"
REQUIREMENTS="${REQUIREMENTS:-requirements.txt}"

echo "========================================"
echo " Linssi Viewer — installer"
echo "========================================"
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

# ── Create venv ────────────────────────────────────────────────────────────────
echo "Creating .venv..."
"$MAIN_PYTHON" -m venv .venv --clear

# ── Install dependencies ───────────────────────────────────────────────────────
echo "Installing dependencies ($REQUIREMENTS)..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r "$REQUIREMENTS"
echo "  Done."
echo ""


echo "========================================"
echo " Installation complete!"
echo ""
echo " Run the app:"
echo "   source .venv/bin/activate"
echo "   python -m src.main --db data/image_analyzer.db"
echo ""
echo " Or without --db to open a file dialog:"
echo "   python -m src.main"
echo "========================================"
