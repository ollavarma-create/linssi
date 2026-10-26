"""FaceBackend Protocol — common interface for face recognition backends."""
from typing import Protocol, runtime_checkable
import numpy as np
from dataclasses import dataclass


@dataclass
class FaceResult:
    """Single face detection result containing bounding box and normalised embedding."""

    bbox: list[float]          # [x1, y1, x2, y2]
    normed_embedding: np.ndarray


@runtime_checkable
class FaceBackend(Protocol):
    """Protocol defining the interface that all face recognition backends must satisfy."""

    def get_embeddings(self, image) -> list[FaceResult]:
        """Return a FaceResult for every face detected in the image."""
        ...
