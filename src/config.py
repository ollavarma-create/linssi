"""Configuration management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class YoloConfig:
    """YOLO object detection settings."""

    model: str = "yolov8m.pt"
    confidence: float = 0.35
    device: str | int = 0


@dataclass
class FacesConfig:
    """Face recognition settings including reference directory and model choice."""

    reference_dir: str = "data/faces"
    similarity_threshold: float = 0.45
    model: str = "buffalo_l"


@dataclass
class LLMConfig:
    """Settings for the LM Studio vision-LLM description stage."""

    api_url: str = "http://localhost:11434/api/chat"
    model: str = "qwen3-VL-8B"
    prompt: str = "Describe this photo briefly in 2-5 sentences in Finnish."
    timeout: int = 20
    max_retries: int = 2
    max_tokens: int = 512
    image_max_side: int = 512
    threads: int = 1


@dataclass
class PipelineConfig:
    """Flags controlling which pipeline stages are enabled."""

    exif: bool = True
    yolo: bool = True
    faces: bool = True
    llm: bool = True


@dataclass
class ProcessingConfig:
    """Batch processing settings shared across pipeline stages."""

    batch_size: int = 10
    skip_existing: bool = True
    max_workers: int = 2


@dataclass
class AppConfig:
    """Root application configuration aggregating all sub-configs."""

    image_dirs: list[str] = field(default_factory=lambda: ["~/Pictures"])
    extensions: list[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png", ".tiff", ".webp", ".heic"]
    )
    excluded_dirs: list[str] = field(default_factory=lambda: ["_PAlbTN"])
    database_path: str = "data/image_analyzer.db"
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    yolo: YoloConfig = field(default_factory=YoloConfig)
    faces: FacesConfig = field(default_factory=FacesConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file, falling back to defaults."""
    project_root = Path(__file__).parent.parent
    paths_to_try = [
        config_path,
        project_root / "config.local.yaml",
        project_root / "config.yaml",
    ]

    for path in paths_to_try:
        if path and Path(path).exists():
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
            return _parse_config(raw)

    return AppConfig()


def _parse_config(raw: dict) -> AppConfig:
    """Parse raw YAML dict into typed config."""
    config = AppConfig()

    if "image_dirs" in raw:
        config.image_dirs = raw["image_dirs"]
    if "extensions" in raw:
        config.extensions = raw["extensions"]
    if "excluded_dirs" in raw:
        config.excluded_dirs = raw["excluded_dirs"]
    if db := raw.get("database"):
        config.database_path = db.get("path", config.database_path)

    if p := raw.get("pipeline"):
        config.pipeline = PipelineConfig(**{k: p.get(k, True) for k in ["exif", "yolo", "faces", "llm"]})

    if y := raw.get("yolo"):
        config.yolo = YoloConfig(
            model=y.get("model", "yolov8m.pt"),
            confidence=y.get("confidence", 0.35),
            device=y.get("device", 0),
        )

    if fc := raw.get("faces"):
        config.faces = FacesConfig(
            reference_dir=fc.get("reference_dir", "data/faces"),
            similarity_threshold=fc.get("similarity_threshold", 0.45),
            model=fc.get("model", "buffalo_l"),
        )

    if lm := raw.get("llm"):
        config.llm = LLMConfig(
            api_url=lm.get("api_url", "http://localhost:11434/api/chat"),
            model=lm.get("model", "qwen3-VL-8B"),
            prompt=lm.get("prompt", "Describe this image in detail."),
            timeout=lm.get("timeout", 20),
            max_retries=lm.get("max_retries", 2),
            max_tokens=lm.get("max_tokens", 512),
            image_max_side=lm.get("image_max_side", 512),
            threads=lm.get("threads", 1),
        )

    if pr := raw.get("processing"):
        config.processing = ProcessingConfig(
            batch_size=pr.get("batch_size", 10),
            skip_existing=pr.get("skip_existing", True),
            max_workers=pr.get("max_workers", 2),
        )

    return config
