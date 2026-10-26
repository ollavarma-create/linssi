#!/usr/bin/env python3
"""
Face recognition worker — runs inside .venv-face, isolated from the main process.

If this process crashes (SIGABRT, cuDNN error, etc.), the main app is unaffected.

Protocol (newline-delimited JSON on stdin/stdout):

  Startup (first line on stdin):
    {"model":"buffalo_l","reference_dir":"/abs/path","similarity_threshold":0.45,
     "cache_path":"/abs/path/.embeddings.pkl"}

  Response:
    {"status":"ready","persons":3}
    {"status":"error","message":"..."}

  Per image (stdin):
    {"cmd":"process","path":"/abs/path/image.jpg"}

  Response (stdout):
    {"status":"ok","faces":[{"name":"Alice","confidence":0.82,"bbox":[x1,y1,x2,y2]}]}
    {"status":"error","message":"..."}

  Shutdown:
    {"cmd":"quit"}  (or close stdin)
"""

import json
import logging
import os
import pickle
import sys
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("face_worker")

_IMG_EXT = {".jpg", ".jpeg", ".png"}


# ── Backends ──────────────────────────────────────────────────────────────────

class InsightFaceRunner:
    """CPU onnxruntime backend — no system CUDA libraries required."""

    def __init__(self, model_name: str):
        os.environ.setdefault("ORT_DISABLE_CUDNN_FRONTEND", "1")
        import insightface
        app = insightface.app.FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1)
        self._app = app

    def get_embeddings(self, img) -> list[tuple[np.ndarray, list]]:
        """Return normalised face embeddings and bounding boxes for all faces in the image."""
        result = []
        for face in self._app.get(img):
            emb = face.normed_embedding
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            result.append((emb, face.bbox.tolist()))
        return result


class FacenetRunner:
    """facenet-pytorch backend — Volta+ GPU (sm_70+)."""

    def __init__(self):
        import torch
        from facenet_pytorch import InceptionResnetV1, MTCNN
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._mtcnn = MTCNN(keep_all=True, device=self._device)
        self._resnet = InceptionResnetV1(pretrained="vggface2").eval().to(self._device)

    def get_embeddings(self, img) -> list[tuple[np.ndarray, list]]:
        """Return normalised face embeddings and bounding boxes for all faces in the image."""
        import torch
        from PIL import Image as PILImage
        pil = PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        boxes, _ = self._mtcnn.detect(pil)
        if boxes is None:
            return []
        faces_tensor = self._mtcnn(pil)
        if faces_tensor is None:
            return []
        if faces_tensor.dim() == 3:
            faces_tensor = faces_tensor.unsqueeze(0)
        with torch.no_grad():
            embeddings = self._resnet(faces_tensor.to(self._device)).cpu().numpy()
        result = []
        for emb, box in zip(embeddings, boxes):
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            result.append((emb, box.tolist()))
        return result


def make_runner(model_name: str):
    """Return the best available face backend — InsightFace preferred, then FaceNet.

    Raises:
        RuntimeError: When neither backend is importable.
    """
    try:
        import insightface  # noqa: F401
        logger.warning("Using InsightFaceRunner (CPU)")
        return InsightFaceRunner(model_name)
    except ImportError:
        pass
    try:
        import facenet_pytorch  # noqa: F401
        logger.warning("Using FacenetRunner")
        return FacenetRunner()
    except ImportError:
        pass
    raise RuntimeError(
        "No face backend available in this environment. "
        "Run install.sh to set up .venv-face correctly."
    )


# ── Reference embeddings ──────────────────────────────────────────────────────

