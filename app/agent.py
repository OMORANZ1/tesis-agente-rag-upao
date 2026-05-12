try:
    from .config import PROMPT_PATH
    from .graph import construir_grafo
    from .services.llm_service import crear_llm
    from .services.memory_service import (
        construir_historial_texto,
        registrar_interaccion,
        reiniciar_memoria,
    )
    from .services.rag_service import crear_retriever
    from .state import TutorState
except ImportError:
    from config import PROMPT_PATH
    from graph import construir_grafo
    from services.llm_service import crear_llm
    from services.memory_service import (
        construir_historial_texto,
        registrar_interaccion,
        reiniciar_memoria,
    )
    from services.rag_service import crear_retriever
    from state import TutorState


def crear_agente():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = crear_llm()
    retriever = crear_retriever()
    graph = construir_grafo(llm, retriever, system_prompt)

    def obtener_respuesta(pregunta: str) -> str:
        state: TutorState = {
            "student_message": pregunta,
            "history_text": construir_historial_texto(),
        }
        resultado = graph.invoke(state)
        respuesta = resultado.get(
            "final_response",
            "No pude generar una respuesta. Intenta reformular tu pregunta.",
        )

        registrar_interaccion(pregunta, respuesta)
        return respuesta

    return obtener_respuesta


def reiniciar_historial():
    reiniciar_memoria()
