"""Base class for pipeline stages."""
import logging
from abc import ABC, abstractmethod
from src.database import Database


class PipelineStage(ABC):
    """Abstract base class for all pipeline stages.

    Subclasses must set ``stage_name`` and implement ``process``.
    The ``run`` method handles skip-existing logic and error logging.
    """

    stage_name: str = "base"

    def __init__(self, db: Database):
        self.db = db
        self.logger = logging.getLogger(f"pipeline.{self.stage_name}")

    @abstractmethod
    def process(self, image_id: int, file_path: str):
        """Run the stage-specific processing on a single image.

        Args:
            image_id: Database row id of the image.
            file_path: Absolute path to the image file on disk.
        """
        ...

    def run(self, image_id: int, file_path: str, force: bool = False) -> bool:
        """Execute the stage, skipping already-done images unless force is True.

        Args:
            image_id: Database row id of the image.
            file_path: Absolute path to the image file on disk.
            force: When True, re-process even if stage is already marked done.

        Returns:
            True on success, False if an exception was caught.
        """
        if not force and self.db.is_stage_done(image_id, self.stage_name):
            return True
        try:
            self.process(image_id, file_path)
            self.db.mark_stage(image_id, self.stage_name, "done")
            return True
        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            self.db.mark_stage(image_id, self.stage_name, "error", str(e))
            return False