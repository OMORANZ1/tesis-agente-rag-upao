from langgraph.graph import END, StateGraph

try:
    from .agents.exercise_generator import agente_generador_ejercicios
    from .agents.motivational import agente_motivador
    from .agents.orchestrator import agente_orquestador
    from .agents.out_of_syllabus import agente_fuera_silabo
    from .agents.quality_evaluator import agente_evaluador_calidad
    from .agents.socratic import agente_pedagogo_socratico
    from .agents.technical import agente_especialista_tecnico
    from .state import TutorState
except ImportError:
    from agents.exercise_generator import agente_generador_ejercicios
    from agents.motivational import agente_motivador
    from agents.orchestrator import agente_orquestador
    from agents.out_of_syllabus import agente_fuera_silabo
    from agents.quality_evaluator import agente_evaluador_calidad
    from agents.socratic import agente_pedagogo_socratico
    from agents.technical import agente_especialista_tecnico
    from state import TutorState


def decidir_flujo(state: TutorState) -> str:
    if state.get("route") == "fuera_silabo" or state.get("out_of_syllabus"):
        return "fuera_silabo"
    if state.get("modo_aprendizaje") == "tutorial":
        return "tutorial"
    if state.get("modo_aprendizaje") == "reto":
        return "reto"
    return "socratico"


def _inicio_socratico(state: TutorState) -> str:
    if state.get("has_code") and state.get("activate_technical"):
        return "especialista_tecnico_socratico"
    return "pedagogo_socratico"


def _despues_especialista_reto(state: TutorState) -> str:
    if state.get("attempt_count", 0) > 2:
        return "pedagogo_reto"
    return "quality_evaluator"


def _despues_evaluador(state: TutorState) -> str:
    if state.get("quality_approved"):
        return END
    if state.get("quality_regen_count", 0) >= 2:
        return END
    respondedor = state.get("agente_respondedor", "pedagogo")
    if respondedor == "generador":
        return "generador_ejercicios"
    if respondedor == "especialista":
        return "especialista_tecnico"
    return "pedagogo_socratico"


def construir_grafo(llm, retriever, system_prompt: str):
    workflow = StateGraph(TutorState)

    workflow.add_node("orquestador", lambda state: agente_orquestador(state, retriever))
    workflow.add_node("fuera_silabo", agente_fuera_silabo)
    workflow.add_node("motivador", agente_motivador)
    workflow.add_node("inicio_socratico", lambda state: state)
    workflow.add_node("especialista_tecnico_reto", lambda state: state)
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
        decidir_flujo,
        {
            "fuera_silabo": "fuera_silabo",
            "socratico": "inicio_socratico",
            "tutorial": "especialista_tecnico",
            "reto": "especialista_tecnico",
        },
    )
    workflow.add_edge("fuera_silabo", END)

    workflow.add_conditional_edges(
        "inicio_socratico",
        _inicio_socratico,
        {
            "especialista_tecnico_socratico": "especialista_tecnico",
            "pedagogo_socratico": "pedagogo_socratico",
        },
    )

    workflow.add_conditional_edges(
        "especialista_tecnico",
        lambda state: state.get("modo_aprendizaje", "socratico"),
        {
            "socratico": "pedagogo_socratico",
            "tutorial": "generador_ejercicios",
            "reto": "especialista_tecnico_reto",
        },
    )
    workflow.add_conditional_edges(
        "especialista_tecnico_reto",
        _despues_especialista_reto,
        {
            "pedagogo_reto": "pedagogo_socratico",
            "quality_evaluator": "quality_evaluator",
        },
    )
    workflow.add_edge("generador_ejercicios", "quality_evaluator")
    workflow.add_edge("pedagogo_socratico", "quality_evaluator")
    workflow.add_conditional_edges(
        "quality_evaluator",
        _despues_evaluador,
        {
            END: END,
            "pedagogo_socratico": "pedagogo_socratico",
            "generador_ejercicios": "generador_ejercicios",
            "especialista_tecnico": "especialista_tecnico",
        },
    )

    return workflow.compile()
