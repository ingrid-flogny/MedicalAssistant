"""Transcription locale de l'audio avec Whisper : l'enregistrement ne quitte pas le serveur."""

import os
from functools import lru_cache
from typing import BinaryIO

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "fr")


@lru_cache(maxsize=1)
def _model():
    # Import différé : le reste de l'application démarre même là où les
    # bibliothèques natives de Whisper ne se chargent pas (poste Windows verrouillé).
    from faster_whisper import WhisperModel

    # int8 : tourne sur CPU sans GPU, suffisant pour un pod OpenShift standard.
    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe(audio: BinaryIO) -> str:
    """Transcrit un flux audio (webm, wav, mp3...) sans l'écrire sur disque."""
    segments, _ = _model().transcribe(audio, language=WHISPER_LANGUAGE, vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()
