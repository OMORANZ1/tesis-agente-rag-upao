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
        "fuera_silabo": "no activado",
        "pedagogo_socratico": "activo",
    }


DEFAULT_ALLOWED_AGENTS = {
    "orquestador": True,
    "pedagogo": True,
    "tecnico": True,
    "generador": True,
    "motivador": True,
}


AGENT_NAME_MAP = {
    "orquestador": "orquestador",
    "motivador": "motivador",
    "especialista_tecnico": "tecnico",
    "generador_ejercicios": "generador",
    "pedagogo_socratico": "pedagogo",
}


def _normalizar_allowed_agents(allowed_agents: dict | None) -> dict[str, bool]:
    config = dict(DEFAULT_ALLOWED_AGENTS)
    if isinstance(allowed_agents, dict):
        for agent_name in config:
            if agent_name in allowed_agents:
                config[agent_name] = bool(allowed_agents[agent_name])
    config["orquestador"] = True
    return config


def _executed_agents(agents_used: list[str]) -> list[str]:
    executed = []
    for agent_name in agents_used:
        ui_name = AGENT_NAME_MAP.get(agent_name)
        if ui_name and ui_name not in executed:
            executed.append(ui_name)
    return executed


def crear_agente():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = crear_llm()
    retriever = crear_retriever()
    graph = construir_grafo(llm, retriever, system_prompt)

    def obtener_respuesta(pregunta: str, allowed_agents: dict | None = None) -> dict:
        allowed_agents_config = _normalizar_allowed_agents(allowed_agents)
        state: TutorState = {
            "student_message": pregunta,
            "allowed_agents": allowed_agents_config,
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
        return {
            "respuesta": respuesta,
            "agents_trace": agents_trace,
            "executed_agents": _executed_agents(resultado.get("agents_used", [])),
        }

    return obtener_respuesta


def reiniciar_historial():
    reiniciar_memoria()