def load_or_build_embeddings(runner, reference_dir: Path, cache_path: Path) -> dict:
    """Load reference embeddings from cache, or build them from reference photo directories.

    Args:
        runner: A face backend instance with a ``get_embeddings`` method.
        reference_dir: Root directory containing one subdirectory per known person.
        cache_path: Path to the pickle file used for caching computed embeddings.

    Returns:
        Dict mapping person name to a list of normalised embedding arrays.
    """
    ref_files = [
        f for f in reference_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in _IMG_EXT
    ]
    if not ref_files:
        return {}

    if cache_path.exists():
        cache_mtime = cache_path.stat().st_mtime
        if all(f.stat().st_mtime <= cache_mtime for f in ref_files):
            try:
                with open(cache_path, "rb") as fh:
                    cached = pickle.load(fh)
                person_dirs = [d for d in reference_dir.iterdir() if d.is_dir()]
                if len(cached) == len(person_dirs):
                    logger.warning(f"Loaded {len(cached)} persons from cache")
                    return cached
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")

    known: dict[str, list[np.ndarray]] = {}
    for person_dir in sorted(reference_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        embeddings = []
        for photo in person_dir.iterdir():
            if photo.suffix.lower() not in _IMG_EXT:
                continue
            try:
                img = cv2.imread(str(photo))
                if img is None:
                    continue
                for emb, _ in runner.get_embeddings(img):
                    embeddings.append(emb)
            except Exception:
                continue
        if embeddings:
            known[person_dir.name] = embeddings

    if known:
        try:
            with open(cache_path, "wb") as fh:
                pickle.dump(known, fh)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    logger.warning(f"Built embeddings for {len(known)} persons")
    return known


def identify(
    embedding: np.ndarray,
    known: dict[str, list[np.ndarray]],
    threshold: float,
) -> tuple[str, float]:
    """Match an embedding against known persons using cosine similarity.

    Args:
        embedding: Normalised face embedding to identify.
        known: Dict mapping person name to reference embeddings.
        threshold: Minimum similarity score required for a positive match.

    Returns:
        Tuple of (person_name, similarity_score). Name is 'unknown' when below threshold.
    """
    if not known:
        return "unknown", 0.0
    emb = embedding / (np.linalg.norm(embedding) or 1.0)
    best_name, best_sim = "unknown", -1.0
    for name, refs in known.items():
        sim = float(np.max(np.dot(refs, emb)))
        if sim > best_sim:
            best_sim, best_name = sim, name
    if best_sim < threshold:
        return "unknown", best_sim
    return best_name, best_sim


# ── I/O helpers ───────────────────────────────────────────────────────────────

def send(obj: dict):
    """Write a JSON object followed by a newline to stdout and flush immediately."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Run the face worker event loop: initialise the backend, then process images from stdin."""
    # Read init config (first stdin line)
    try:
        line = sys.stdin.readline()
        if not line:
            send({"status": "error", "message": "no init config received"})
            sys.exit(1)
        cfg = json.loads(line)
    except Exception as e:
        send({"status": "error", "message": f"config parse error: {e}"})
        sys.exit(1)

    model_name = cfg.get("model", "buffalo_l")
    reference_dir = Path(cfg["reference_dir"])
    similarity_threshold = float(cfg.get("similarity_threshold", 0.45))
    cache_path = Path(cfg.get("cache_path", str(reference_dir / ".embeddings.pkl")))

    try:
        runner = make_runner(model_name)
    except Exception as e:
        send({"status": "error", "message": str(e)})
        sys.exit(1)

    known: dict = {}
    if reference_dir.exists():
        try:
            known = load_or_build_embeddings(runner, reference_dir, cache_path)
        except Exception as e:
            logger.warning(f"Reference embeddings failed: {e}")

    send({"status": "ready", "persons": len(known)})

    # Process loop
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            msg = json.loads(raw_line)
        except Exception:
            send({"status": "error", "message": "invalid JSON"})
            continue

        cmd = msg.get("cmd", "process")

        if cmd == "quit":
            break

        if cmd == "process":
            path = msg.get("path", "")
            try:
                img = cv2.imread(path)
                if img is None:
                    send({"status": "error", "message": f"cannot read image: {path}"})
                    continue
                faces = []
                for emb, bbox in runner.get_embeddings(img):
                    name, confidence = identify(emb, known, similarity_threshold)
                    faces.append({
                        "name": name,
                        "confidence": float(confidence),
                        "bbox": bbox,
                    })
                send({"status": "ok", "faces": faces})
            except Exception as e:
                send({"status": "error", "message": str(e)})


if __name__ == "__main__":
    main()
