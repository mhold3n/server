#!/usr/bin/env bash
set -e

echo "Bootstrapping environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

echo "Installing project and extras..."
pip install -e ".[dev,eval]"

echo "Detecting platform for torch..."
OS_NAME=$(uname -s)
ARCH=$(uname -m)

if [ "$OS_NAME" == "Darwin" ] && [ "$ARCH" == "arm64" ]; then
    echo "Apple Silicon detected. Installing standard MPS-compatible PyTorch..."
    pip install torch torchvision torchaudio
    pip install -e ".[apple]"
elif command -v nvidia-smi &> /dev/null; then
    echo "NVIDIA GPU detected. Installing CUDA PyTorch..."
    pip install torch torchvision torchaudio
    pip install -e ".[nvidia]"
else
    echo "CPU only or unrecognized system. Installing CPU PyTorch..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

echo "Verifying environment..."
python scripts/verify_env.py
