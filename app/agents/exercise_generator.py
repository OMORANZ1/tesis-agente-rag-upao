try:
    from ..state import TutorState
    from ..utils import formatear_historial
except ImportError:
    from state import TutorState
    from utils import formatear_historial


def agente_generador_ejercicios(state: TutorState, llm, retriever) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))

    if not state.get("activate_exercise_generator"):
        agents_trace["generador_ejercicios"] = "no activado"
        return {
            "generated_exercise": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
        }

    consulta_rag = (
        f"ejercicios prácticos {state.get('topic', '')} "
        f"{state['student_message']}"
    )
    docs = retriever.invoke(consulta_rag)
    contexto = "\n\n".join([d.page_content for d in docs])
    historial_texto = formatear_historial(state.get("history", []))

    prompt = f"""
Eres el Agente de Generación de Contenido y Ejercicios.
El estudiante lleva {state.get("attempt_count", 0)} intentos en el tema
"{state.get("topic", "tema_no_identificado")}" sin avance suficiente.

Genera UN ejercicio práctico personalizado para el Pedagogo Socrático (no respondas
directamente al estudiante). Incluye:
- Enunciado claro y breve.
- Un reto modular (paso a paso).
- Una analogía del mundo real relacionada con el sílabo.

No entregues la solución. Adapta al primer ciclo universitario.

Contexto del sílabo (RAG):
{contexto}

Historial:
{historial_texto}

Resumen diagnóstico:
{state.get("diagnostic_summary", "")}

Mensaje del estudiante:
{state["student_message"]}

Ejercicio generado (solo para el pedagogo):
"""
    response = llm.invoke(prompt)
    agents_used.append("generador_ejercicios")
    agents_trace["generador_ejercicios"] = "activado"

    return {
        "generated_exercise": response.content.strip(),
        "rag_context": contexto,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
