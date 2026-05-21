try:
    from ..state import TutorState
    from ..utils import formatear_historial
except ImportError:
    from state import TutorState
    from utils import formatear_historial


def agente_motivador(state: TutorState, llm) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))

    if not state.get("activate_motivator"):
        agents_trace["motivador"] = "no activado"
        return {
            "motivational_message": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
        }

    historial_texto = formatear_historial(state.get("history", []))
    prompt = f"""
Eres el Agente Motivador y de Apoyo Afectivo de un tutor universitario.
El estudiante muestra señales de: {state.get("emotion", "bloqueo")}.

Genera UN mensaje breve (2-3 oraciones) de apoyo empático y motivación realista.
No expliques contenido académico ni des soluciones. No uses exageraciones.

Historial:
{historial_texto}

Mensaje del estudiante:
{state["student_message"]}
"""
    response = llm.invoke(prompt)
    agents_used.append("motivador")
    agents_trace["motivador"] = "activado"

    return {
        "motivational_message": response.content.strip(),
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
