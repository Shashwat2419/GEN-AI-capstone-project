"""Personalized Travel Itinerary Planner - FastAPI backend.

Run locally:   uvicorn main:app --reload --port 8000
Interactive docs:  http://localhost:8000/docs
"""
import os
import re
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

import db
import services
from core.config import (
    APP_NAME, BUDGETS, DIETS, INTERESTS, MAX_DAYS, PACES, PARTIES, PROVIDER_DEMO, SLOTS,
    SWAP_SUGGESTIONS, VIBES,
)
from core.llm import LLMError
from core.pdf_export import build_pdf
from core.planner import PlannerError

app = FastAPI(title=APP_NAME, version="1.0.0")

_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------------------- #
# Error handling - always return {"detail": "..."} so the UI can show it
# --------------------------------------------------------------------------- #
@app.exception_handler(PlannerError)
async def _planner_error(_: Request, exc: PlannerError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def _llm_error(_: Request, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(db.NotFound)
async def _not_found(_: Request, exc: db.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(db.StorageError)
async def _storage_error(_: Request, exc: db.StorageError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class LLMConfig(BaseModel):
    provider: str = "Demo"            # "Demo", "Gemini" or "Groq"
    api_key: str = Field("", max_length=300)
    model: str = Field("", max_length=100)


class Prefs(BaseModel):
    destination: str = Field("", max_length=80)
    vibe: Literal[tuple(VIBES)] = "Cultural"
    days: int = Field(4, ge=1, le=MAX_DAYS)
    start_date: date
    budget: Literal[tuple(BUDGETS)] = "Moderate"
    party: Literal[tuple(PARTIES)] = "Couple"
    pace: Literal[tuple(PACES)] = "Moderate"
    interests: List[Literal[tuple(INTERESTS)]] = []
    diet: Literal[tuple(DIETS)] = "No preference"


class PlanRequest(BaseModel):
    prefs: Prefs
    llm: LLMConfig = LLMConfig()


class ItineraryBody(BaseModel):
    itinerary: Dict[str, Any]


class SwapRequest(BaseModel):
    itinerary: Dict[str, Any]
    day_index: int = Field(ge=0)
    slot: str
    item_index: int = Field(0, ge=0)
    instruction: str = Field(max_length=300)
    llm: LLMConfig = LLMConfig()


class RegenRequest(BaseModel):
    itinerary: Dict[str, Any]
    day_index: int = Field(ge=0)
    instruction: str = Field("", max_length=300)
    llm: LLMConfig = LLMConfig()


class SaveTripRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    itinerary: Dict[str, Any]
    trip_id: Optional[str] = None


_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_TRIP_ID = re.compile(r"^[A-Za-z0-9-]{1,40}$")


def _client(x_client_id: Optional[str]) -> str:
    if not x_client_id or not _ID.match(x_client_id):
        raise HTTPException(status_code=400, detail="Missing or invalid X-Client-Id header.")
    return x_client_id


def _trip_id(value: str) -> str:
    if not _TRIP_ID.match(value):
        raise HTTPException(status_code=400, detail="Invalid trip id.")
    return value


def _llm(cfg: LLMConfig) -> Dict:
    return services.resolve_llm(cfg.provider, cfg.api_key, cfg.model)


def _pdf_response(itin: Dict) -> Response:
    itin = services.validate_itinerary(itin)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", itin["destination"]) or "trip"
    return Response(content=build_pdf(itin), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="%s_itinerary.pdf"' % name,
                             "Access-Control-Expose-Headers": "Content-Disposition"})


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok", "storage": db.backend_name(),
            "server_ai_keys": {"Gemini": bool(os.environ.get("GEMINI_API_KEY")),
                               "Groq": bool(os.environ.get("GROQ_API_KEY"))}}


@app.get("/api/options")
def options():
    return {"vibes": VIBES, "budgets": BUDGETS, "parties": PARTIES, "paces": PACES,
            "interests": INTERESTS, "diets": DIETS, "max_days": MAX_DAYS, "slots": SLOTS,
            "swap_suggestions": SWAP_SUGGESTIONS, "providers": ["Demo", "Gemini", "Groq"],
            "demo_cities": ["Jaipur", "Goa", "Manali", "Paris", "Bangkok"]}


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
@app.post("/api/recommend")
def recommend_destinations(req: PlanRequest):
    llm = _llm(req.llm)
    recs = services.do_recommend(req.prefs.model_dump(), llm)
    return {"recommendations": recs, "mode": "Demo" if llm["provider"] == PROVIDER_DEMO else llm["provider"]}


@app.post("/api/itinerary")
def create_itinerary(req: PlanRequest):
    return services.do_generate(req.prefs.model_dump(), _llm(req.llm))


@app.post("/api/summary")
def summary(body: ItineraryBody):
    """Recompute totals after the user edits exchange rates."""
    return services.with_analytics(services.validate_itinerary(body.itinerary))


@app.post("/api/swap")
def swap(req: SwapRequest):
    itin = services.validate_itinerary(req.itinerary)
    return services.do_swap(itin, req.day_index, req.slot, req.item_index, req.instruction, _llm(req.llm))


@app.post("/api/regenerate-day")
def regenerate(req: RegenRequest):
    itin = services.validate_itinerary(req.itinerary)
    return services.do_regenerate(itin, req.day_index, req.instruction, _llm(req.llm))


@app.post("/api/pdf")
def pdf_from_body(body: ItineraryBody):
    return _pdf_response(body.itinerary)


# --------------------------------------------------------------------------- #
# Saved trips (Supabase)
# --------------------------------------------------------------------------- #
@app.get("/api/trips")
def get_trips(x_client_id: Optional[str] = Header(None)):
    return {"trips": db.list_trips(_client(x_client_id))}


@app.post("/api/trips")
def save_trip(req: SaveTripRequest, x_client_id: Optional[str] = Header(None)):
    itin = services.validate_itinerary(req.itinerary)
    trip_id = _trip_id(req.trip_id) if req.trip_id else None
    new_id = db.save_trip(_client(x_client_id), req.name.strip(), itin, trip_id)
    return {"id": new_id}


@app.get("/api/trips/{trip_id}")
def get_trip(trip_id: str, x_client_id: Optional[str] = Header(None)):
    itin = db.load_trip(_client(x_client_id), _trip_id(trip_id))
    return services.with_analytics(services.validate_itinerary(itin))


@app.delete("/api/trips/{trip_id}")
def remove_trip(trip_id: str, x_client_id: Optional[str] = Header(None)):
    db.delete_trip(_client(x_client_id), _trip_id(trip_id))
    return {"deleted": True}


@app.get("/api/trips/{trip_id}/pdf")
def trip_pdf(trip_id: str, x_client_id: Optional[str] = Header(None)):
    return _pdf_response(db.load_trip(_client(x_client_id), _trip_id(trip_id)))
