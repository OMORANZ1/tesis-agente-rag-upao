import re
import unicodedata

try:
    from ..config import ALLOWED_TOPICS
    from ..services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from ..services.memory_service import registrar_intento
    from ..services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from ..state import TutorState
    from ..utils import formatear_historial
except ImportError:
    from config import ALLOWED_TOPICS
    from services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from services.memory_service import registrar_intento
    from services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from state import TutorState
    from utils import formatear_historial


def _extraer_preguntas(texto: str) -> list[str]:
    preguntas_con_apertura = [
        pregunta.strip()
        for pregunta in re.findall(r"¿[^?]*\?", texto or "")
        if pregunta.strip()
    ]
    if preguntas_con_apertura:
        return preguntas_con_apertura

    preguntas_malformadas = [
        pregunta.strip()
        for pregunta in re.findall(r"\?[^?]+\?", texto or "")
        if pregunta.strip()
    ]
    if preguntas_malformadas:
        return preguntas_malformadas

    return [
        pregunta.strip()
        for pregunta in re.findall(r"[^.!?\n]*\?", texto or "")
        if pregunta.strip()
    ]


def _normalizar_pregunta(pregunta: str) -> str:
    texto = unicodedata.normalize("NFD", pregunta.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[¿?¡!.,;:()\"']", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _pregunta_repetida(pregunta: str, preguntas_hechas: list[str]) -> bool:
    pregunta_normalizada = _normalizar_pregunta(pregunta)
    return pregunta_normalizada in {
        _normalizar_pregunta(pregunta_previa)
        for pregunta_previa in preguntas_hechas
    }


def _formatear_preguntas_hechas(preguntas_hechas: list[str]) -> str:
    if not preguntas_hechas:
        return "Aún no hay preguntas previas registradas en esta sesión."
    return "\n".join(f"- {pregunta}" for pregunta in preguntas_hechas[-8:])


def _limitar_texto(texto: str, max_chars: int) -> str:
    if len(texto or "") <= max_chars:
        return texto or ""
    return (texto or "")[-max_chars:]


def _dict_lineas(data: dict, keys: list[str]) -> str:
    if not data:
        return "No disponible."
    return "\n".join(
        f"- {key}: {data.get(key, '')}"
        for key in keys
        if data.get(key)
    ) or "No disponible."


def _tipo_respuesta_socratica(state: TutorState, attempt_count: int) -> str:
    if state.get("generated_exercise") and state.get("technical_analysis"):
        return "integración de apoyo, ejercicio y análisis técnico"
    if state.get("generated_exercise"):
        return "pregunta desde ejercicio práctico"
    if state.get("technical_analysis"):
        return "pregunta técnicamente precisa"
    if state.get("bloqueo") or attempt_count >= 4:
        return "pista directa conceptual"
    return "pregunta socrática basada en RAG"


def _instruccion_modo(state: TutorState, attempt_count: int) -> str:
    modo = state.get("modo_aprendizaje", "socratico")
    if modo == "tutorial":
        return (
            "Modo tutorial: puedes dar una explicación breve y un ejemplo conceptual, "
            "pero siempre termina con exactamente UNA pregunta de verificación."
        )
    if modo == "reto":
        if attempt_count <= 2:
            return (
                "Modo reto: da pistas mínimas. No expliques directamente. "
                "Formula una pregunta que guíe sin revelar la solución."
            )
        return (
            "Modo reto (más de 2 intentos): puedes dar una pista progresiva, "
            "pero sigue sin dar la solución completa."
        )
    return (
        "Modo socrático: solo preguntas orientadoras. "
        "NUNCA des explicaciones directas ni soluciones."
    )


def _instruccion_progresiva(state: TutorState, attempt_count: int) -> str:
    if attempt_count >= 4:
        return (
            "Intento 4 o superior: da una pista conceptual directa, sin código ni "
            "solución completa. Luego formula exactamente una pregunta de verificación."
        )
    if attempt_count == 3:
        return (
            "Intento 3: usa la pista_inicial del ejercicio si existe y formula una "
            "pregunta específica."
        )
    return (
        "Intentos 1-2: formula una pregunta socrática amplia, salvo que haya análisis "
        "técnico o ejercicio activo; en ese caso hazla más precisa."
    )


def _pregunta_alternativa(state: TutorState, preguntas_hechas: list[str]) -> str:
    analysis = state.get("technical_analysis", {})
    pregunta_tecnica = analysis.get("pregunta_tecnica_sugerida") if analysis else ""
    opciones = [
        pregunta_tecnica,
        "¿Qué dato o condición controla el siguiente paso del algoritmo?",
        "¿Qué parte del problema indica cuándo repetir o cuándo detenerse?",
        "¿Qué elemento cambia mientras el algoritmo avanza?",
    ]
    for pregunta in opciones:
        if pregunta and not _pregunta_repetida(pregunta, preguntas_hechas):
            return pregunta
    return "¿Qué paso pequeño podrías revisar primero?"


def _reparar_respuesta_si_necesario(
    respuesta: str,
    llm,
    preguntas_hechas: list[str],
    state: TutorState,
) -> str:
    preguntas = _extraer_preguntas(respuesta)
    tiene_repetida = any(
        _pregunta_repetida(pregunta, preguntas_hechas) for pregunta in preguntas
    )
    respuesta_normalizada = _normalizar_pregunta(respuesta)
    frase_prohibida = "puedes pensar" in respuesta_normalizada

    if len(preguntas) == 1 and not tiene_repetida and not frase_prohibida:
        return respuesta

    prompt = f"""
Reescribe la respuesta para corregir estrictamente:
- Exactamente UNA pregunta.
- No repetir preguntas ya hechas.
- No usar "puedes pensar".
- No entregar código completo ni solución directa.
- Mantener tono humano y reconocer avances correctos si existen.
- Máximo 110 palabras.

Preguntas ya hechas:
{_formatear_preguntas_hechas(preguntas_hechas)}

Pregunta alternativa segura:
{_pregunta_alternativa(state, preguntas_hechas)}

Respuesta anterior:
{respuesta}

Respuesta corregida:
"""
    response = llm.invoke(prompt)
    corregida = response.content.strip()
    preguntas_corregidas = _extraer_preguntas(corregida)
    if len(preguntas_corregidas) != 1:
        base = corregida.split("?")[0].strip()
        return f"{base}\n\n{_pregunta_alternativa(state, preguntas_hechas)}"
    return corregida


def _ejercicio_vigente(state: TutorState) -> dict:
    critic = state.get("critic_of_exercise", "")
    corrected = state.get("corrected_exercise", {})
    if critic.lower().startswith("corrección técnica") and corrected:
        return corrected
    return state.get("generated_exercise", {})


def _resumen_integracion(state: TutorState, attempt_count: int) -> str:
    piezas = []
    if state.get("motivational_message"):
        piezas.append("apoyo emocional")
    if state.get("generated_exercise"):
        piezas.append("ejercicio práctico")
    if state.get("technical_analysis"):
        piezas.append("análisis técnico")
    if not piezas:
        piezas.append("RAG del sílabo")
    return f"Integró {', '.join(piezas)} con progresión intento {attempt_count}."


def agente_pedagogo_socratico(
    state: TutorState, retriever, system_prompt: str
) -> TutorState:
    llm = get_llm_for_agent("pedagogo")
    modelo = AGENT_MODEL_LABELS["pedagogo"]
    quality_feedback = state.get("quality_feedback", "")
    regen = state.get("quality_regen_count", 0)
    debate_events = emitir_inicio(
        state,
        "pedagogo",
        modelo,
        ronda=3,
        mensaje=(
            "Regenerando respuesta según feedback del evaluador..."
            if quality_feedback
            else "Integrando aportes de todos los agentes..."
        ),
    )
    topic = state.get("topic", "tema_no_identificado")
    attempt_count = registrar_intento(topic)
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-6:]), 1400)
    preguntas_hechas = state.get("preguntas_hechas", [])
    preguntas_hechas_texto = _formatear_preguntas_hechas(preguntas_hechas)

    contexto = state.get("rag_context", "")
    if not contexto:
        docs = retriever.invoke(f"{state['student_message']} {topic}")
        contexto = "\n\n".join([doc.page_content for doc in docs])
    contexto = _limitar_texto(contexto, 1200)

    motivational_message = state.get("motivational_message", {})
    generated_exercise = _ejercicio_vigente(state)
    technical_analysis = state.get("technical_analysis", {})
    critic_of_motivator = state.get("critic_of_motivator", "")
    critic_of_exercise = state.get("critic_of_exercise", "")
    orchestrator_decision = state.get("orchestrator_decision", {})
    system_prompt_compacto = _limitar_texto(system_prompt, 900)
    ayuda_progresiva = _instruccion_progresiva(state, attempt_count)
    instruccion_modo = _instruccion_modo(state, attempt_count)

    prompt = f"""
{system_prompt_compacto}

Eres el Agente Pedagogo Socrático, integrador final del sistema.

Modelo usado: {AGENT_MODEL_LABELS["pedagogo"]}. Es apropiado por su capacidad de
integrar debate, tono pedagógico, RAG y restricciones socráticas.

Rol como integrador:
- Lee TutorState: orchestrator_decision, motivational_message, generated_exercise,
  critic_of_motivator, technical_analysis, critic_of_exercise, preguntas_hechas,
  RAG, historial y progreso.
- Escribe TutorState.final_response, preguntas_nuevas, agents_contributions y
  agents_debate.

Reglas obligatorias:
- Eres el único que responde al estudiante.
- NUNCA entregues código completo ni solución directa.
- Haz exactamente UNA pregunta socrática por respuesta.
- No repitas preguntas ya hechas ni con palabras similares.
- Si motivational_message existe, empieza usando o adaptando frase_apoyo.
- Si critic_of_motivator trae sugerencia, ajusta el tono inicial.
- Si technical_analysis existe, basa la pregunta en pregunta_tecnica_sugerida.
- Si generated_exercise existe y critic_of_exercise es "correcto", reformula el
  ejercicio como situación de reflexión.
- Si critic_of_exercise trae corrección, usa el ejercicio corregido.
- Si todos están activos, integra apoyo emocional, ejercicio y precisión técnica.
- Si solo estás tú, usa pregunta socrática basada en RAG.
- Responde en máximo 130 palabras.

Modo de aprendizaje:
{instruccion_modo}

Progresión:
{ayuda_progresiva}

Feedback del Evaluador de Calidad (si existe, corrige la respuesta):
{quality_feedback or "Sin feedback previo."}
Regeneración número: {regen}

Temas permitidos:
{ALLOWED_TOPICS}

Decisión del Orquestador:
{orchestrator_decision}

Apoyo del Motivador:
{_dict_lineas(motivational_message, ["frase_apoyo", "reencuadre"])}
Crítica al Motivador:
{critic_of_motivator or "No disponible."}

Ejercicio vigente:
{_dict_lineas(generated_exercise, ["contexto_real", "ejercicio", "pista_inicial", "nivel"])}
Crítica al ejercicio:
{critic_of_exercise or "No disponible."}

Análisis técnico:
{_dict_lineas(technical_analysis, ["concepto_clave", "precision_requerida", "error_comun", "pregunta_tecnica_sugerida"])}

Preguntas ya hechas:
{preguntas_hechas_texto}

Contexto del sílabo vía RAG:
{contexto}

Historial reciente:
{historial_texto}

Estado del estudiante:
- Tema: {topic}
- Intentos: {attempt_count}
- Bloqueo: {state.get("bloqueo", False)}
- Progreso: {state.get("student_progress", "sin_evidencia")}
- Fuera de sílabo: {state.get("out_of_syllabus", False)}

Mensaje actual:
{state["student_message"]}

Respuesta final para el estudiante:
"""
    response = llm.invoke(prompt)
    respuesta = _reparar_respuesta_si_necesario(
        response.content.strip(),
        llm,
        preguntas_hechas,
        state,
    )
    preguntas_nuevas = _extraer_preguntas(respuesta)[:1]
    tipo_respuesta = _tipo_respuesta_socratica(state, attempt_count)

    agents_used = list(state.get("agents_used", []))
    agents_used.append("pedagogo_socratico")
    agents_trace = dict(state.get("agents_trace", {}))
    contributions = dict(state.get("agents_contributions", {}))
    debate = list(state.get("agents_debate", []))
    aporte = _resumen_integracion(state, attempt_count)

    agents_trace["pedagogo_socratico"] = f"activo — {tipo_respuesta}"
    contributions["pedagogo"] = aporte
    debate.append(
        {
            "agente": "Pedagogo Socrático",
            "modelo": AGENT_MODEL_LABELS["pedagogo"],
            "accion": "integró todo",
            "aporte": aporte[:220],
        }
    )
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["pedagogo"],
        modelo=modelo,
        ronda=3,
        accion="sintetiza",
        mensaje=(
            f"Integrando debate → {tipo_respuesta}. "
            f"{aporte}"
        )[:220],
        estado="final",
    )

    return {
        "attempt_count": attempt_count,
        "rag_context": contexto,
        "final_response": respuesta,
        "socratic_response_type": tipo_respuesta,
        "preguntas_nuevas": preguntas_nuevas,
        "quality_feedback": "",
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_contributions": contributions,
        "agents_debate": debate,
        "debate_events": debate_events,
        "ronda_actual": 3,
    }
