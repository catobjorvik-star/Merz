from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .catalogue_service import get_catalogue_data, get_catalogue_family, search_catalogue

router = APIRouter(tags=["catalogue"])


@router.get("/api/catalogue")
def catalogue_index():
    return get_catalogue_data()


@router.get("/api/catalogue/search")
def catalogue_search(
    q: str = Query(default=""),
    category: str = Query(default="Alle"),
):
    return search_catalogue(q, category)


@router.get("/api/catalogue/family/{code}")
def catalogue_family(code: str):
    item = get_catalogue_family(code)
    if not item:
        raise HTTPException(status_code=404, detail="Katalogfamilie nicht gefunden.")
    return item
