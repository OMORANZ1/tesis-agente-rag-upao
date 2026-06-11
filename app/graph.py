from langgraph.graph import END, StateGraph

try:
    from .agents.exercise_generator import agente_generador_ejercicios
    from .agents.motivational import agente_motivador
    from .agents.orchestrator import agente_orquestador
    from .agents.quality_evaluator import agente_evaluador_calidad
    from .agents.socratic import agente_pedagogo_socratico
    from .agents.technical import agente_especialista_tecnico
    from .state import TutorState
except ImportError:
    from agents.exercise_generator import agente_generador_ejercicios
    from agents.motivational import agente_motivador
    from agents.orchestrator import agente_orquestador
    from agents.quality_evaluator import agente_evaluador_calidad
    from agents.socratic import agente_pedagogo_socratico
    from agents.technical import agente_especialista_tecnico
    from state import TutorState


def _seleccionado(state: TutorState, agent_name: str) -> bool:
    return agent_name in state.get("agentes_seleccionados", [])


def _despues_orquestador(state: TutorState) -> str:
    if _seleccionado(state, "motivador") and state.get("activate_motivator"):
        return "motivador"
    if _seleccionado(state, "generador") and state.get("activate_exercise_generator"):
        return "generador_ejercicios"
    if _seleccionado(state, "especialista") and state.get("activate_technical"):
        return "especialista_tecnico"
    return "pedagogo_socratico"


def _despues_motivador(state: TutorState) -> str:
    if _seleccionado(state, "generador") and state.get("activate_exercise_generator"):
        return "generador_ejercicios"
    if _seleccionado(state, "especialista") and state.get("activate_technical"):
        return "especialista_tecnico"
    return "pedagogo_socratico"


def _despues_generador(state: TutorState) -> str:
    if _seleccionado(state, "especialista") and state.get("activate_technical"):
        return "especialista_tecnico"
    return "pedagogo_socratico"


def _despues_evaluador(state: TutorState) -> str:
    if state.get("quality_approved"):
        return END
    if state.get("quality_regen_count", 0) >= 2:
        return END
    return "pedagogo_socratico"


def construir_grafo(llm, retriever, system_prompt: str):
    workflow = StateGraph(TutorState)

    workflow.add_node("orquestador", lambda state: agente_orquestador(state, retriever))
    workflow.add_node("motivador", agente_motivador)
    workflow.add_node(
        "generador_ejercicios",
        lambda state: agente_generador_ejercicios(state, retriever),
    )
    workflow.add_node(
        "especialista_tecnico",
        lambda state: agente_especialista_tecnico(state, retriever),
    )
    workflow.add_node(
        "pedagogo_socratico",
        lambda state: agente_pedagogo_socratico(state, retriever, system_prompt),
    )
    workflow.add_node("quality_evaluator", agente_evaluador_calidad)

    workflow.set_entry_point("orquestador")
    workflow.add_conditional_edges(
        "orquestador",
        _despues_orquestador,
        {
            "motivador": "motivador",
            "generador_ejercicios": "generador_ejercicios",
            "especialista_tecnico": "especialista_tecnico",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_conditional_edges(
        "motivador",
        _despues_motivador,
        {
            "generador_ejercicios": "generador_ejercicios",
            "especialista_tecnico": "especialista_tecnico",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_conditional_edges(
        "generador_ejercicios",
        _despues_generador,
        {
            "especialista_tecnico": "especialista_tecnico",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_edge("especialista_tecnico", "pedagogo_socratico")
    workflow.add_edge("pedagogo_socratico", "quality_evaluator")
    workflow.add_conditional_edges(
        "quality_evaluator",
        _despues_evaluador,
        {
            END: END,
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )

    return workflow.compile()
