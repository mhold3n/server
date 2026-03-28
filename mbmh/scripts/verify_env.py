import sys
try:
    import torch
    import transformers
    import accelerate
    import peft
    import trl
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

print(f"Python: {sys.version.split()[0]}")
print(f"Torch: {torch.__version__}")
print(f"Transformers: {transformers.__version__}")
print(f"Accelerate: {accelerate.__version__}")
print(f"PEFT: {peft.__version__}")
print(f"TRL: {trl.__version__}")

cuda_available = torch.cuda.is_available()
mps_available = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()

print(f"CUDA Available: {cuda_available}")
print(f"MPS Available: {mps_available}")

# Platform requirement validation
if sys.platform == "darwin":
    import platform
    if platform.machine() == "arm64" and not mps_available:
        print("ERROR: Apple Silicon detected but MPS is unavailable.")
        sys.exit(1)
else:
    import shutil
    if shutil.which("nvidia-smi") and not cuda_available:
        print("ERROR: NVIDIA GPU detected but CUDA is unavailable.")
        sys.exit(1)

# Run tensor op
if cuda_available:
    device = "cuda"
elif mps_available:
    device = "mps"
else:
    device = "cpu"

print(f"Selected device: {device}")
try:
    x = torch.rand(2, 2).to(device)
    y = x @ x
    print("Tensor op succeeded.")
except Exception as e:
    print(f"ERROR: Tensor op failed on {device}: {e}")
    sys.exit(1)

print("Environment verification passed.")
