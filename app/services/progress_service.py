from __future__ import annotations

from typing import Dict

TEMAS_SILABO = [
    "variables",
    "operadores",
    "secuencial",
    "condicionales",
    "bucles",
    "descomposicion",
]

TEMAS_ETIQUETAS = {
    "variables": "Variables y tipos de datos",
    "operadores": "Operadores",
    "secuencial": "Estructura secuencial",
    "condicionales": "Condicionales (if/else)",
    "bucles": "Bucles (for/while)",
    "descomposicion": "Descomposición de problemas",
}

MAPEO_TEMA = {
    "variable": "variables",
    "variables": "variables",
    "tipo": "variables",
    "tipos": "variables",
    "dato": "variables",
    "operador": "operadores",
    "operadores": "operadores",
    "expresion": "operadores",
    "secuencial": "secuencial",
    "secuencia": "secuencial",
    "condicional": "condicionales",
    "condicionales": "condicionales",
    "if": "condicionales",
    "else": "condicionales",
    "bucle": "bucles",
    "bucles": "bucles",
    "while": "bucles",
    "for": "bucles",
    "repeticion": "bucles",
    "descomposicion": "descomposicion",
    "descomposición": "descomposicion",
    "problema": "descomposicion",
    "pseudocodigo": "descomposicion",
    "pseudocódigo": "descomposicion",
    "algoritmo": "descomposicion",
}

progreso_por_tema: Dict[str, int] = {tema: 0 for tema in TEMAS_SILABO}
intentos_previos: Dict[str, int] = {}


def _progreso_inicial() -> Dict[str, int]:
    return {tema: 0 for tema in TEMAS_SILABO}


def normalizar_tema_progreso(topic: str) -> str:
    texto = (topic or "").strip().lower()
    if not texto or texto == "tema_no_identificado":
        return "variables"
    for clave, valor in MAPEO_TEMA.items():
        if clave in texto:
            return valor
    return "variables"


def obtener_progreso() -> Dict[str, int]:
    return dict(progreso_por_tema)


def reiniciar_progreso() -> None:
    global progreso_por_tema, intentos_previos
    progreso_por_tema = _progreso_inicial()
    intentos_previos = {}


def _incrementar(tema: str, puntos: int) -> None:
    global progreso_por_tema
    actual = progreso_por_tema.get(tema, 0)
    progreso_por_tema[tema] = min(100, actual + puntos)


def actualizar_progreso(
    topic: str,
    *,
    interaccion: bool = True,
    respuesta_correcta: bool = False,
    attempt_count: int | None = None,
    student_progress: str = "",
) -> Dict[str, int]:
    tema = normalizar_tema_progreso(topic)

    if interaccion:
        _incrementar(tema, 5)

    if respuesta_correcta or student_progress == "avance_correcto":
        _incrementar(tema, 10)

    if attempt_count is not None:
        previo = intentos_previos.get(tema)
        if previo is not None and attempt_count < previo:
            _incrementar(tema, 15)
        intentos_previos[tema] = attempt_count

    return obtener_progreso()
