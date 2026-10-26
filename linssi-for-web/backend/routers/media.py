"""Image media endpoints — thumbnail and preview serving."""

import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps

router = APIRouter()


def get_db(request: Request):
    return request.app.state.db


def _serve_image(image_id: int, max_size: tuple[int, int], db) -> StreamingResponse:
    detail = db.get_image_detail(image_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Image not found")

    file_path = detail.get("file_path", "")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    img = Image.open(file_path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail(max_size, Image.LANCZOS)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/jpeg",
        headers={"Cache-Control": "max-age=86400"},
    )


@router.get("/media/thumbnail/{image_id}")
def thumbnail(image_id: int, db=Depends(get_db)):
    return _serve_image(image_id, (200, 200), db)


@router.get("/media/preview/{image_id}")
def preview(image_id: int, db=Depends(get_db)):
    return _serve_image(image_id, (1200, 1200), db)
