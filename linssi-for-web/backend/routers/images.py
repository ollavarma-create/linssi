"""Image metadata endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

router = APIRouter()


def get_db(request: Request):
    return request.app.state.db


@router.get("/images")
def list_images(
    request: Request,
    query: str = Query(default=""),
    query_and: list[str] = Query(default=[]),
    query_or: list[str] = Query(default=[]),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    camera: str = Query(default=""),
    obj: str = Query(default=""),
    person: str = Query(default=""),
    limit: int = Query(default=50),
    db=Depends(get_db),
):
    return db.get_images(
        query=query,
        query_and=query_and,
        query_or=query_or,
        date_from=date_from,
        date_to=date_to,
        camera=camera,
        obj=obj,
        person=person,
        limit=limit,
    )


@router.get("/images/{image_id}")
def get_image(image_id: int, db=Depends(get_db)):
    detail = db.get_image_detail(image_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Image not found")
    return detail


@router.get("/meta/cameras")
def meta_cameras(db=Depends(get_db)):
    return db.get_distinct_cameras()


@router.get("/meta/objects")
def meta_objects(db=Depends(get_db)):
    return db.get_distinct_objects()


@router.get("/meta/persons")
def meta_persons(db=Depends(get_db)):
    return db.get_distinct_persons()


@router.get("/meta/stats")
def meta_stats(db=Depends(get_db)):
    s = db.stats()
    oldest, newest = db.get_date_range()
    return {
        **s,
        "date_from": oldest,
        "date_to": newest,
        "top_cameras": db.get_top_cameras(5),
        "top_objects": db.get_top_objects(5),
        "top_persons": db.get_top_persons(5),
        "top_locations": db.get_top_locations(5),
    }
