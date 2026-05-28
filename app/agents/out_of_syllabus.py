try:
    from ..state import TutorState
except ImportError:
    from state import TutorState


def agente_fuera_silabo(state: TutorState) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_used.append("fuera_silabo")
    agents_trace = dict(state.get("agents_trace", {}))
    agents_trace["fuera_silabo"] = "activado"
    agents_trace["motivador"] = "no activado"
    agents_trace["especialista_tecnico"] = "no activado"
    agents_trace["generador_ejercicios"] = "no activado"
    agents_trace["pedagogo_socratico"] = "no activado"

    return {
        "final_response": (
            "Ese tema está fuera del sílabo y del curso de Algoritmia y "
            "Programación."
        ),
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
