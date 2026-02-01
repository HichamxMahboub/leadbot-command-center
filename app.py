import asyncio
import threading
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scraper import scrape_google_maps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
LATEST_JSON = os.path.join(RESULTS_DIR, "latest_results.json")
LATEST_XLSX = os.path.join(RESULTS_DIR, "latest_results.xlsx")
LATEST_CSV = os.path.join(RESULTS_DIR, "latest_results.csv")

app = FastAPI()


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


class ScrapeRequest(BaseModel):
    keyword: str
    location: str


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Optional[WebSocket] = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active = websocket

    def disconnect(self, websocket: WebSocket) -> None:
        if self.active == websocket:
            self.active = None

    async def send(self, message: str) -> None:
        if self.active:
            await self.active.send_text(message)


manager = ConnectionManager()
current_task: Optional[asyncio.Task] = None
current_stop_event: Optional[threading.Event] = None

SUGGESTIONS = [
    "Real Estate",
    "Dentists",
    "Lawyers",
    "Marketing Agencies",
    "Accounting Firms",
    "Roofing Contractors",
    "Plumbers",
    "Electricians",
    "HVAC Services",
    "Chiropractors",
    "Physical Therapists",
    "Med Spas",
    "Car Dealerships",
    "Auto Repair",
    "Restaurants",
    "Coffee Shops",
    "Gyms",
    "Personal Trainers",
    "Insurance Brokers",
    "Mortgage Brokers",
    "Real Estate Agents",
    "IT Consultants",
    "Software Companies",
    "Web Design Agencies",
    "SEO Agencies",
    "Managed IT Services",
    "Cybersecurity Firms",
    "Logistics Companies",
    "Freight Forwarders",
    "Construction Companies",
    "Architects",
    "Interior Designers",
    "Event Planners",
    "Catering Companies",
    "Hotels",
    "Property Management",
    "Dental Labs",
    "Veterinary Clinics",
    "Optometrists",
    "Pharmacies",
    "Home Health Care",
    "Legal Consultants",
    "Recruiting Agencies",
    "Staffing Firms",
    "E-commerce Brands",
    "Manufacturers",
    "Wholesalers",
    "B2B SaaS",
    "Coworking Spaces",
    "Cleaning Services",
]


@app.get("/")
async def index() -> HTMLResponse:
    with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as handle:
        return HTMLResponse(handle.read())


async def run_scrape(keyword: str, location: str, deep_search: bool) -> None:
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = threading.Event()
    global current_stop_event
    current_stop_event = stop_event

    async def forward_logs() -> None:
        while True:
            message = await queue.get()
            await manager.send(message)
            if message == "__SCRAPE_DONE__":
                break

    def log_callback(message: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, message)

    async def run_playwright() -> List[Dict[str, Any]]:
        print("SCRAPER STARTED")
        await manager.send("Starting scraper...")
        return await loop.run_in_executor(
            None,
            scrape_google_maps,
            keyword,
            location,
            log_callback,
            100,
            False,
            stop_event,
            deep_search,
        )

    forward_task = asyncio.create_task(forward_logs())
    leads = await run_playwright()
    loop.call_soon_threadsafe(queue.put_nowait, "__SCRAPE_DONE__")
    await forward_task

    _save_results(leads)
    await manager.send("Scrape finished. Results ready.")
    current_stop_event = None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send("Invalid message format.")
                continue

            if payload.get("type") == "SUGGEST":
                query = payload.get("query", "").strip().lower()
                matches = [
                    item
                    for item in SUGGESTIONS
                    if query and query in item.lower()
                ][:6]
                if not query:
                    matches = SUGGESTIONS[:6]
                await manager.send("__SUGGEST__:" + json.dumps(matches))

            if payload.get("type") == "PING":
                await manager.send("__PONG__")

            if payload.get("type") == "start":
                keyword = payload.get("keyword", "").strip()
                location = payload.get("location", "").strip()
                deep_search = bool(payload.get("deep_search", False))
                if not keyword or not location:
                    await manager.send("Keyword and location are required.")
                    continue
                global current_task
                if current_task and not current_task.done():
                    await manager.send("A scrape is already running.")
                    continue
                current_task = asyncio.create_task(run_scrape(keyword, location, deep_search))

            if payload.get("type") == "stop":
                if current_stop_event:
                    current_stop_event.set()
                    await manager.send("Stopping scraper...")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _save_results(leads: List[Dict[str, Any]]) -> None:
    with open(LATEST_JSON, "w", encoding="utf-8") as handle:
        json.dump(leads, handle, ensure_ascii=False, indent=2)

    df = pd.DataFrame(leads)
    df.to_excel(LATEST_XLSX, index=False)
    df.to_csv(LATEST_CSV, index=False)


@app.post("/scrape")
async def scrape(request: ScrapeRequest) -> JSONResponse:
    if not manager.active:
        return JSONResponse({"error": "WebSocket not connected."}, status_code=400)

    await run_scrape(request.keyword, request.location, False)
    return JSONResponse({"status": "started"})


@app.get("/download")
async def download_results() -> FileResponse:
    if not os.path.exists(LATEST_XLSX):
        return FileResponse(
            os.path.join(BASE_DIR, "index.html"),
            media_type="text/html",
        )
    return FileResponse(
        LATEST_XLSX,
        filename=f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )


@app.get("/download-csv")
async def download_csv() -> FileResponse:
    if not os.path.exists(LATEST_CSV):
        return FileResponse(
            os.path.join(BASE_DIR, "index.html"),
            media_type="text/html",
        )
    return FileResponse(
        LATEST_CSV,
        filename=f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
    )
