"""LLM image description via LM Studio (OpenAI-compatible API)."""
import base64
import io
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image
from pathlib import Path
from src.config import LLMConfig
from .base import PipelineStage


class LLMDescriber(PipelineStage):
    """Pipeline stage that calls a vision LLM to generate a text description of each image."""

    stage_name = "llm"

    def __init__(self, db, config: LLMConfig):
        super().__init__(db)
        self.config = config
        self.session = requests.Session()
        self._executor = ThreadPoolExecutor(max_workers=getattr(config, 'threads', 1))

    def _encode_image(self, file_path: str) -> str:
        """Encode image as data URI, resizing large images to fit image_max_side."""
        img = Image.open(file_path)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        max_side = getattr(self.config, 'image_max_side', 512)
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{b64}"

    def process(self, image_id: int, file_path: str):
        """Encode the image and POST it to the LLM API, saving the resulting description."""
        data_uri = self._encode_image(file_path)

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.config.prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                    ],
                }
            ],
            "max_tokens": getattr(self.config, 'max_tokens', 512),
            "temperature": 0.3,
        }

        for attempt in range(self.config.max_retries + 1):
            try:
                resp = self.session.post(
                    self.config.api_url,
                    json=payload,
                    timeout=self.config.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                description = data["choices"][0]["message"]["content"]
                self.db.save_llm_description(
                    image_id, description, self.config.model
                )
                self.logger.debug(
                    f"{file_path}: {len(description)} chars"
                )
                return
            except (requests.RequestException, KeyError, IndexError) as e:
                if attempt < self.config.max_retries:
                    self.logger.warning(
                        f"Retry {attempt + 1} for {file_path}: {e}"
                    )
                else:
                    raise
