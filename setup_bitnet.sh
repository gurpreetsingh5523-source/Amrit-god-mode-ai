#!/bin/bash
# ============================================================
#  BitNet b1.58 - Complete Setup Script for Mac (Apple Silicon)
#  System: macOS, 16GB RAM
#  Model:  Falcon3-10B-Instruct-1.58bit  (largest official
#          BitNet b1.58 model; ~2-3 GB RAM in 1-bit format)
#
#  NOTE: ਕੋਈ ਵੀ ਅਧਿਕਾਰਤ 30B / 70B BitNet b1.58 ਮਾਡਲ ਅਜੇ ਤੱਕ
#         ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਸਭ ਤੋਂ ਵੱਡਾ ਉਪਲਬਧ ਮਾਡਲ Falcon3-10B ਹੈ
#         ਜੋ 16GB RAM ਵਿੱਚ ਆਸਾਨੀ ਨਾਲ ਚੱਲਦਾ ਹੈ (ਸਿਰਫ ~2-3 GB ਵਰਤਦਾ ਹੈ)।
# ============================================================

set -e  # Exit immediately on any error

BITNET_DIR="$HOME/BitNet"
MODEL_DIR="$BITNET_DIR/models/Falcon3-10B-1.58bit"
PYTHON_BIN="python3"

echo ""
echo "========================================================"
echo "  BitNet b1.58 Setup - Mac Apple Silicon (16GB RAM)"
echo "========================================================"
echo ""

# ─────────────────────────────────────────────
# STEP 1: Install Homebrew dependencies
# ─────────────────────────────────────────────
echo ">>> [1/6] Homebrew dependencies ਚੈੱਕ ਕਰ ਰਹੇ ਹਾਂ..."

if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew ਨਹੀਂ ਮਿਲਿਆ। ਪਹਿਲਾਂ https://brew.sh ਤੋਂ ਇੰਸਟਾਲ ਕਰੋ।"
    exit 1
fi

# cmake is required for building bitnet.cpp
if ! command -v cmake &>/dev/null; then
    echo "  → cmake ਇੰਸਟਾਲ ਕਰ ਰਹੇ ਹਾਂ..."
    brew install cmake
else
    echo "  ✓ cmake already installed: $(cmake --version | head -1)"
fi

# ninja speeds up the build
if ! command -v ninja &>/dev/null; then
    echo "  → ninja ਇੰਸਟਾਲ ਕਰ ਰਹੇ ਹਾਂ..."
    brew install ninja
else
    echo "  ✓ ninja already installed"
fi

echo ""

# ─────────────────────────────────────────────
# STEP 2: Clone BitNet repository
# ─────────────────────────────────────────────
echo ">>> [2/6] BitNet ਰੈਪੋ ਕਲੋਨ ਕਰ ਰਹੇ ਹਾਂ..."

if [ -d "$BITNET_DIR" ]; then
    echo "  ✓ BitNet directory ਪਹਿਲਾਂ ਤੋਂ ਮੌਜੂਦ ਹੈ: $BITNET_DIR"
    echo "  → latest changes pull ਕਰ ਰਹੇ ਹਾਂ..."
    cd "$BITNET_DIR"
    git pull --recurse-submodules
else
    git clone --recursive https://github.com/microsoft/BitNet.git "$BITNET_DIR"
    cd "$BITNET_DIR"
fi

echo ""

# ─────────────────────────────────────────────
# STEP 3: Python virtual environment ਬਣਾਓ
# ─────────────────────────────────────────────
echo ">>> [3/6] Python virtual environment ਸੈੱਟਅੱਪ ਕਰ ਰਹੇ ਹਾਂ..."

VENV_DIR="$BITNET_DIR/.venv-bitnet"
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv "$VENV_DIR"
    echo "  ✓ venv ਬਣਾਇਆ: $VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"
echo "  ✓ venv activated"

# Upgrade pip
pip install --upgrade pip --quiet

# Install BitNet requirements
echo "  → requirements.txt ਇੰਸਟਾਲ ਕਰ ਰਹੇ ਹਾਂ..."
pip install -r "$BITNET_DIR/requirements.txt" --quiet

