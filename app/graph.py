from langgraph.graph import END, StateGraph

try:
    from .agents.exercise_generator import agente_generador_ejercicios
    from .agents.motivational import agente_motivador
    from .agents.orchestrator import agente_orquestador
    from .agents.socratic import agente_pedagogo_socratico
    from .agents.technical import agente_especialista_tecnico
    from .state import TutorState
except ImportError:
    from agents.exercise_generator import agente_generador_ejercicios
    from agents.motivational import agente_motivador
    from agents.orchestrator import agente_orquestador
    from agents.socratic import agente_pedagogo_socratico
    from agents.technical import agente_especialista_tecnico
    from state import TutorState


def _siguiente_agente(state: TutorState) -> str:
    if state.get("activate_motivator") and "motivador" not in state.get(
        "agents_used", []
    ):
        return "motivador"
    if state.get("activate_technical") and "especialista_tecnico" not in state.get(
        "agents_used", []
    ):
        return "especialista_tecnico"
    exercise_pending = "generador_ejercicios" not in state.get("agents_used", [])
    if state.get("activate_exercise_generator") and exercise_pending:
        return "generador_ejercicios"
    return "pedagogo_socratico"


def construir_grafo(llm, retriever, system_prompt: str):
    workflow = StateGraph(TutorState)

    workflow.add_node("orquestador", lambda state: agente_orquestador(state, llm))
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
            "motivador": "motivador",
            "especialista_tecnico": "especialista_tecnico",
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_conditional_edges(
        "motivador",
        _siguiente_agente,
        {
            "especialista_tecnico": "especialista_tecnico",
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_conditional_edges(
        "especialista_tecnico",
        _siguiente_agente,
        {
            "generador_ejercicios": "generador_ejercicios",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )
    workflow.add_edge("generador_ejercicios", "pedagogo_socratico")
    workflow.add_edge("pedagogo_socratico", END)

    return workflow.compile()
