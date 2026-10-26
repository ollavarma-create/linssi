"""InsightFace backend — for Pascal GPUs or CPU fallback."""
import logging
import os
import subprocess
import sys

import numpy as np

from .face_backend import FaceResult

logger = logging.getLogger("face.insightface_backend")

# Subprocess script that tests CUDA inference. Run in isolation so that a
# C-level SIGABRT (exit 6) from broken CUDA/cuDNN libs cannot kill the main
# process — Python try/except cannot catch OS signals raised by native code.
_CUDA_TEST_SCRIPT = """
import os, sys
os.environ['ORT_DISABLE_CUDNN_FRONTEND'] = '1'
import onnxruntime as ort
import numpy as np
import insightface

providers = [p for p in ['CUDAExecutionProvider', 'CPUExecutionProvider']
             if p in ort.get_available_providers()]
if 'CUDAExecutionProvider' not in providers:
    sys.exit(1)

app = insightface.app.FaceAnalysis(name=sys.argv[1], providers=providers)
app.prepare(ctx_id=0)
dummy = np.zeros((112, 112, 3), dtype=np.uint8)
app.get(dummy)
print('OK')
"""


def _cuda_works(model_name: str) -> bool:
    """
    Test CUDAExecutionProvider in a subprocess.

    A missing CUDA/cuDNN library can raise SIGABRT (exit 6) at the C level —
    that cannot be caught by Python. Running the test in a subprocess means a
    crash there does not affect the main process.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", _CUDA_TEST_SCRIPT, model_name],
            capture_output=True, text=True, timeout=120,
        )
        ok = result.returncode == 0 and "OK" in result.stdout
        if not ok:
            reason = (result.stderr.strip().splitlines() or ["exit code " + str(result.returncode)])[-1]
            logger.debug(f"CUDA subprocess test failed: {reason}")
        return ok
    except subprocess.TimeoutExpired:
        logger.debug("CUDA subprocess test timed out")
        return False
    except Exception as e:
        logger.debug(f"CUDA subprocess test error: {e}")
        return False


class InsightFaceBackend:
    """InsightFace backend with automatic GPU/CPU fallback via a subprocess safety test."""

    def __init__(self, model_name: str = "buffalo_l", providers=None):
        os.environ.setdefault("ORT_DISABLE_CUDNN_FRONTEND", "1")

        import onnxruntime as ort

        available = set(ort.get_available_providers())
        if providers is None:
            providers = [p for p in ['CUDAExecutionProvider', 'CPUExecutionProvider'] if p in available]

        cuda_requested = 'CUDAExecutionProvider' in providers

        if cuda_requested:
            if _cuda_works(model_name):
                logger.info("CUDAExecutionProvider OK — using GPU")
                self._app = self._init_app(model_name, providers, ctx_id=0)
            else:
                logger.warning(
                    "CUDAExecutionProvider failed subprocess test "
                    "— falling back to CPUExecutionProvider"
                )
                self._app = self._init_app(model_name, ['CPUExecutionProvider'], ctx_id=-1)
        else:
            self._app = self._init_app(model_name, providers, ctx_id=-1)

    def _init_app(self, model_name: str, providers: list, ctx_id: int):
        """Initialise and prepare the InsightFace FaceAnalysis app."""
        import insightface
        app = insightface.app.FaceAnalysis(name=model_name, providers=providers)
        app.prepare(ctx_id=ctx_id)
        return app

    def get_embeddings(self, image) -> list[FaceResult]:
        """Detect all faces in the image and return normalised embeddings with bounding boxes."""
        faces = self._app.get(image)
        return [
            FaceResult(
                bbox=face.bbox.tolist(),
                normed_embedding=face.normed_embedding / np.linalg.norm(face.normed_embedding),
            )
            for face in faces
        ]
