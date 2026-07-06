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
    modo = state.get("modo_aprendizaje", "socratico")
    if modo == "tutorial":
        return "explicación tutorial con ejemplo y verificación"
    if modo == "reto":
        return "reto práctico con pistas mínimas"
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
        return """
MODO TUTORIAL ACTIVO:
- Primero explica el concepto de forma clara y concisa.
- Luego da un ejemplo concreto y simple.
- Termina siempre con UNA pregunta de verificación.
- Puedes dar información directa, no seas socrático puro.
- El objetivo es que el estudiante comprenda el concepto.
"""
    if modo == "reto":
        return f"""
MODO RETO ACTIVO:
- Presenta inmediatamente un problema práctico para resolver.
- NO expliques el concepto ni hagas preguntas orientadoras al inicio.
- Solo da pistas si attempt_count > 2. Intento actual: {attempt_count}.
- Las pistas deben ser mínimas, una por vez.
- El objetivo es que el estudiante resuelva por su cuenta.
"""
    return """
MODO SOCRÁTICO ACTIVO:
- Responde ÚNICAMENTE con preguntas orientadoras.
- NUNCA des explicaciones directas ni ejemplos.
- NUNCA des la respuesta aunque el estudiante la pida.
- Una sola pregunta por respuesta, específica y progresiva.
- El objetivo es que el estudiante llegue solo a la respuesta.
"""


def _instruccion_progresiva(state: TutorState, attempt_count: int) -> str:
    modo = state.get("modo_aprendizaje", "socratico")
    if modo == "tutorial":
        return (
            "Modo tutorial: prioriza comprensión. Mantén explicación y ejemplo "
            "breves, y cierra con una sola pregunta de verificación."
        )
    if modo == "reto":
        if attempt_count <= 2:
            return (
                "Modo reto intentos 1-2: entrega solo un reto concreto. "
                "No expliques ni des pistas todavía."
            )
        return (
            "Modo reto intento 3 o superior: puedes añadir una pista mínima, "
            "sin resolver el reto."
        )
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


def _forzar_una_pregunta(respuesta: str, state: TutorState, preguntas_hechas: list[str]) -> str:
    preguntas = _extraer_preguntas(respuesta)
    for pregunta in preguntas:
        if not _pregunta_repetida(pregunta, preguntas_hechas):
            return pregunta
    return _pregunta_alternativa(state, preguntas_hechas)


def _reparar_respuesta_si_necesario(
    respuesta: str,
    llm,
    preguntas_hechas: list[str],
    state: TutorState,
) -> str:
    modo = state.get("modo_aprendizaje", "socratico")
    preguntas = _extraer_preguntas(respuesta)
    tiene_repetida = any(
        _pregunta_repetida(pregunta, preguntas_hechas) for pregunta in preguntas
    )
    respuesta_normalizada = _normalizar_pregunta(respuesta)
    frase_prohibida = "puedes pensar" in respuesta_normalizada

    if modo == "reto":
        if len(preguntas) <= 1 and not frase_prohibida:
            return respuesta
    elif len(preguntas) == 1 and not tiene_repetida and not frase_prohibida:
        return respuesta

    regla_pregunta = (
        "No es obligatorio hacer pregunta en modo reto. Si haces una, que sea solo una."
        if modo == "reto"
        else "Exactamente UNA pregunta."
    )
    prompt = f"""
Reescribe la respuesta para corregir estrictamente:
- {regla_pregunta}
- No repetir preguntas ya hechas.
- No usar "puedes pensar".
- No entregar código completo ni solución directa.
- Mantener tono humano y reconocer avances correctos si existen.
- Máximo 110 palabras.
- Respetar el modo activo: {modo}.

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
    if modo == "reto":
        return corregida
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
    if state.get("route") == "fuera_silabo":
        return {
            "final_response": "",
            "agents_trace": {
                **dict(state.get("agents_trace", {})),
                "pedagogo_socratico": "no activado por fuera_silabo",
            },
        }

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
    modo = state.get("modo_aprendizaje", "socratico")
    attempt_count = state.get("attempt_count", 1) if modo == "reto" else registrar_intento(topic)
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-6:]), 1400)
    preguntas_hechas = state.get("preguntas_hechas", [])
    preguntas_hechas_texto = _formatear_preguntas_hechas(preguntas_hechas)

    contexto = state.get("rag_context", "")
    if not contexto:
        docs = retriever.invoke(f"{state['student_message']} {topic}")
        contexto = "\n\n".join([doc.page_content for doc in docs])
    contexto = _limitar_texto(contexto, 1200)

    if modo == "reto":
        apoyo = ""
        if attempt_count > 2:
            prompt_apoyo = f"""
