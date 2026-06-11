from __future__ import annotations

from queue import Queue
from typing import Any

from state import TutorState


AGENTE_NOMBRES = {
    "orquestador": "Orquestador",
    "motivador": "Motivador",
    "generador": "Generador de Contenido",
    "especialista": "Especialista Técnico",
    "pedagogo": "Pedagogo Socrático",
    "evaluador": "Evaluador de Calidad",
}

AGENTE_COLORES = {
    "Orquestador": "#2563eb",
    "Motivador": "#22c55e",
    "Especialista Técnico": "#f97316",
    "Generador de Contenido": "#a855f7",
    "Pedagogo Socrático": "#eab308",
    "Evaluador de Calidad": "#64748b",
}


def obtener_cola(state: TutorState) -> Queue | None:
    cola = state.get("event_queue")
    return cola if isinstance(cola, Queue) else None


def emitir_evento(state: TutorState, evento: dict[str, Any]) -> list[dict[str, Any]]:
    cola = obtener_cola(state)
    if cola is not None:
        cola.put(evento)
    debate_events = list(state.get("debate_events", []))
    if evento.get("tipo") != "respuesta_final":
        debate_events.append(evento)
    return debate_events


def emitir(
    state: TutorState,
    *,
    agente: str,
    modelo: str,
    ronda: int,
    accion: str,
    mensaje: str,
    estado: str = "working",
    critica_a: str = "",
    veredicto: str = "",
) -> list[dict[str, Any]]:
    evento: dict[str, Any] = {
        "agente": agente,
        "modelo": modelo,
        "ronda": ronda,
        "accion": accion,
        "mensaje": mensaje,
        "estado": estado,
    }
    if critica_a:
        evento["critica_a"] = critica_a
    if veredicto:
        evento["veredicto"] = veredicto
    return emitir_evento(state, evento)


def emitir_inicio(
    state: TutorState,
    clave_agente: str,
    modelo: str,
    ronda: int,
    mensaje: str = "Analizando contexto...",
) -> list[dict[str, Any]]:
    return emitir(
        state,
        agente=AGENTE_NOMBRES.get(clave_agente, clave_agente),
        modelo=modelo,
        ronda=ronda,
        accion="iniciando",
        mensaje=mensaje,
        estado="working",
    )