# Install huggingface_hub for model download
pip install huggingface_hub --quiet
echo "  ✓ dependencies installed"
echo ""

# ─────────────────────────────────────────────
# STEP 4: Model Download + Build Kernels
# ─────────────────────────────────────────────
echo ">>> [4/6] Falcon3-10B-Instruct-1.58bit ਡਾਊਨਲੋਡ ਅਤੇ kernels ਬਿਲਡ ਕਰ ਰਹੇ ਹਾਂ..."
echo "  (ਇਹ ਪਹਿਲੀ ਵਾਰ ਕੁਝ ਮਿੰਟ ਲਵੇਗਾ - model ~4GB ਹੈ)"
echo ""

cd "$BITNET_DIR"
$PYTHON_BIN setup_env.py \
    --hf-repo tiiuae/Falcon3-10B-Instruct-1.58bit \
    -q i2_s

echo ""
echo "  ✓ Model downloaded and kernels compiled!"
echo ""

# ─────────────────────────────────────────────
# STEP 5: Quick inference test
# ─────────────────────────────────────────────
echo ">>> [5/6] Quick inference test ਚਲਾ ਰਹੇ ਹਾਂ..."
echo ""

MODEL_FILE="$BITNET_DIR/models/Falcon3-10B-1.58bit/ggml-model-i2_s.gguf"
if [ ! -f "$MODEL_FILE" ]; then
    # Try alternate naming convention
    MODEL_FILE=$(find "$BITNET_DIR/models" -name "*.gguf" 2>/dev/null | head -1)
fi

if [ -z "$MODEL_FILE" ]; then
    echo "ERROR: GGUF model file ਨਹੀਂ ਮਿਲਿਆ। setup_env.py ਦੁਬਾਰਾ ਚਲਾਓ।"
    exit 1
fi

echo "  Model file: $MODEL_FILE"
echo ""

$PYTHON_BIN "$BITNET_DIR/run_inference.py" \
    -m "$MODEL_FILE" \
    -p "ਤੁਸੀਂ ਇੱਕ ਮਦਦਗਾਰ AI ਅਸਿਸਟੈਂਟ ਹੋ। ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ।" \
    -n 100 \
    -t 4

echo ""

# ─────────────────────────────────────────────
# STEP 6: Save run script for future use
# ─────────────────────────────────────────────
echo ">>> [6/6] ਭਵਿੱਖ ਲਈ run script ਬਣਾ ਰਹੇ ਹਾਂ..."

cat > "$HOME/run_bitnet.sh" << 'RUNSCRIPT'
#!/bin/bash
# BitNet b1.58 - Falcon3-10B - Quick Run Script
BITNET_DIR="$HOME/BitNet"
VENV_DIR="$BITNET_DIR/.venv-bitnet"
MODEL_FILE=$(find "$BITNET_DIR/models" -name "*.gguf" 2>/dev/null | head -1)

source "$VENV_DIR/bin/activate"

echo "BitNet b1.58 - Falcon3-10B-Instruct (Chat Mode)"
echo "================================================"
echo "Model: $MODEL_FILE"
echo ""

python3 "$BITNET_DIR/run_inference.py" \
    -m "$MODEL_FILE" \
    -p "You are a helpful AI assistant." \
    -t 4 \
    -c 2048 \
    -cnv
RUNSCRIPT

chmod +x "$HOME/run_bitnet.sh"
echo "  ✓ Saved to: ~/run_bitnet.sh"
echo ""

echo "========================================================"
echo "  ✅ BitNet b1.58 Setup ਮੁਕੰਮਲ ਹੋਇਆ!"
echo ""
echo "  Chat mode ਵਿੱਚ ਚਲਾਉਣ ਲਈ:"
echo "    ~/run_bitnet.sh"
echo ""
echo "  ਜਾਂ ਸਿੱਧਾ command:"
echo "    source ~/BitNet/.venv-bitnet/bin/activate"
echo "    python3 ~/BitNet/run_inference.py \\"
echo "      -m $MODEL_FILE \\"
echo "      -p \"You are a helpful assistant\" \\"
echo "      -t 4 -cnv"
echo "========================================================"
