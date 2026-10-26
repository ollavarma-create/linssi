#!/usr/bin/env python3
"""
Detect GPU compute capability and install the correct face recognition backend.

Run once:
    python install_face_deps.py

GPU compute >= 7.0 (Volta+, e.g. RTX/GTX 1070 Ti and newer)
    → installs facenet-pytorch  (FacenetBackend, uses PyTorch CUDA directly)

GPU compute < 7.0 (Pascal, e.g. GTX 1080 Ti = sm_61)
    → installs onnxruntime-gpu + insightface  (InsightFaceBackend, ONNX Runtime)

No GPU / no CUDA
    → installs onnxruntime (CPU) + insightface  (CPU fallback)

Note: the decision is based on GPU compute capability (sm_XX), NOT on the
CUDA driver version shown by nvidia-smi. A GTX 1080 Ti running CUDA 12.x
drivers is still sm_61 and needs the InsightFace backend.
"""
import subprocess
import sys


def get_compute_major() -> int | None:
    """Return GPU compute capability major (e.g. 6 for sm_61), or None."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            line = result.stdout.strip().splitlines()[0]  # e.g. "6.1"
            return int(line.split(".")[0])
    except Exception:
        pass

    # Fallback: PyTorch (may be absent or report False for unsupported GPUs)
    try:
        import torch
        if torch.cuda.is_available():
            major, _ = torch.cuda.get_device_capability(0)
            return major
    except Exception:
        pass

    return None


def pip_install(*packages: str):
    subprocess.run([sys.executable, "-m", "pip", "install", *packages], check=True)


def main():
    compute_major = get_compute_major()

    if compute_major is None:
        print("No CUDA-capable GPU detected — installing CPU-only face backend.")
        pip_install("onnxruntime>=1.16", "insightface>=0.7")
        print("\nInstalled: InsightFace (CPU mode)")
        print("Backend: InsightFaceBackend (CPU)")

    elif compute_major >= 7:
        print(f"GPU compute sm_{compute_major}.x (Volta or newer) — installing FaceNet-PyTorch backend.")
        print("Note: onnxruntime-gpu is NOT installed (not needed for sm_70+).")
        pip_install("facenet-pytorch>=0.5.0")
        print("\nInstalled: facenet-pytorch")
        print("Backend: FacenetBackend (CUDA)")

    else:  # sm_61 and older (Pascal, Maxwell, Kepler)
        print(f"GPU compute sm_{compute_major}.x (Pascal or older) — installing InsightFace + onnxruntime-gpu.")
        print("Note: facenet-pytorch is NOT installed (PyTorch cu118+ drops sm_61 support).")
        print("Note: onnxruntime-gpu >= 1.17 supports CUDA 12.x system libraries (libcurand, libcudnn9).")
        print("      Requires: sudo apt install libcurand-12-5 libcudnn9-cuda-12")
        # albumentations>=2.0 requires numpy>=2.0 which breaks torch 2.0.x.
        # Pin albumentations<2.0 so numpy stays on 1.x.
        pip_install("albumentations<2.0", "onnxruntime-gpu>=1.17", "insightface>=0.7")
        print("\nInstalled: InsightFace + onnxruntime-gpu")
        print("Backend: InsightFaceBackend (CUDA)")

    print("\nDone. The correct backend will be selected automatically at startup.")


if __name__ == "__main__":
    main()
