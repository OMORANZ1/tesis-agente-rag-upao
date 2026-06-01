from langgraph.graph import END, StateGraph

try:
    from .agents.exercise_generator import agente_generador_ejercicios
    from .agents.motivational import agente_motivador
    from .agents.orchestrator import agente_orquestador
    from .agents.out_of_syllabus import agente_fuera_silabo
    from .agents.socratic import agente_pedagogo_socratico
    from .agents.technical import agente_especialista_tecnico
    from .state import TutorState
except ImportError:
    from agents.exercise_generator import agente_generador_ejercicios
    from agents.motivational import agente_motivador
    from agents.orchestrator import agente_orquestador
    from agents.out_of_syllabus import agente_fuera_silabo
    from agents.socratic import agente_pedagogo_socratico
    from agents.technical import agente_especialista_tecnico
    from state import TutorState


def _agent_allowed(state: TutorState, agent_name: str) -> bool:
    allowed_agents = state.get("allowed_agents", {})
    return bool(allowed_agents.get(agent_name, True))


def _siguiente_agente(state: TutorState) -> str:
    if state.get("out_of_syllabus") or state.get("route") == "fuera_silabo":
        return "fuera_silabo"
    if (
        _agent_allowed(state, "motivador")
        and state.get("activate_motivator")
        and "motivador" not in state.get(
        "agents_used", []
        )
    ):
        return "motivador"
    if (
        _agent_allowed(state, "tecnico")
        and state.get("activate_technical")
        and "especialista_tecnico" not in state.get("agents_used", [])
    ):
        return "especialista_tecnico"
    exercise_pending = "generador_ejercicios" not in state.get("agents_used", [])
    if (
        _agent_allowed(state, "generador")
        and state.get("activate_exercise_generator")
        and exercise_pending
    ):
        return "generador_ejercicios"
    if not _agent_allowed(state, "pedagogo"):
        return "respuesta_configuracion"
    return "pedagogo_socratico"


def respuesta_configuracion(state: TutorState) -> TutorState:
    agents_trace = dict(state.get("agents_trace", {}))
    agents_trace["pedagogo_socratico"] = "desactivado por el usuario"
    if state.get("generated_exercise"):
        return {
            "final_response": state["generated_exercise"],
            "agents_trace": agents_trace,
            "agents_used": list(state.get("agents_used", [])),
        }

    return {
        "final_response": (
            "El Pedagogo Socrático está desactivado. Para continuar, activa el "
            "Pedagogo Socrático o el Generador de Contenido si deseas recibir un "
            "ejemplo conceptual."
        ),
        "agents_trace": agents_trace,
        "agents_used": list(state.get("agents_used", [])),
    }


def construir_grafo(llm, retriever, system_prompt: str):
    workflow = StateGraph(TutorState)

    workflow.add_node("orquestador", lambda state: agente_orquestador(state, llm))
    workflow.add_node("respuesta_configuracion", respuesta_configuracion)
    workflow.add_node("fuera_silabo", agente_fuera_silabo)
    workflow.add_node("motivador", lambda state: agente_motivador(state, llm))
    workflow.add_node(
        "especialista_tecnico",
        lambda state: agente_especialista_tecnico(state, llm),
    )
    workflow.add_node(
        "generador_ejercicios",
        lambda state: agente_generador_ejercicios(state, llm, retriever),
    )
    workflow.add_node(
        "pedagogo_socratico",
        lambda state: agente_pedagogo_socratico(
            state, llm, retriever, system_prompt
        ),
    )

    workflow.set_entry_point("orquestador")
    workflow.add_conditional_edges(
        "orquestador",
        _siguiente_agente,
        {
            "fuera_silabo": "fuera_silabo",
            "motivador": "motivador",
            "especialista_tecnico": "especialista_tecnico",
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
            "respuesta_configuracion": "respuesta_configuracion",
        },
    )
    workflow.add_conditional_edges(
        "motivador",
        _siguiente_agente,
        {
            "especialista_tecnico": "especialista_tecnico",
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
            "respuesta_configuracion": "respuesta_configuracion",
        },
    )
    workflow.add_conditional_edges(
        "especialista_tecnico",
        _siguiente_agente,
        {
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
            "respuesta_configuracion": "respuesta_configuracion",
        },
    )
    workflow.add_conditional_edges(
        "generador_ejercicios",
        _siguiente_agente,
        {
            "pedagogo_socratico": "pedagogo_socratico",
            "respuesta_configuracion": "respuesta_configuracion",
        },
    )
    workflow.add_edge("pedagogo_socratico", END)
    workflow.add_edge("fuera_silabo", END)
    workflow.add_edge("respuesta_configuracion", END)

    return workflow.compile()
