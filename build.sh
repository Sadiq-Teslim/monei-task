#!/usr/bin/env bash
# Render build script
set -o errexit

# Install CPU-only PyTorch first (saves ~1.5 GB vs full CUDA build)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
pip install -r requirements.txt
