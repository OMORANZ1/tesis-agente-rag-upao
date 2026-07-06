try:
    from ..state import TutorState
except ImportError:
    from state import TutorState


def agente_fuera_silabo(state: TutorState) -> TutorState:
    respuesta = (
        "Ese tema está fuera del contenido del curso de Algoritmia y Programación "
        "de la UPAO. Solo puedo ayudarte con: variables, operadores, estructuras "
        "secuenciales, condicionales y bucles."
    )
    agents_used = list(state.get("agents_used", []))
    agents_used.append("fuera_silabo")
    agents_trace = dict(state.get("agents_trace", {}))
    agents_trace["fuera_silabo"] = "activado"
    agents_trace["motivador"] = "no activado"
    agents_trace["especialista_tecnico"] = "no activado"
    agents_trace["generador_ejercicios"] = "no activado"
    agents_trace["pedagogo_socratico"] = "no activado"

    debate = list(state.get("agents_debate", []))
    debate.append(
        {
            "agente": "Fuera de Sílabo",
            "modelo": "regla local",
            "accion": "respondió rechazo",
            "aporte": respuesta,
        }
    )

    return {
        "final_response": respuesta,
        "agente_respondedor": "fuera_silabo",
        "route": "fuera_silabo",
        "out_of_syllabus": True,
        "topic": "fuera_silabo",
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_debate": debate,
        "agents_contributions": {"fuera_silabo": respuesta},
        "preguntas_nuevas": [],
    }
