from queue import Queue

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
    from .services.progress_service import actualizar_progreso, obtener_progreso
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
    from services.progress_service import actualizar_progreso, obtener_progreso
    from services.rag_service import crear_retriever
    from state import TutorState


def _trace_por_defecto() -> dict[str, str]:
    return {
        "orquestador": "sin datos",
        "motivador": "no activado",
        "especialista_tecnico": "no activado",
        "generador_ejercicios": "no activado",
        "evaluador_calidad": "pendiente",
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

MODE_DEFAULT_AGENTS = {
    "socratico": {
        "orquestador": True,
        "pedagogo": True,
        "tecnico": True,
        "generador": False,
        "motivador": False,
    },
    "tutorial": {
        "orquestador": True,
        "pedagogo": True,
        "tecnico": True,
        "generador": True,
        "motivador": False,
    },
    "reto": {
        "orquestador": True,
        "pedagogo": True,
        "tecnico": True,
        "generador": False,
        "motivador": False,
    },
}

AGENT_NAME_MAP = {
    "orquestador": "orquestador",
    "motivador": "motivador",
    "especialista_tecnico": "tecnico",
    "generador_ejercicios": "generador",
    "pedagogo_socratico": "pedagogo",
    "evaluador_calidad": "evaluador",
}


def _normalizar_modo(modo: str | None) -> str:
    modo = (modo or "socratico").strip().lower()
    if modo not in MODE_DEFAULT_AGENTS:
        return "socratico"
    return modo


def _normalizar_allowed_agents(
    allowed_agents: dict | None,
    modo: str,
) -> dict[str, bool]:
    config = dict(MODE_DEFAULT_AGENTS.get(modo, MODE_DEFAULT_AGENTS["socratico"]))
    if isinstance(allowed_agents, dict) and allowed_agents:
        for agent_name in config:
            if agent_name in allowed_agents:
                config[agent_name] = bool(allowed_agents[agent_name])
    config["orquestador"] = True
    config["pedagogo"] = True
    return config


def _agentes_seleccionados(allowed_agents: dict[str, bool]) -> list[str]:
    selected = []
    if allowed_agents.get("motivador", False):
        selected.append("motivador")
    if allowed_agents.get("generador", False):
        selected.append("generador")
    if allowed_agents.get("tecnico", False):
        selected.append("especialista")
    selected.append("pedagogo")
    return selected


def _executed_agents(agents_used: list[str]) -> list[str]:
    executed = []
    for agent_name in agents_used:
        ui_name = AGENT_NAME_MAP.get(agent_name)
        if ui_name and ui_name not in executed:
            executed.append(ui_name)
    return executed


def _construir_state_inicial(
    pregunta: str,
    allowed_agents: dict | None,
    modo: str | None,
    event_queue: Queue | None = None,
) -> TutorState:
    modo_norm = _normalizar_modo(modo)
    allowed_agents_config = _normalizar_allowed_agents(allowed_agents, modo_norm)
    state: TutorState = {
        "student_message": pregunta,
        "modo_aprendizaje": modo_norm,
        "allowed_agents": allowed_agents_config,
        "agentes_seleccionados": _agentes_seleccionados(allowed_agents_config),
        "history": obtener_historial(),
        "preguntas_hechas": obtener_preguntas_hechas(),
        "agents_used": [],
        "agents_trace": _trace_por_defecto(),
        "agents_contributions": {},
        "agents_debate": [],
        "debate_events": [],
        "topic_progress": obtener_progreso(),
        "quality_feedback": "",
        "quality_approved": False,
        "quality_regen_count": 0,
        "ronda_actual": 1,
    }
    if event_queue is not None:
        state["event_queue"] = event_queue
    return state


def _formatear_resultado(resultado: dict, pregunta: str) -> dict:
    respuesta = resultado.get(
        "final_response",
        "No pude generar una respuesta. Intenta reformular tu pregunta.",
    )
    agents_trace = resultado.get("agents_trace", _trace_por_defecto())
    if agents_trace.get("pedagogo_socratico") == "pendiente":
        agents_trace["pedagogo_socratico"] = (
            f"activo — {resultado.get('socratic_response_type', 'respuesta socrática')}"
        )

    topic_progress = actualizar_progreso(
        resultado.get("topic", "tema_no_identificado"),
        interaccion=True,
        respuesta_correcta=bool(resultado.get("student_answer_correct")),
        attempt_count=resultado.get("attempt_count"),
        student_progress=resultado.get("student_progress", ""),
    )

    registrar_interaccion(pregunta, respuesta)
    registrar_preguntas(resultado.get("preguntas_nuevas", []))

    return {
        "respuesta": respuesta,
        "agents_trace": agents_trace,
        "executed_agents": _executed_agents(resultado.get("agents_used", [])),
        "agents_debate": resultado.get("agents_debate", []),
        "agents_contributions": resultado.get("agents_contributions", {}),
        "orchestrator_decision": resultado.get("orchestrator_decision", {}),
        "debate_events": resultado.get("debate_events", []),
        "topic_progress": topic_progress,
        "modo_aprendizaje": resultado.get("modo_aprendizaje", "socratico"),
    }


def crear_agente():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = crear_llm()
    retriever = crear_retriever()
    graph = construir_grafo(llm, retriever, system_prompt)

    def obtener_respuesta(
        pregunta: str,
        allowed_agents: dict | None = None,
        modo: str | None = "socratico",
        event_queue: Queue | None = None,
    ) -> dict:
        state = _construir_state_inicial(pregunta, allowed_agents, modo, event_queue)
        resultado = graph.invoke(state)
        salida = _formatear_resultado(resultado, pregunta)

        if event_queue is not None:
            event_queue.put(
                {
                    "tipo": "respuesta_final",
                    "respuesta": salida["respuesta"],
                    "agents_trace": salida["agents_trace"],
                    "executed_agents": salida["executed_agents"],
                    "agents_debate": salida["agents_debate"],
                    "orchestrator_decision": salida["orchestrator_decision"],
                    "topic_progress": salida["topic_progress"],
                    "debate_events": salida["debate_events"],
                    "estado": "done",
                }
            )

        return salida

    return obtener_respuesta


def reiniciar_historial():
    reiniciar_memoria()
    try:
        from .services.progress_service import reiniciar_progreso
    except ImportError:
        from services.progress_service import reiniciar_progreso
    reiniciar_progreso()
