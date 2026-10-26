"""Face recognition stage — delegates to face_worker.py running in .venv-face."""
import json
import logging
import subprocess
from pathlib import Path

from src.config import FacesConfig
from src.database import Database
from .base import PipelineStage

logger = logging.getLogger("face_recognizer")

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_VENV_FACE_PYTHON = _PROJECT_ROOT / ".venv-face" / "bin" / "python"
_WORKER_SCRIPT = _PROJECT_ROOT / "src" / "pipeline" / "face_worker.py"


class FaceRecognizer(PipelineStage):
    """Detect and identify faces via a subprocess worker in .venv-face."""

    stage_name = "faces"

    def __init__(self, db: Database, config: FacesConfig):
        super().__init__(db)
        self.config = config
        self._worker: subprocess.Popen | None = None
        self._worker_ok = False
        self._start_worker()

    # ── Worker lifecycle ──────────────────────────────────────────────────────

    def _start_worker(self):
        """Launch the face worker subprocess and send the initial configuration."""
        if not _VENV_FACE_PYTHON.exists():
            logger.error(
                f".venv-face not found at {_VENV_FACE_PYTHON}. "
                "Run install.sh first."
            )
            return

        try:
            self._worker = subprocess.Popen(
                [str(_VENV_FACE_PYTHON), str(_WORKER_SCRIPT)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.error(f"Failed to start face worker: {e}")
            return

        cfg = {
            "model": self.config.model,
            "reference_dir": str(Path(self.config.reference_dir).resolve()),
            "similarity_threshold": self.config.similarity_threshold,
            "cache_path": str(
                Path(self.config.reference_dir).resolve() / ".embeddings.pkl"
            ),
        }
        self._send(cfg)

        response = self._recv()
        if response and response.get("status") == "ready":
            n = response.get("persons", 0)
            logger.info(f"Face worker ready — {n} known persons")
            self._worker_ok = True
        else:
            msg = response.get("message", "unknown error") if response else "no response"
            logger.error(f"Face worker failed to initialise: {msg}")
            self._worker_ok = False

    def _send(self, obj: dict):
        """Write a JSON message to the worker's stdin."""
        if self._worker and self._worker.stdin:
            try:
                self._worker.stdin.write(json.dumps(obj) + "\n")
                self._worker.stdin.flush()
            except BrokenPipeError:
                self._worker_ok = False

    def _recv(self) -> dict | None:
        """Read the next JSON response from the worker, skipping non-JSON stdout noise."""
        if not (self._worker and self._worker.stdout):
            return None
        # InsightFace / onnxruntime print non-JSON lines to stdout during model
        # loading ("Applied providers:", "find model:", "set det-size:" etc.).
        # Loop until we get a valid JSON line or the pipe closes.
        while True:
            try:
                line = self._worker.stdout.readline()
            except Exception:
                self._worker_ok = False
                return None
            if not line:
                # Pipe closed — worker died (SIGABRT or other crash)
                rc = self._worker.wait()
                logger.error(f"Face worker exited unexpectedly (exit code {rc})")
                self._worker_ok = False
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"Worker stdout (skipped): {line}")
                continue

    # ── PipelineStage interface ───────────────────────────────────────────────

    def process(self, image_id: int, file_path: str):
        """Send the image to the worker for face detection and save results to the database."""
        if not self._worker_ok:
            # Worker is down — mark as error so the pipeline doesn't retry silently
            raise RuntimeError(
                "Face worker is not running. "
                "Check logs for startup errors (run install.sh if .venv-face is missing)."
            )

        self._send({"cmd": "process", "path": file_path})
        response = self._recv()

        if response is None:
            raise RuntimeError("Face worker died during processing")

        if response.get("status") == "error":
            raise RuntimeError(f"Face worker error: {response.get('message', '?')}")

        detections = [
            {
                "person_name": f["name"],
                "confidence": f["confidence"],
                "bbox": f["bbox"],
            }
            for f in response.get("faces", [])
        ]
        self.db.save_face_detections(image_id, detections)
        if detections:
            names = [d["person_name"] for d in detections]
            self.logger.debug(f"{file_path}: {names}")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def __del__(self):
        """Gracefully shut down the worker subprocess on garbage collection."""
        if self._worker and self._worker.poll() is None:
            try:
                self._send({"cmd": "quit"})
                self._worker.wait(timeout=5)
            except Exception:
                self._worker.kill()
