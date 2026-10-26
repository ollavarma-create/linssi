"""Tests for face backend auto-selection logic.

These tests mock torch.cuda so they run without a GPU.
The key behaviour: selection is based on GPU compute capability,
NOT on torch.version.cuda (the PyTorch build target).

Real-world case that motivated this: GTX 1080 Ti (sm_61, Pascal) with
PyTorch 2.10+cu128.  torch.version.cuda == "12" → old logic wrongly
selected FacenetBackend, which crashes because sm_61 is not compiled in.
The correct selection is InsightFaceBackend via onnxruntime.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_torch_mock(cuda_available: bool, compute_major: int | None, compute_minor: int = 0,
                     cuda_version_str: str = "12.8"):
    """Return a minimal torch mock suitable for patching src.pipeline.face."""
    torch_mock = MagicMock()
    torch_mock.version.cuda = cuda_version_str if cuda_available else None
    torch_mock.cuda.is_available.return_value = cuda_available
    if cuda_available and compute_major is not None:
        torch_mock.cuda.get_device_capability.return_value = (compute_major, compute_minor)
    else:
        torch_mock.cuda.get_device_capability.side_effect = RuntimeError("no device")
    return torch_mock


# ---------------------------------------------------------------------------
# _detect_gpu_compute
# ---------------------------------------------------------------------------

class TestDetectGpuCompute:
    def _call(self, torch_mock):
        with patch.dict(sys.modules, {"torch": torch_mock}):
            # Re-import to pick up fresh module state
            import importlib
            import src.pipeline.face as face_mod
            importlib.reload(face_mod)
            return face_mod._detect_gpu_compute()

    def test_volta_gpu(self):
        """V100 — sm_70 — should report compute 7, cuda available."""
        mock = _make_torch_mock(cuda_available=True, compute_major=7, cuda_version_str="11.8")
        major, has_cuda = self._call(mock)
        assert major == 7
        assert has_cuda is True

    def test_ampere_gpu(self):
        """RTX 3090 — sm_86 — compute 8."""
        mock = _make_torch_mock(cuda_available=True, compute_major=8, cuda_version_str="12.8")
        major, has_cuda = self._call(mock)
        assert major == 8
        assert has_cuda is True

    def test_pascal_gpu(self):
        """GTX 1080 Ti — sm_61 — compute 6, even when torch.version.cuda == 12.8."""
        mock = _make_torch_mock(cuda_available=True, compute_major=6, cuda_version_str="12.8")
        major, has_cuda = self._call(mock)
        assert major == 6
        assert has_cuda is True

    def test_no_cuda(self):
        """CPU-only machine — no CUDA available."""
        mock = _make_torch_mock(cuda_available=False, compute_major=None)
        major, has_cuda = self._call(mock)
        assert major is None
        assert has_cuda is False

    def test_torch_not_installed(self):
        """torch not present at all — graceful fallback."""
        with patch.dict(sys.modules, {"torch": None}):
            import importlib
            import src.pipeline.face as face_mod
            importlib.reload(face_mod)
            major, has_cuda = face_mod._detect_gpu_compute()
        assert major is None
        assert has_cuda is False


# ---------------------------------------------------------------------------
# get_face_backend — backend selection
# ---------------------------------------------------------------------------

class TestGetFaceBackend:
    """Verify which backend class is instantiated for each GPU scenario."""

    def _call_with_gpu(self, compute_major: int | None, cuda_available: bool,
                       cuda_version_str: str = "12.8"):
        torch_mock = _make_torch_mock(
            cuda_available=cuda_available,
            compute_major=compute_major,
            cuda_version_str=cuda_version_str,
        )
        facenet_mock = MagicMock()
        insightface_mock = MagicMock()

        facenet_backend_cls = MagicMock(return_value=MagicMock())
        insightface_backend_cls = MagicMock(return_value=MagicMock())

        with patch.dict(sys.modules, {"torch": torch_mock}):
            import importlib
            import src.pipeline.face as face_mod
            importlib.reload(face_mod)

            with (
                patch.object(face_mod, "_detect_gpu_compute",
                             return_value=(compute_major, cuda_available)),
                patch("src.pipeline.face.facenet_backend.FacenetBackend",
                      facenet_backend_cls, create=True),
                patch("src.pipeline.face.insightface_backend.InsightFaceBackend",
                      insightface_backend_cls, create=True),
            ):
                # Patch the submodule imports inside get_face_backend
                facenet_module = types.ModuleType("src.pipeline.face.facenet_backend")
                facenet_module.FacenetBackend = facenet_backend_cls
                insightface_module = types.ModuleType("src.pipeline.face.insightface_backend")
                insightface_module.InsightFaceBackend = insightface_backend_cls

                with patch.dict(sys.modules, {
                    "src.pipeline.face.facenet_backend": facenet_module,
                    "src.pipeline.face.insightface_backend": insightface_module,
                }):
                    face_mod.get_face_backend()

        return facenet_backend_cls, insightface_backend_cls

    def test_pascal_1080ti_selects_insightface(self):
        """GTX 1080 Ti: sm_61 with torch built for CUDA 12.8 → InsightFaceBackend."""
        facenet_cls, insightface_cls = self._call_with_gpu(
            compute_major=6, cuda_available=True, cuda_version_str="12.8"
        )
        insightface_cls.assert_called_once()
        facenet_cls.assert_not_called()

    def test_volta_selects_facenet(self):
        """V100: sm_70 → FacenetBackend."""
        facenet_cls, insightface_cls = self._call_with_gpu(
            compute_major=7, cuda_available=True
        )
        facenet_cls.assert_called_once()
        insightface_cls.assert_not_called()

    def test_ampere_selects_facenet(self):
        """RTX 3090: sm_86 → FacenetBackend."""
        facenet_cls, insightface_cls = self._call_with_gpu(
            compute_major=8, cuda_available=True
        )
        facenet_cls.assert_called_once()
        insightface_cls.assert_not_called()

    def test_no_cuda_selects_insightface_cpu(self):
        """No GPU at all → InsightFaceBackend with CPUExecutionProvider."""
        facenet_cls, insightface_cls = self._call_with_gpu(
            compute_major=None, cuda_available=False
        )
        insightface_cls.assert_called_once()
        call_kwargs = insightface_cls.call_args
        providers = call_kwargs.kwargs.get("providers") or call_kwargs.args[1]
        assert providers == ["CPUExecutionProvider"]
        facenet_cls.assert_not_called()

    def test_pascal_insightface_gets_cuda_providers(self):
        """Pascal with CUDA → InsightFaceBackend should get CUDAExecutionProvider."""
        torch_mock = _make_torch_mock(cuda_available=True, compute_major=6,
                                      cuda_version_str="12.8")
        insightface_backend_cls = MagicMock(return_value=MagicMock())
        facenet_backend_cls = MagicMock(return_value=MagicMock())

        with patch.dict(sys.modules, {"torch": torch_mock}):
            import importlib
            import src.pipeline.face as face_mod
            importlib.reload(face_mod)

            insightface_module = types.ModuleType("src.pipeline.face.insightface_backend")
            insightface_module.InsightFaceBackend = insightface_backend_cls
            facenet_module = types.ModuleType("src.pipeline.face.facenet_backend")
            facenet_module.FacenetBackend = facenet_backend_cls

            with patch.dict(sys.modules, {
                "src.pipeline.face.facenet_backend": facenet_module,
                "src.pipeline.face.insightface_backend": insightface_module,
            }):
                face_mod.get_face_backend()

        insightface_backend_cls.assert_called_once()
        call_kwargs = insightface_backend_cls.call_args
        providers = call_kwargs.kwargs.get("providers") or call_kwargs.args[1]
        assert "CUDAExecutionProvider" in providers
