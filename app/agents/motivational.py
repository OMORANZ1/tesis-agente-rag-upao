try:
    from ..services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from ..services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from ..state import TutorState
    from ..utils import extraer_json, formatear_historial
except ImportError:
    from services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from state import TutorState
    from utils import extraer_json, formatear_historial


def _seleccionado(state: TutorState) -> bool:
    return "motivador" in state.get("agentes_seleccionados", [])


def _limitar_texto(texto: str, max_chars: int = 900) -> str:
    if len(texto or "") <= max_chars:
        return texto or ""
    return (texto or "")[-max_chars:]


def agente_motivador(state: TutorState) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))
    contributions = dict(state.get("agents_contributions", {}))
    debate = list(state.get("agents_debate", []))

    if not _seleccionado(state):
        agents_trace["motivador"] = "no seleccionado"
        return {
            "motivational_message": {},
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": state.get("debate_events", []),
        }

    if not state.get("activate_motivator"):
        agents_trace["motivador"] = "no activado: no se detectó emoción afectiva"
        return {
            "motivational_message": {},
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": state.get("debate_events", []),
        }

    llm = get_llm_for_agent("motivador")
    modelo = AGENT_MODEL_LABELS["motivador"]
    debate_events = emitir_inicio(
        state,
        "motivador",
        modelo,
        ronda=1,
        mensaje="Generando apoyo emocional contextualizado...",
    )
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-4:]))
    topic = state.get("topic", "tema_no_identificado")
    rag_context = _limitar_texto(state.get("rag_context", ""), 700)

    prompt = f"""
Eres el Agente Motivador y de Apoyo Afectivo.

Modelo usado: {AGENT_MODEL_LABELS["motivador"]}. Es apropiado porque genera
mensajes afectivos más ricos y específicos.

Rol como ejecutor:
- Lee TutorState: topic, emotion, bloqueo, diagnostic_summary, historial y mensaje.
- Escribe TutorState.motivational_message con JSON estructurado.
- No criticas a otro agente porque eres el primer agente colaborativo.
- NO respondas directamente al estudiante; tu salida la integrará el Pedagogo.

El apoyo debe ser específico al tema "{topic}", no genérico.
Usa este contexto RAG del sílabo como anclaje académico breve:
{rag_context or "Sin contexto RAG disponible."}

Devuelve SOLO JSON válido:
{{
  "frase_apoyo": "frase breve, humana y específica al tema",
  "reencuadre": "cómo ver el error como aprendizaje, mencionando el tema específico"
}}

Emoción detectada: {state.get("emotion", "neutral")}
Bloqueo explícito: {state.get("bloqueo", False)}
Diagnóstico: {state.get("diagnostic_summary", "")}

Historial reciente:
{historial_texto}

Mensaje del estudiante:
{state["student_message"]}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "frase_apoyo": f"Vamos paso a paso con {topic}; la confusión es parte del proceso.",
            "reencuadre": f"Cada intento ayuda a distinguir mejor la idea central de {topic}.",
        },
    )

    agents_used.append("motivador")
    contributions["motivador"] = (
        f"Apoyo afectivo sobre {topic}: {data.get('frase_apoyo', '')}"
    )
    debate.append(
        {
            "agente": "Motivador",
            "modelo": AGENT_MODEL_LABELS["motivador"],
            "accion": "ejecutó",
            "aporte": (
                f"frase de apoyo sobre {topic}: {data.get('frase_apoyo', '')}"
            )[:220],
        }
    )
    agents_trace["motivador"] = "activado — apoyo afectivo específico"
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["motivador"],
        modelo=modelo,
        ronda=1,
        accion="ejecutó",
        mensaje=f"Apoyo emocional sobre {topic}: {data.get('frase_apoyo', '')}"[:220],
        estado="working",
    )

    return {
        "motivational_message": data,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_contributions": contributions,
        "agents_debate": debate,
        "debate_events": debate_events,
        "ronda_actual": 1,
    }
