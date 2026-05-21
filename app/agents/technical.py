try:
    from ..state import TutorState
    from ..utils import formatear_historial
except ImportError:
    from state import TutorState
    from utils import formatear_historial


def agente_especialista_tecnico(state: TutorState, llm) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))

    if not state.get("activate_technical"):
        agents_trace["especialista_tecnico"] = "no activado"
        return {
            "technical_analysis": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
        }

    historial_texto = formatear_historial(state.get("history", []))
    prompt = f"""
Eres el Agente Especialista Técnico en Algoritmia y Programación (primer ciclo).
Evalúa el código, pseudocódigo o lógica concreta del estudiante.

Analiza SOLO para uso interno del Pedagogo Socrático (NO respondas al estudiante):
1. Correctitud sintáctica y lógica aparente.
2. Eficiencia básica (complejidad O(n) u otra relevante).
3. Selección de estructuras de control (if/else, for, while).

Sé conciso (máximo 8 líneas). No des la solución ni código corregido completo.

Tema: {state.get("topic", "tema_no_identificado")}
Tipo de dificultad: {state.get("difficulty_type", "pregunta_ambigua")}

Historial:
{historial_texto}

Mensaje con código/lógica del estudiante:
{state["student_message"]}

Análisis técnico interno:
"""
    response = llm.invoke(prompt)
    analisis = response.content.strip()
    resumen_corto = analisis.split("\n")[0][:120]

    agents_used.append("especialista_tecnico")
    agents_trace["especialista_tecnico"] = f"activado — {resumen_corto}"

    return {
        "technical_analysis": analisis,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
