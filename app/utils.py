import json
import re


def extraer_json(texto: str, fallback: dict) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if not match:
            return fallback
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return fallback


def normalizar_tema(tema: str) -> str:
    tema = (tema or "tema_no_identificado").strip().lower()
    tema = re.sub(r"[^a-z0-9áéíóúñü\s_-]", "", tema)
    tema = re.sub(r"\s+", "_", tema)
    return tema or "tema_no_identificado"
