try:
    from ..state import TutorState
except ImportError:
    from state import TutorState


def agente_fuera_silabo(state: TutorState) -> TutorState:
    return {
        "final_response": (
            "Esa pregunta esta fuera del contenido del curso de "
            "Algoritmia y Programacion."
        )
    }
