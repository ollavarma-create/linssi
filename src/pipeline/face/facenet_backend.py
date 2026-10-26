"""FaceNet-PyTorch backend — for CUDA >= 12."""
import numpy as np
import cv2
from .face_backend import FaceResult


class FacenetBackend:
    """Face recognition backend using facenet-pytorch (MTCNN + InceptionResnetV1)."""

    def __init__(self):
        from facenet_pytorch import MTCNN, InceptionResnetV1
        import torch
        self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self._mtcnn = MTCNN(keep_all=True, device=self._device)
        self._resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self._device)

    def get_embeddings(self, image) -> list[FaceResult]:
        """Detect all faces in a BGR image and return normalised embeddings with bounding boxes."""
        import torch
        from PIL import Image as PILImage
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)

        boxes, _ = self._mtcnn.detect(pil_img)
        if boxes is None:
            return []

        faces_tensor = self._mtcnn(pil_img)
        if faces_tensor is None:
            return []

        results = []
        with torch.no_grad():
            embeddings = self._resnet(faces_tensor.to(self._device)).cpu().numpy()

        for i, (box, emb) in enumerate(zip(boxes, embeddings)):
            normed = emb / np.linalg.norm(emb)
            results.append(FaceResult(bbox=box.tolist(), normed_embedding=normed))
        return results
