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
    if state.get("modo_aprendizaje") in {"tutorial", "reto"}:
        return True
    return "especialista" in state.get("agentes_seleccionados", [])


def _limitar_texto(texto: str, max_chars: int = 1200) -> str:
    if len(texto or "") <= max_chars:
        return texto or ""
    return (texto or "")[-max_chars:]


def agente_especialista_tecnico(state: TutorState, retriever) -> TutorState:
    agents_used = list(state.get("agents_used", []))
    agents_trace = dict(state.get("agents_trace", {}))
    contributions = dict(state.get("agents_contributions", {}))
    debate = list(state.get("agents_debate", []))

    if not _seleccionado(state):
        agents_trace["especialista_tecnico"] = "no seleccionado"
        return {
            "technical_analysis": {},
            "critic_of_exercise": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": state.get("debate_events", []),
        }

    llm = get_llm_for_agent("especialista")
    modelo = AGENT_MODEL_LABELS["especialista"]
    debate_events = emitir_inicio(
        state,
        "especialista",
        modelo,
        ronda=1,
        mensaje="Analizando lógica, conceptos y ejercicio propuesto...",
    )
    topic = state.get("topic", "tema_no_identificado")
    docs = retriever.invoke(f"precisión técnica {topic} {state['student_message']}")
    contexto = _limitar_texto("\n\n".join([doc.page_content for doc in docs]))
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-4:]), 900)
    generated_exercise = state.get("generated_exercise", {})

    if state.get("modo_aprendizaje") == "reto":
        attempt_count = state.get("attempt_count", 1)
        prompt_reto = f"""
Eres un evaluador técnico. Presenta retos prácticos directos y evalúa las
soluciones del estudiante con feedback técnico preciso. No expliques antes del
reto. Solo da pistas si el estudiante lleva más de 2 intentos fallidos.

Contexto del sílabo:
{contexto}

Tema: {topic}
Intento actual: {attempt_count}
Historial reciente:
{historial_texto}

Mensaje actual:
{state["student_message"]}

Reglas de salida:
- Si es el primer mensaje sobre el tema o el estudiante pide aprender, responde:
  "🎯 RETO: [enunciado del problema práctico]
  Criterios: [qué debe cumplir la solución]
  Pista inicial: [pista conceptual mínima]"
- Si el estudiante entrega una solución, responde:
  "[✓ Correcto / ✗ Incorrecto]: [feedback técnico directo]
  [Si incorrecto]: Revisa [aspecto específico]. Intenta de nuevo."
- No expliques el concepto antes del reto.

Respuesta final:
"""
        respuesta = llm.invoke(prompt_reto).content.strip()
        analysis = {
            "concepto_clave": topic,
            "precision_requerida": "Modo reto: el estudiante debe resolver un problema práctico.",
            "error_comun": "Esperar explicación previa en lugar de intentar la solución.",
            "pregunta_tecnica_sugerida": "",
        }
        agents_used.append("especialista_tecnico")
        contributions["especialista"] = "Respondió como evaluador técnico principal del modo reto."
        debate.append(
            {
                "agente": "Especialista Técnico",
                "modelo": AGENT_MODEL_LABELS["especialista"],
                "accion": "respondió reto",
                "aporte": respuesta[:220],
            }
        )
        agents_trace["especialista_tecnico"] = "respondedor principal — reto técnico"
        debate_events = emitir(
            {**state, "debate_events": debate_events},
            agente=AGENTE_NOMBRES["especialista"],
            modelo=modelo,
            ronda=3,
            accion="responde",
            mensaje="Generó o evaluó el reto técnico del turno.",
            estado="final",
        )
        return {
            "final_response": respuesta,
            "technical_analysis": analysis,
            "critic_of_exercise": "",
            "corrected_exercise": {},
            "rag_context": contexto,
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": debate_events,
            "ronda_actual": 3,
        }

    prompt = f"""
Eres el Agente Especialista Técnico en Algoritmia y Programación.

Modelo usado: {AGENT_MODEL_LABELS["especialista"]}. Es apropiado por su precisión
técnica y velocidad para revisar conceptos, ejercicios y lógica.

Rol como ejecutor:
- Lee TutorState: topic, student_message, has_code, diagnostic_summary, RAG e historial.
- Escribe TutorState.technical_analysis con concepto_clave, precision_requerida,
  error_comun y pregunta_tecnica_sugerida.

Rol como crítico:
- Lee TutorState.generated_exercise.
- Escribe TutorState.critic_of_exercise como "correcto" o
  "corrección técnica: [ajuste necesario]".
- Si corriges, escribe corrected_exercise con una versión técnica corregida.

No respondas directamente al estudiante.
No entregues código completo ni solución directa.

Contexto del sílabo vía RAG:
{contexto}

Tema: {topic}
Contiene código o lógica concreta: {state.get("has_code", False)}
Dificultad: {state.get("difficulty_type", "pregunta_ambigua")}
Diagnóstico: {state.get("diagnostic_summary", "")}

Ejercicio del Generador:
{generated_exercise}

Historial reciente:
{historial_texto}

Mensaje actual:
{state["student_message"]}

Devuelve SOLO JSON válido:
{{
  "technical_analysis": {{
    "concepto_clave": "concepto técnico central de la consulta",
    "precision_requerida": "explicación técnica correcta y completa",
    "error_comun": "error conceptual frecuente relacionado",
    "pregunta_tecnica_sugerida": "pregunta específica que el Pedagogo puede usar"
  }},
  "critic_of_exercise": "correcto o corrección técnica: ajuste necesario",
  "corrected_exercise": {{
    "contexto_real": "solo si hay corrección",
    "ejercicio": "solo si hay corrección",
    "pista_inicial": "solo si hay corrección",
    "nivel": "básico|intermedio"
  }}
}}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "technical_analysis": {
                "concepto_clave": topic,
                "precision_requerida": "Identificar correctamente la condición, variable o estructura principal antes de resolver.",
                "error_comun": "Confundir cuándo repetir con qué acción se repite.",
                "pregunta_tecnica_sugerida": "¿Qué condición o dato controla el avance del algoritmo?",
            },
            "critic_of_exercise": "correcto" if generated_exercise else "corrección técnica: falta ejercicio para evaluar",
            "corrected_exercise": {},
        },
    )
    analysis = data.get("technical_analysis", {})
    if not isinstance(analysis, dict):
        analysis = {
            "concepto_clave": topic,
            "precision_requerida": str(analysis),
            "error_comun": "No identificado.",
            "pregunta_tecnica_sugerida": "¿Qué dato o condición controla el algoritmo?",
        }
    critic = data.get("critic_of_exercise", "correcto")
    corrected_exercise = data.get("corrected_exercise", {})
    if not isinstance(corrected_exercise, dict):
        corrected_exercise = {}

    agents_used.append("especialista_tecnico")
    contributions["especialista"] = (
        f"Concepto clave: {analysis.get('concepto_clave', topic)}. "
        f"Pregunta sugerida: {analysis.get('pregunta_tecnica_sugerida', '')}"
    )
    debate.append(
        {
            "agente": "Especialista Técnico",
            "modelo": AGENT_MODEL_LABELS["especialista"],
            "accion": "ejecutó + criticó al Generador",
            "aporte": (
                f"identificó {analysis.get('concepto_clave', topic)} | "
                f"ejercicio: {critic}"
            )[:220],
        }
    )
    agents_trace["especialista_tecnico"] = (
        f"activado — {analysis.get('concepto_clave', topic)} | ejercicio: {critic}"
    )
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["especialista"],
        modelo=modelo,
        ronda=1,
        accion="propone",
        mensaje=(
            f"Propuesta: concepto clave = {analysis.get('concepto_clave', topic)} | "
            f"Error común = {analysis.get('error_comun', 'no identificado')}"
        )[:220],
        estado="working",
    )
    veredicto = "aprobado" if critic == "correcto" else "sugiere"
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["especialista"],
        modelo=modelo,
        ronda=2,
        accion="critica",
        mensaje=(
            f"Crítica al Generador: {critic}"
            if critic != "correcto"
            else "Crítica al Generador: ejercicio técnicamente coherente ✓"
        )[:220],
        estado="working",
        critica_a="Generador de Contenido",
        veredicto=veredicto,
    )

    return {
        "technical_analysis": analysis,
        "critic_of_exercise": critic,
        "corrected_exercise": corrected_exercise,
        "rag_context": contexto,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_contributions": contributions,
        "agents_debate": debate,
        "debate_events": debate_events,
        "ronda_actual": 2,
    }
