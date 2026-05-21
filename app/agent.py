try:
    from .config import PROMPT_PATH
    from .graph import construir_grafo
    from .services.llm_service import crear_llm
    from .services.memory_service import (
        obtener_historial,
        obtener_preguntas_hechas,
        registrar_interaccion,
        registrar_preguntas,
        reiniciar_memoria,
    )
    from .services.rag_service import crear_retriever
    from .state import TutorState
except ImportError:
    from config import PROMPT_PATH
    from graph import construir_grafo
    from services.llm_service import crear_llm
    from services.memory_service import (
        obtener_historial,
        obtener_preguntas_hechas,
        registrar_interaccion,
        registrar_preguntas,
        reiniciar_memoria,
    )
    from services.rag_service import crear_retriever
    from state import TutorState


def _trace_por_defecto() -> dict[str, str]:
    return {
        "orquestador": "sin datos",
        "motivador": "no activado",
        "especialista_tecnico": "no activado",
        "generador_ejercicios": "no activado",
        "pedagogo_socratico": "activo",
    }


def crear_agente():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = crear_llm()
    retriever = crear_retriever()
    graph = construir_grafo(llm, retriever, system_prompt)

    def obtener_respuesta(pregunta: str) -> dict:
        state: TutorState = {
            "student_message": pregunta,
            "history": obtener_historial(),
            "preguntas_hechas": obtener_preguntas_hechas(),
            "agents_used": [],
            "agents_trace": _trace_por_defecto(),
        }
        resultado = graph.invoke(state)
        respuesta = resultado.get(
            "final_response",
            "No pude generar una respuesta. Intenta reformular tu pregunta.",
        )
        agents_trace = resultado.get("agents_trace", _trace_por_defecto())
        if agents_trace.get("pedagogo_socratico") == "pendiente":
            agents_trace["pedagogo_socratico"] = (
                f"activo — {resultado.get('socratic_response_type', 'respuesta socrática')}"
            )

        registrar_interaccion(pregunta, respuesta)
        registrar_preguntas(resultado.get("preguntas_nuevas", []))
        return {"respuesta": respuesta, "agents_trace": agents_trace}

    return obtener_respuesta


def reiniciar_historial():
    reiniciar_memoria()
