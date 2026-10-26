"""YOLO object detection stage."""
from ultralytics import YOLO
from src.config import YoloConfig
from .base import PipelineStage


class YoloDetector(PipelineStage):
    """Pipeline stage that runs YOLOv8 object detection on each image."""

    stage_name = "yolo"

    def __init__(self, db, config: YoloConfig):
        super().__init__(db)
        self.config = config
        self._model = None

    @property
    def model(self):
        """Load and cache the YOLO model on first access, moving it to the configured device."""
        if self._model is None:
            self.logger.info(f"Loading YOLO model: {self.config.model}")
            self._model = YOLO(self.config.model)
            device = self.config.device
            if device != "cpu":
                device_str = f"cuda:{device}" if isinstance(device, int) else device
                self.logger.info(f"Moving YOLO model to {device_str}")
                self._model.to(device_str)
        return self._model

    def process(self, image_id: int, file_path: str):
        """Run YOLO inference on the image and save detections to the database."""
        results = self.model(
            file_path, conf=self.config.confidence,
            device=self.config.device, verbose=False,
        )
        detections = []
        for result in results:
            for box in result.boxes:
                detections.append({
                    "class_name": result.names[int(box.cls[0])],
                    "confidence": float(box.conf[0]),
                    "bbox": [float(x) for x in box.xyxy[0]],
                })
        self.db.save_yolo_detections(image_id, detections)
        self.logger.debug(f"{file_path}: {len(detections)} objects found")
