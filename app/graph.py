from langgraph.graph import END, StateGraph

try:
    from .agents.diagnostic import agente_diagnosticador
    from .agents.motivational import agente_motivador
    from .agents.orchestrator import agente_orquestador
    from .agents.out_of_syllabus import agente_fuera_silabo
    from .agents.socratic import agente_socratico
    from .state import RouteOption, TutorState
except ImportError:
    from agents.diagnostic import agente_diagnosticador
    from agents.motivational import agente_motivador
    from agents.orchestrator import agente_orquestador
    from agents.out_of_syllabus import agente_fuera_silabo
    from agents.socratic import agente_socratico
    from state import RouteOption, TutorState


def seleccionar_ruta(state: TutorState) -> RouteOption:
    return state.get("route", "diagnosticador")


def construir_grafo(llm, retriever, system_prompt: str):
    workflow = StateGraph(TutorState)

    workflow.add_node("orquestador", lambda state: agente_orquestador(state, llm))
    workflow.add_node("diagnosticador", lambda state: agente_diagnosticador(state, llm))
    workflow.add_node("motivador", lambda state: agente_motivador(state, llm))
    workflow.add_node(
        "socratico",
        lambda state: agente_socratico(state, llm, retriever, system_prompt),
    )
    workflow.add_node("fuera_silabo", agente_fuera_silabo)

    workflow.set_entry_point("orquestador")
    workflow.add_conditional_edges(
        "orquestador",
        seleccionar_ruta,
        {
            "motivador": "motivador",
            "diagnosticador": "diagnosticador",
            "socratico": "socratico",
            "fuera_silabo": "fuera_silabo",
        },
    )
    workflow.add_edge("motivador", "diagnosticador")
    workflow.add_edge("diagnosticador", "socratico")
    workflow.add_edge("socratico", END)
    workflow.add_edge("fuera_silabo", END)

    return workflow.compile()
