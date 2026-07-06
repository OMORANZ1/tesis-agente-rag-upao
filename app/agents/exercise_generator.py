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
    if state.get("modo_aprendizaje") == "tutorial":
        return True
    return "generador" in state.get("agentes_seleccionados", [])


def _limitar_texto(texto: str, max_chars: int = 1200) -> str:
    if len(texto or "") <= max_chars:
        return texto or ""
    return (texto or "")[-max_chars:]


def agente_generador_ejercicios(state: TutorState, retriever) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))
    contributions = dict(state.get("agents_contributions", {}))
    debate = list(state.get("agents_debate", []))

    if not _seleccionado(state):
        agents_trace["generador_ejercicios"] = "no seleccionado"
        return {
            "generated_exercise": {},
            "critic_of_motivator": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": state.get("debate_events", []),
        }

    llm = get_llm_for_agent("generador")
    modelo = AGENT_MODEL_LABELS["generador"]
    debate_events = emitir_inicio(
        state,
        "generador",
        modelo,
        ronda=1,
        mensaje="Diseñando ejercicio práctico personalizado...",
    )
    topic = state.get("topic", "tema_no_identificado")
    attempt_count = state.get("attempt_count", 1)
    nivel = "básico" if attempt_count <= 2 else "intermedio"
    docs = retriever.invoke(f"ejercicios analogías {topic} {state['student_message']}")
    contexto = _limitar_texto("\n\n".join([doc.page_content for doc in docs]))
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-4:]), 900)
    motivational_message = state.get("motivational_message", {})

    if state.get("modo_aprendizaje") == "tutorial":
        technical_analysis = state.get("technical_analysis", {})
        prompt_tutorial = f"""
Eres un tutor didáctico. SIEMPRE estructura tu respuesta en tres partes:
CONCEPTO (explicación directa), EJEMPLO (concreto y simple), VERIFICACIÓN
(una pregunta de comprobación). Nunca mezcles estos elementos.

Reglas:
- El Pedagogo Socrático no participa en este modo.
- CONCEPTO: máximo 2-3 oraciones.
- EJEMPLO: simple, concreto y alineado al sílabo.
- VERIFICACIÓN: exactamente UNA pregunta.
- Corrige el ejemplo si el análisis técnico advierte un riesgo o error.

Contexto del sílabo:
{contexto}

Validación técnica interna:
{technical_analysis}

Tema: {topic}
Historial reciente:
{historial_texto}

Mensaje actual:
{state["student_message"]}

Respuesta final obligatoria:
📖 CONCEPTO: ...

💡 EJEMPLO: ...

✅ VERIFICACIÓN: ...
"""
        respuesta = llm.invoke(prompt_tutorial).content.strip()
        agents_used.append("generador_ejercicios")
        contributions["generador"] = "Respuesta tutorial final con concepto, ejemplo y verificación."
        debate.append(
            {
                "agente": "Generador de Contenido",
                "modelo": AGENT_MODEL_LABELS["generador"],
                "accion": "respondió tutorial",
                "aporte": "Estructuró la respuesta final en CONCEPTO, EJEMPLO y VERIFICACIÓN.",
            }
        )
        agents_trace["generador_ejercicios"] = "respondedor principal — tutorial estructurado"
        debate_events = emitir(
            {**state, "debate_events": debate_events},
            agente=AGENTE_NOMBRES["generador"],
            modelo=modelo,
            ronda=3,
            accion="responde",
            mensaje="Generó respuesta tutorial final con concepto, ejemplo y verificación.",
            estado="final",
        )
        return {
            "final_response": respuesta,
            "generated_exercise": {
                "contexto_real": "",
                "ejercicio": "",
                "pista_inicial": "",
                "nivel": nivel,
            },
            "critic_of_motivator": "",
            "rag_context": contexto,
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": debate_events,
            "ronda_actual": 3,
        }

    prompt = f"""
Eres el Agente de Generación de Contenido y Ejercicios.

Modelo usado: {AGENT_MODEL_LABELS["generador"]}. Es apropiado por su ventana amplia
para crear ejercicios contextualizados y revisar el aporte anterior.

Rol como ejecutor:
- Lee TutorState: topic, attempt_count, diagnostic_summary, mensaje, historial y RAG.
- Escribe TutorState.generated_exercise con contexto_real, ejercicio, pista_inicial y nivel.

Rol como crítico:
- Lee TutorState.motivational_message.
- Escribe TutorState.critic_of_motivator como "apropiado" o
  "sugerencia: [ajuste específico]".

No respondas directamente al estudiante. El Pedagogo integrará tu aporte.
No entregues solución ni código completo.

Contexto del sílabo vía RAG:
{contexto}

Tema: {topic}
Intentos: {attempt_count}
Nivel esperado: {nivel}
Resumen diagnóstico: {state.get("diagnostic_summary", "")}
Apoyo del Motivador:
{motivational_message}

Historial reciente:
{historial_texto}

Mensaje actual:
{state["student_message"]}

Devuelve SOLO JSON válido:
{{
  "generated_exercise": {{
    "contexto_real": "analogía del mundo real relacionada al tema del sílabo",
    "ejercicio": "enunciado del problema práctico sin solución",
    "pista_inicial": "primera pista conceptual sin revelar solución",
    "nivel": "{nivel}"
  }},
  "critic_of_motivator": "apropiado o sugerencia: ajuste específico"
}}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "generated_exercise": {
                "contexto_real": f"Una rutina diaria que requiere aplicar {topic}.",
                "ejercicio": f"Plantea un caso pequeño donde debas reconocer {topic} sin resolverlo completo.",
                "pista_inicial": "Identifica primero la entrada, el proceso y la salida.",
                "nivel": nivel,
            },
            "critic_of_motivator": (
                "apropiado" if motivational_message else "sugerencia: no hubo aporte motivador que evaluar"
            ),
        },
    )
    exercise = data.get("generated_exercise", {})
    if not isinstance(exercise, dict):
        exercise = {
            "contexto_real": f"Situación cotidiana asociada a {topic}.",
            "ejercicio": str(exercise),
            "pista_inicial": "Identifica primero la idea principal.",
            "nivel": nivel,
        }
    critic = data.get("critic_of_motivator", "apropiado")

    agents_used.append("generador_ejercicios")
    contributions["generador"] = (
        f"Ejercicio {exercise.get('nivel', nivel)} sobre {topic}: "
        f"{exercise.get('ejercicio', '')}"
    )
    debate.append(
        {
            "agente": "Generador de Contenido",
            "modelo": AGENT_MODEL_LABELS["generador"],
            "accion": "ejecutó + criticó al Motivador",
            "aporte": (
                f"creó ejercicio {exercise.get('nivel', nivel)} sobre {topic} | "
                f"motivador: {critic}"
            )[:220],
        }
    )
    agents_trace["generador_ejercicios"] = (
        f"activado — ejercicio {exercise.get('nivel', nivel)} | motivador: {critic}"
    )
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["generador"],
        modelo=modelo,
        ronda=1,
        accion="propone",
        mensaje=f"Propuesta: {exercise.get('ejercicio', 'ejercicio contextualizado')}"[:220],
        estado="working",
    )
    if critic and critic != "apropiado":
        debate_events = emitir(
            {**state, "debate_events": debate_events},
            agente=AGENTE_NOMBRES["generador"],
            modelo=modelo,
            ronda=2,
            accion="critica",
            mensaje=critic[:220],
            estado="working",
            critica_a="Motivador",
            veredicto="sugiere",
        )

    return {
        "generated_exercise": exercise,
        "critic_of_motivator": critic,
        "rag_context": contexto,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_contributions": contributions,
        "agents_debate": debate,
        "debate_events": debate_events,
        "ronda_actual": 2 if critic and critic != "apropiado" else 1,
    }
