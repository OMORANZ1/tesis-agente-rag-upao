try:
    from ..config import ALLOWED_TOPICS
    from ..state import TutorState
    from ..utils import extraer_json
except ImportError:
    from config import ALLOWED_TOPICS
    from state import TutorState
    from utils import extraer_json


def agente_orquestador(state: TutorState, llm) -> TutorState:
    prompt = f"""
Eres el Orquestador de una arquitectura multiagente para un tutor socratico.
Analiza el mensaje del estudiante y decide la siguiente ruta.

Temas permitidos del curso:
{ALLOWED_TOPICS}

Criterios de ruta:
- "motivador": si detectas frustracion, ansiedad, bloqueo o desmotivacion.
- "diagnosticador": si el tema o la dificultad no estan claros.
- "socratico": si el tema esta claro y pertenece al curso.
- "fuera_silabo": si la pregunta no pertenece al curso.

Devuelve solo JSON valido con estas claves:
{{
  "route": "motivador|diagnosticador|socratico|fuera_silabo",
  "topic": "tema probable o tema_no_identificado",
  "difficulty_type": "confusion_conceptual|error_logico|pregunta_ambigua|ninguna",
  "emotion": "neutral|frustracion|desmotivacion|ansiedad"
}}

Historial:
{state.get("history_text", "")}

Mensaje del estudiante:
{state["student_message"]}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "route": "diagnosticador",
            "topic": "tema_no_identificado",
            "difficulty_type": "pregunta_ambigua",
            "emotion": "neutral",
        },
    )
    route = data.get("route", "diagnosticador")
    if route not in ("motivador", "diagnosticador", "socratico", "fuera_silabo"):
        route = "diagnosticador"

    return {
        "route": route,
        "topic": data.get("topic", "tema_no_identificado"),
        "difficulty_type": data.get("difficulty_type", "pregunta_ambigua"),
        "emotion": data.get("emotion", "neutral"),
    }
