"""Hardware-independent tests for face backend selection.

No GPU, PyTorch, OpenCV, NumPy or ONNX Runtime installation
is required. These tests verify selection logic, not actual
GPU inference or model compatibility.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

import src.pipeline.face as face_mod


def make_torch_mock(cuda_available, compute_major,
                    cuda_version="12.8"):
    mock = MagicMock()
    mock.version.cuda = cuda_version if cuda_available else None
    mock.cuda.is_available.return_value = cuda_available

    if cuda_available and compute_major is not None:
        mock.cuda.get_device_capability.return_value = (
            compute_major, 0
        )
    else:
        mock.cuda.get_device_capability.side_effect = (
            RuntimeError("no device")
        )

    return mock


class TestDetectGpuCompute:

    @pytest.mark.parametrize(
        "major,cuda_version",
        [(6, "12.8"), (7, "11.8"), (8, "12.8")],
    )
    def test_torch_gpu_detection(self, major, cuda_version):
        torch_mock = make_torch_mock(
            True, major, cuda_version
        )

        with (
            patch.dict(sys.modules, {"torch": torch_mock}),
            patch.object(
                face_mod, "_detect_via_nvidia_smi",
                return_value=None,
            ),
        ):
            assert face_mod._detect_gpu_compute() == (
                major, True
            )

    def test_no_cuda(self):
        torch_mock = make_torch_mock(False, None)

        with (
            patch.dict(sys.modules, {"torch": torch_mock}),
            patch.object(
                face_mod, "_detect_via_nvidia_smi",
                return_value=None,
            ),
        ):
            assert face_mod._detect_gpu_compute() == (
                None, False
            )

    def test_torch_not_installed(self):
        with (
            patch.dict(sys.modules, {"torch": None}),
            patch.object(
                face_mod, "_detect_via_nvidia_smi",
                return_value=None,
            ),
        ):
            assert face_mod._detect_gpu_compute() == (
                None, False
            )

    @pytest.mark.parametrize("major", [6, 7, 8])
    def test_nvidia_smi_detection(self, major):
        with (
            patch.dict(sys.modules, {"torch": None}),
            patch.object(
                face_mod, "_detect_via_nvidia_smi",
                return_value=major,
            ),
        ):
            assert face_mod._detect_gpu_compute() == (
                major, True
            )


class TestGetFaceBackend:

    def call_backend(self, major, has_cuda, providers):
        facenet_cls = MagicMock()
        insightface_cls = MagicMock()

        facenet_module = types.ModuleType(
            "src.pipeline.face.facenet_backend"
        )
        facenet_module.FacenetBackend = facenet_cls

        insightface_module = types.ModuleType(
            "src.pipeline.face.insightface_backend"
        )
        insightface_module.InsightFaceBackend = insightface_cls

        ort_module = types.ModuleType("onnxruntime")
        ort_module.get_available_providers = MagicMock(
            return_value=providers
        )

        with (
            patch.dict(sys.modules, {
                "src.pipeline.face.facenet_backend":
                    facenet_module,
                "src.pipeline.face.insightface_backend":
                    insightface_module,
                "onnxruntime": ort_module,
            }),
            patch.object(
                face_mod, "_detect_gpu_compute",
                return_value=(major, has_cuda),
            ),
        ):
            face_mod.get_face_backend()

        return facenet_cls, insightface_cls

    @pytest.mark.parametrize("major", [7, 8])
    def test_modern_gpu_selects_facenet(self, major):
        facenet, insightface = self.call_backend(
            major, True, ["CPUExecutionProvider"]
        )
        facenet.assert_called_once()
        insightface.assert_not_called()

    def test_pascal_selects_insightface(self):
        facenet, insightface = self.call_backend(
            6, True, ["CPUExecutionProvider"]
        )
        insightface.assert_called_once()
        facenet.assert_not_called()

    def test_cpu_selects_insightface(self):
        facenet, insightface = self.call_backend(
            None, False, ["CPUExecutionProvider"]
        )
        insightface.assert_called_once_with(
            model_name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        facenet.assert_not_called()

    def test_pascal_with_cuda_provider(self):
        facenet, insightface = self.call_backend(
            6, True, [
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
        )
        insightface.assert_called_once_with(
            model_name="buffalo_l",
            providers=[
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ],
        )
        facenet.assert_not_called()

    def test_pascal_without_cuda_provider(self):
        facenet, insightface = self.call_backend(
            6, True, ["CPUExecutionProvider"]
        )
        insightface.assert_called_once_with(
            model_name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        facenet.assert_not_called()

    def test_cpu_does_not_request_cuda(self):
        facenet, insightface = self.call_backend(
            None, False, [
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
        )
        insightface.assert_called_once_with(
            model_name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        facenet.assert_not_called()


class TestOrtProviders:

    def test_onnxruntime_not_installed(self):
        with patch.dict(sys.modules, {"onnxruntime": None}):
            assert face_mod._available_ort_providers(True) == [
                "CPUExecutionProvider"
            ]

    def test_provider_query_failure(self):
        ort = MagicMock()
        ort.get_available_providers.side_effect = RuntimeError(
            "provider query failed"
        )

        with patch.dict(sys.modules, {"onnxruntime": ort}):
            assert face_mod._available_ort_providers(True) == [
                "CPUExecutionProvider"
            ]
