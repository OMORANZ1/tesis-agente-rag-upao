try:
    from ..config import ALLOWED_TOPICS
    from ..state import TutorState
    from ..utils import extraer_json
except ImportError:
    from config import ALLOWED_TOPICS
    from state import TutorState
    from utils import extraer_json


def agente_diagnosticador(state: TutorState, llm) -> TutorState:
    prompt = f"""
Eres el Agente Diagnosticador del tutor de Algoritmia y Programacion.
Tu tarea es identificar el concepto que el estudiante no entiende y el tipo
de dificultad, sin resolver ejercicios ni entregar codigo.

Temas permitidos:
{ALLOWED_TOPICS}

Devuelve solo JSON valido:
{{
  "topic": "concepto especifico",
  "difficulty_type": "confusion_conceptual|error_logico|pregunta_ambigua",
  "diagnostic_summary": "resumen breve del problema del estudiante"
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
            "topic": state.get("topic", "tema_no_identificado"),
            "difficulty_type": state.get("difficulty_type", "pregunta_ambigua"),
            "diagnostic_summary": "El estudiante necesita precisar mejor su duda.",
        },
    )
    return {
        "topic": data.get("topic", state.get("topic", "tema_no_identificado")),
        "difficulty_type": data.get(
            "difficulty_type",
            state.get("difficulty_type", "pregunta_ambigua"),
        ),
        "diagnostic_summary": data.get(
            "diagnostic_summary",
            "El estudiante necesita precisar mejor su duda.",
        ),
    }
