from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage

try:
    from ..utils import normalizar_tema
except ImportError:
    from utils import normalizar_tema


historial: List[HumanMessage | AIMessage] = []
intentos_por_tema: Dict[str, int] = {}


def construir_historial_texto() -> str:
    return "\n".join(
        [
            f"Estudiante: {m.content}"
            if isinstance(m, HumanMessage)
            else f"Tutor: {m.content}"
            for m in historial
        ]
    )


def registrar_interaccion(pregunta: str, respuesta: str) -> None:
    global historial

    historial.append(HumanMessage(content=pregunta))
    historial.append(AIMessage(content=respuesta))
    if len(historial) > 20:
        historial = historial[-20:]


def registrar_intento(tema: str) -> int:
    tema_normalizado = normalizar_tema(tema)
    intentos_por_tema[tema_normalizado] = intentos_por_tema.get(tema_normalizado, 0) + 1
    return intentos_por_tema[tema_normalizado]


def reiniciar_memoria() -> None:
    global historial, intentos_por_tema

    historial = []
    intentos_por_tema = {}
