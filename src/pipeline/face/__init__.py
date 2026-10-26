"""Face backend auto-selection based on GPU compute capability."""
import logging

logger = logging.getLogger("face.backend")

# Minimum GPU compute capability (major) for FacenetBackend.
# Volta (sm_70) is the oldest architecture with full PyTorch CUDA support.
# Pascal (sm_61) and older must use InsightFaceBackend via onnxruntime.
_FACENET_MIN_COMPUTE_MAJOR = 7


def get_face_backend(model_name: str = "buffalo_l"):
    """
    Auto-select face backend based on GPU compute capability.

    GPU compute >= 7.0 (Volta+)  →  FacenetBackend   (facenet-pytorch)
    GPU compute <  7.0 (Pascal-) →  InsightFaceBackend (onnxruntime-gpu)
    No CUDA / unavailable        →  InsightFaceBackend (CPU)

    Note: uses torch.cuda.get_device_capability(), NOT torch.version.cuda.
    torch.version.cuda reflects the PyTorch build target (e.g. 12.8),
    which can be much higher than what the physical GPU actually supports.
    """
    compute_major, has_cuda = _detect_gpu_compute()

    if has_cuda and compute_major is not None and compute_major >= _FACENET_MIN_COMPUTE_MAJOR:
        logger.info(f"GPU compute sm_{compute_major}.x — selecting FacenetBackend")
        try:
            from .facenet_backend import FacenetBackend
            return FacenetBackend()
        except ImportError as e:
            logger.error(
                f"FacenetBackend unavailable ({e}). "
                "Run: python install_face_deps.py"
            )
            raise RuntimeError(
                f"facenet-pytorch is not installed. "
                f"GPU compute capability is sm_{compute_major}.x. "
                f"Run `python install_face_deps.py` to install the correct backend."
            ) from e

    else:
        reason = (
            "no CUDA" if not has_cuda
            else f"GPU compute sm_{compute_major}.x < sm_{_FACENET_MIN_COMPUTE_MAJOR}.0 (Pascal or older)"
        )
        logger.info(f"{reason} — selecting InsightFaceBackend")
        try:
            from .insightface_backend import InsightFaceBackend
            providers = _available_ort_providers(has_cuda)
            logger.info(f"onnxruntime providers: {providers}")
            return InsightFaceBackend(model_name=model_name, providers=providers)
        except ImportError as e:
            logger.error(
                f"InsightFaceBackend unavailable ({e}). "
                "Run: python install_face_deps.py"
            )
            raise RuntimeError(
                f"insightface/onnxruntime is not installed. "
                f"Run `python install_face_deps.py` to install the correct backend."
            ) from e


def _detect_gpu_compute() -> tuple[int | None, bool]:
    """
    Return (compute_capability_major, cuda_available).

    Primary: nvidia-smi query — works regardless of which PyTorch build is
    installed.  This is critical for Pascal GPUs (sm_61, e.g. GTX 1080 Ti)
    where PyTorch 2.2+ cu118 builds do not support the device and
    torch.cuda.is_available() returns False even though the GPU is present.

    Fallback: torch.cuda.get_device_capability() for environments without
    nvidia-smi (e.g. WSL without the CLI in PATH, Docker without host tools).
    """
    # --- Primary: nvidia-smi ---
    major = _detect_via_nvidia_smi()
    if major is not None:
        return major, True

    # --- Fallback: PyTorch CUDA ---
    try:
        import torch
        if not torch.cuda.is_available():
            return None, False
        major, _minor = torch.cuda.get_device_capability(0)
        return major, True
    except Exception:
        return None, False


def _available_ort_providers(has_cuda: bool) -> list[str]:
    """
    Return onnxruntime execution providers filtered to what is actually
    available in the installed onnxruntime package.

    Plain 'onnxruntime' (CPU-only build) does not include CUDAExecutionProvider.
    'onnxruntime-gpu' does. Filtering avoids a UserWarning when requesting a
    provider that isn't compiled in.
    """
    try:
        import onnxruntime as rt
        available = set(rt.get_available_providers())
    except Exception:
        return ['CPUExecutionProvider']

    preferred = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if has_cuda else ['CPUExecutionProvider']
    return [p for p in preferred if p in available] or ['CPUExecutionProvider']


def _detect_via_nvidia_smi() -> int | None:
    """
    Query compute capability major version via nvidia-smi.
    Returns None if nvidia-smi is absent, fails, or no GPU is found.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().splitlines()[0]   # e.g. "6.1"
        major = int(line.split(".")[0])
        return major
    except Exception:
        return None
