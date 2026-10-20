from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.observations import ObservationError, generate_observations
from app.transcription import transcribe

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="MedicalAssistant")


class Transcript(BaseModel):
    text: str = Field(min_length=1)


class Observations(BaseModel):
    text: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# `def` et non `async def` : Whisper est bloquant, FastAPI l'exécute dans un thread.
@app.post("/api/transcriptions")
def create_transcription(audio: UploadFile) -> Transcript:
    try:
        text = transcribe(audio.file)
    except Exception as e:
        # Ne pas journaliser le contenu : l'audio est une donnée de santé.
        raise HTTPException(422, "Audio illisible ou format non pris en charge.") from e
    if not text:
        raise HTTPException(422, "Aucune parole détectée dans l'enregistrement.")
    return Transcript(text=text)


@app.post("/api/observations")
async def create_observations(transcript: Transcript) -> Observations:
    try:
        return Observations(text=await generate_observations(transcript.text))
    except ObservationError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