Eres el Pedagogo Socrático como apoyo interno del modo reto.
El Especialista Técnico ya dio la respuesta principal. No la reemplaces.

Reglas:
- Si attempt_count es 3 o 4, escribe UNA pista mínima sin solución.
- Si attempt_count es mayor que 4, escribe una solución parcial breve con explicación.
- No agregues preguntas orientadoras largas.

Contexto del sílabo:
{contexto}

Respuesta principal del Especialista:
{state.get("final_response", "")}

Tema: {topic}
Intentos: {attempt_count}
Mensaje del estudiante:
{state["student_message"]}

Apoyo:
"""
            apoyo = llm.invoke(prompt_apoyo).content.strip()

        respuesta = (
            f"{state.get('final_response', '')}\n\n{apoyo}".strip()
            if apoyo
            else state.get("final_response", "")
        )
        agents_used = list(state.get("agents_used", []))
        agents_used.append("pedagogo_socratico")
        agents_trace = dict(state.get("agents_trace", {}))
        contributions = dict(state.get("agents_contributions", {}))
        debate = list(state.get("agents_debate", []))
        agents_trace["pedagogo_socratico"] = (
            "apoyo en reto — pista mínima" if apoyo else "no activado"
        )
        if apoyo:
            contributions["pedagogo"] = apoyo
            debate.append(
                {
                    "agente": "Pedagogo Socrático",
                    "modelo": AGENT_MODEL_LABELS["pedagogo"],
                    "accion": "apoyó reto",
                    "aporte": apoyo[:220],
                }
            )
        return {
            "rag_context": contexto,
            "final_response": respuesta,
            "quality_feedback": "",
            "agents_used": agents_used,
            "agents_trace": agents_trace,
            "agents_contributions": contributions,
            "agents_debate": debate,
            "debate_events": debate_events,
            "ronda_actual": 3,
        }

    motivational_message = state.get("motivational_message", {})
    generated_exercise = _ejercicio_vigente(state)
    technical_analysis = state.get("technical_analysis", {})
    critic_of_motivator = state.get("critic_of_motivator", "")
    critic_of_exercise = state.get("critic_of_exercise", "")
    orchestrator_decision = state.get("orchestrator_decision", {})
    prompt = f"""
Eres un tutor socrático ESTRICTO. Tu ÚNICA función es hacer UNA pregunta
orientadora por respuesta. NUNCA expliques, NUNCA des ejemplos, NUNCA respondas
tu propia pregunta. Si sientes el impulso de explicar algo, conviértelo en una
pregunta.

Reglas obligatorias:
- Devuelve exactamente UNA pregunta.
- No agregues explicación, ejemplo, saludo, lista, título ni cierre.
- No uses frases como "Por ejemplo", "Es decir", "Recuerda" o "La idea es".
- Basa la pregunta en el contexto del sílabo y en el mensaje del estudiante.
- No repitas preguntas ya hechas ni con palabras similares.

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
- Route: {state.get("route", "colaborativa")}

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
    respuesta = _forzar_una_pregunta(respuesta, state, preguntas_hechas)
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
