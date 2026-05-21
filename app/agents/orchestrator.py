try:
    from ..config import ALLOWED_TOPICS
    from ..services.memory_service import obtener_intentos_tema
    from ..state import TutorState
    from ..utils import detectar_codigo, extraer_json, formatear_historial
except ImportError:
    from config import ALLOWED_TOPICS
    from services.memory_service import obtener_intentos_tema
    from state import TutorState
    from utils import detectar_codigo, extraer_json, formatear_historial


EMOCIONES_FRUSTRACION = {"frustracion", "desmotivacion", "ansiedad"}
BLOQUEO_FRASES = (
    "no sé",
    "no se",
    "no entiendo",
    "explícame",
    "explicame",
    "no puedo",
    "ayúdame",
    "ayudame",
    "me rindo",
    "no lo entiendo",
)
PROGRESO_FRASES = (
    "creo que",
    "entiendo",
    "sería",
    "seria",
    "es cuando",
    "se mantiene",
    "se cumple",
    "termina",
    "el número",
    "el numero",
    "la condición",
    "la condicion",
    "contador",
    "repeticiones",
)


def _detectar_bloqueo(mensaje: str) -> bool:
    texto = (mensaje or "").lower()
    return any(frase in texto for frase in BLOQUEO_FRASES)


def _detectar_progreso(mensaje: str, bloqueo: bool) -> str:
    texto = (mensaje or "").lower().strip()
    if bloqueo:
        return "bloqueado"
    if any(frase in texto for frase in PROGRESO_FRASES):
        return "avance_parcial"
    if len(texto.split()) <= 5 and texto:
        return "respuesta_breve"
    return "sin_evidencia"


def _limitar_texto(texto: str, max_chars: int = 1400) -> str:
    if len(texto) <= max_chars:
        return texto
    return texto[-max_chars:]


def agente_orquestador(state: TutorState, llm) -> TutorState:
    history = state.get("history", [])
    historial_texto = _limitar_texto(formatear_historial(history[-6:]))
    has_code = detectar_codigo(state["student_message"])
    bloqueo = _detectar_bloqueo(state["student_message"])
    progreso_local = _detectar_progreso(state["student_message"], bloqueo)

    prompt = f"""
Eres el Orquestador de una arquitectura multiagente para tutoría socrática en
Algoritmia y Programación (UPAO, primer ciclo).

Analiza el mensaje del estudiante considerando el historial completo y el contexto
emocional. NO respondas al estudiante; solo planifica la activación de agentes.

Temas del curso:
{ALLOWED_TOPICS}

Criterios de activación (en orden de prioridad para el flujo):
1. Motivador primero si hay frustración, bloqueo o desmotivación.
2. Especialista Técnico si el mensaje contiene código, pseudocódigo o lógica concreta.
3. Generador de Ejercicios si hay vacío conceptual persistente (más de 3 intentos
   en el mismo tema sin avance aparente).
4. Siempre al final el Pedagogo Socrático integrará todo y dará la respuesta visible.

Indicador local de código detectado: {has_code}
Indicador local de bloqueo detectado: {bloqueo}
Indicador local de progreso del estudiante: {progreso_local}

Devuelve SOLO JSON válido:
{{
  "topic": "concepto o tema_no_identificado",
  "difficulty_type": "confusion_conceptual|error_logico|pregunta_ambigua|ninguna",
  "emotion": "neutral|frustracion|desmotivacion|ansiedad|bloqueo",
  "bloqueo": true,
  "student_progress": "avance_correcto|avance_parcial|respuesta_breve|bloqueado|sin_evidencia",
  "diagnostic_summary": "resumen breve del estado del estudiante",
  "activate_motivator": true,
  "activate_technical": true,
  "activate_exercise_generator": true,
  "route": "ruta_pedagogica_principal",
  "route_reason": "motivo breve de la planificación"
}}

Historial completo:
{historial_texto}

Mensaje actual del estudiante:
{state["student_message"]}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "topic": "tema_no_identificado",
            "difficulty_type": "pregunta_ambigua",
            "emotion": "bloqueo" if bloqueo else "neutral",
            "bloqueo": bloqueo,
            "student_progress": progreso_local,
            "diagnostic_summary": "El estudiante necesita orientación pedagógica.",
            "activate_motivator": False,
            "activate_technical": has_code,
            "activate_exercise_generator": False,
            "route": "ruta_pedagogica_principal",
            "route_reason": "Análisis por defecto del orquestador.",
        },
    )

    topic = data.get("topic", "tema_no_identificado")
    emotion = data.get("emotion", "neutral").lower()
    bloqueo = bloqueo or bool(data.get("bloqueo")) or emotion == "bloqueo"
    if bloqueo and emotion == "neutral":
        emotion = "bloqueo"
    student_progress = data.get("student_progress", progreso_local)
    if student_progress not in {
        "avance_correcto",
        "avance_parcial",
        "respuesta_breve",
        "bloqueado",
        "sin_evidencia",
    }:
        student_progress = progreso_local
    if bloqueo:
        student_progress = "bloqueado"
    attempt_count = obtener_intentos_tema(topic) + 1

    activate_motivator = (
        bool(data.get("activate_motivator"))
        or emotion in EMOCIONES_FRUSTRACION
    )
    activate_technical = has_code
    activate_exercise_generator = bool(data.get("activate_exercise_generator")) or (
        attempt_count > 3
    )

    route = data.get("route", "ruta_pedagogica_principal")
    route_reason = data.get("route_reason", "Planificación pedagógica estándar.")
    if bloqueo and "bloqueo" not in route_reason.lower():
        route_reason = f"{route_reason} Bloqueo explícito detectado."

    agents_used = ["orquestador"]
    agents_trace = {
        "orquestador": (
            f"Ruta: {route}. {route_reason} | "
            f"Motivador: {'sí' if activate_motivator else 'no'} | "
            f"Técnico: {'sí' if activate_technical else 'no'} | "
            f"Ejercicios: {'sí' if activate_exercise_generator else 'no'} | "
            f"Bloqueo: {'sí' if bloqueo else 'no'} | "
            f"Progreso: {student_progress}"
        ),
        "motivador": "activado" if activate_motivator else "no activado",
        "especialista_tecnico": (
            "activado" if activate_technical else "no activado"
        ),
        "generador_ejercicios": (
            "activado" if activate_exercise_generator else "no activado"
        ),
        "pedagogo_socratico": "pendiente",
    }

    return {
        "topic": topic,
        "difficulty_type": data.get("difficulty_type", "pregunta_ambigua"),
        "emotion": emotion,
        "bloqueo": bloqueo,
        "student_progress": student_progress,
        "attempt_count": attempt_count,
        "has_code": has_code,
        "diagnostic_summary": data.get(
            "diagnostic_summary",
            "El estudiante necesita orientación pedagógica.",
        ),
        "activate_motivator": activate_motivator,
        "activate_technical": activate_technical,
        "activate_exercise_generator": activate_exercise_generator,
        "route": route,
        "route_reason": route_reason,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
