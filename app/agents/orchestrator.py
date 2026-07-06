try:
    from ..config import ALLOWED_TOPICS
    from ..services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from ..services.memory_service import obtener_intentos_tema
    from ..services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from ..state import TutorState
    from ..utils import (
        detectar_codigo,
        detectar_fuera_silabo,
        detectar_tema_silabo,
        extraer_json,
        formatear_historial,
    )
except ImportError:
    from config import ALLOWED_TOPICS
    from services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from services.memory_service import obtener_intentos_tema
    from services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from state import TutorState
    from utils import (
        detectar_codigo,
        detectar_fuera_silabo,
        detectar_tema_silabo,
        extraer_json,
        formatear_historial,
    )


EMOCIONES_FRUSTRACION = {"frustracion", "desmotivacion", "ansiedad"}
BLOQUEO_FRASES = (
    "no sé",
    "no se",
    "no entiendo",
    "explícame",
    "explicame",
    "no puedo",
    "ayúdame",
    "ayudame",
    "me rindo",
    "no lo entiendo",
)
PROGRESO_FRASES = (
    "creo que",
    "entiendo",
    "sería",
    "seria",
    "es cuando",
    "se mantiene",
    "se cumple",
    "termina",
    "el número",
    "el numero",
    "la condición",
    "la condicion",
    "contador",
    "repeticiones",
)
AGENTES_COLABORATIVOS = ("motivador", "generador", "especialista", "pedagogo")

RESPUESTA_FUERA_SILABO = (
    "Ese tema está fuera del contenido del curso de Algoritmia y Programación "
    "de la UPAO. Solo puedo ayudarte con: variables, operadores, estructuras "
    "secuenciales, condicionales y bucles."
)


def _detectar_bloqueo(mensaje: str) -> bool:
    texto = (mensaje or "").lower()
    return any(frase in texto for frase in BLOQUEO_FRASES)


def _detectar_progreso(mensaje: str, bloqueo: bool) -> str:
    texto = (mensaje or "").lower().strip()
    if bloqueo:
        return "bloqueado"
    if any(frase in texto for frase in PROGRESO_FRASES):
        return "avance_parcial"
    if len(texto.split()) <= 5 and texto:
        return "respuesta_breve"
    return "sin_evidencia"


def _limitar_texto(texto: str, max_chars: int = 1400) -> str:
    if len(texto or "") <= max_chars:
        return texto or ""
    return (texto or "")[-max_chars:]


def _agentes_seleccionados(state: TutorState) -> list[str]:
    selected = state.get("agentes_seleccionados")
    if selected:
        return selected

    allowed_agents = state.get("allowed_agents", {})
    agentes = [
        agente
        for agente in AGENTES_COLABORATIVOS
        if bool(allowed_agents.get(agente, True))
    ]
    if "pedagogo" not in agentes:
        agentes.append("pedagogo")
    return agentes


def _debate_no_seleccionados(agentes_seleccionados: list[str]) -> list[dict[str, str]]:
    debate = []
    nombres = {
        "motivador": "Motivador",
        "generador": "Generador de Contenido",
        "especialista": "Especialista Técnico",
    }
    for agente, nombre in nombres.items():
        if agente not in agentes_seleccionados:
            debate.append(
                {
                    "agente": nombre,
                    "modelo": AGENT_MODEL_LABELS.get(agente, "sin modelo"),
                    "accion": "no seleccionado",
                    "aporte": "El usuario desactivó este agente para el turno.",
                }
            )
    return debate


def _ajustar_por_modo(state: TutorState, agentes_seleccionados: list[str]) -> dict:
    modo = state.get("modo_aprendizaje", "socratico")
    attempt_count = state.get("attempt_count", 1)
    activate_motivator = state.get("activate_motivator", False)
    activate_technical = "especialista" in agentes_seleccionados
    activate_exercise_generator = "generador" in agentes_seleccionados

    if modo == "socratico":
        activate_exercise_generator = False
        activate_motivator = activate_motivator and "motivador" in agentes_seleccionados
        activate_technical = state.get("has_code", False) and "especialista" in agentes_seleccionados
    elif modo == "tutorial":
        activate_exercise_generator = True
        activate_technical = True
        activate_motivator = False
    elif modo == "reto":
        activate_exercise_generator = False
        activate_motivator = False
        activate_technical = True

    return {
        "activate_motivator": activate_motivator,
        "activate_technical": activate_technical,
        "activate_exercise_generator": activate_exercise_generator,
    }


def agente_orquestador(state: TutorState, retriever) -> TutorState:
    llm = get_llm_for_agent("orquestador")
    modelo = AGENT_MODEL_LABELS["orquestador"]
    debate_events = emitir_inicio(
        state,
        "orquestador",
        modelo,
        ronda=1,
        mensaje="Analizando mensaje, historial y contexto emocional...",
    )
    history = state.get("history", [])
    historial_texto = _limitar_texto(formatear_historial(history[-6:]))
    mensaje = state["student_message"]
    has_code = detectar_codigo(mensaje)
    bloqueo = _detectar_bloqueo(mensaje)
    out_of_syllabus = detectar_fuera_silabo(mensaje) or not detectar_tema_silabo(mensaje)
    progreso_local = _detectar_progreso(mensaje, bloqueo)
    agentes_seleccionados = _agentes_seleccionados(state)
    modo = state.get("modo_aprendizaje", "socratico")

    if out_of_syllabus:
        agents_trace = dict(state.get("agents_trace", {}))
        agents_trace.update(
            {
                "orquestador": "Ruta: fuera_silabo. La consulta no pertenece al sílabo.",
                "motivador": "no activado",
                "generador_ejercicios": "no activado",
                "especialista_tecnico": "no activado",
                "pedagogo_socratico": "no activado",
                "fuera_silabo": "pendiente",
            }
        )
        decision = {
            "ruta": "fuera_silabo",
            "motivo": "La consulta no corresponde a los temas permitidos del curso.",
            "prioridad": "fuera_silabo",
        }
        debate = list(state.get("agents_debate", []))
        debate.append(
            {
                "agente": "Orquestador",
                "modelo": modelo,
                "accion": "rechazó por sílabo",
                "aporte": decision["motivo"],
            }
        )
        debate_events = emitir(
            {**state, "debate_events": debate_events},
            agente=AGENTE_NOMBRES["orquestador"],
            modelo=modelo,
            ronda=1,
            accion="fuera de sílabo",
            mensaje="La consulta no pertenece al curso. Se deriva al agente de rechazo.",
            estado="working",
        )
        return {
            "route": "fuera_silabo",
            "topic": "fuera_silabo",
            "difficulty_type": "fuera_silabo",
            "emotion": "neutral",
            "bloqueo": False,
            "student_progress": "sin_evidencia",
            "out_of_syllabus": True,
            "activate_motivator": False,
            "activate_technical": False,
            "activate_exercise_generator": False,
            "orchestrator_decision": decision,
            "agente_respondedor": "fuera_silabo",
            "agents_used": ["orquestador"],
            "agents_trace": agents_trace,
            "agents_contributions": {"orquestador": RESPUESTA_FUERA_SILABO},
            "agents_debate": debate,
            "debate_events": debate_events,
            "ronda_actual": 1,
        }

    docs = retriever.invoke(mensaje)
    contexto = _limitar_texto("\n\n".join([doc.page_content for doc in docs]), 1200)

    agente_respondedor = {
        "socratico": "pedagogo",
        "tutorial": "generador",
        "reto": "especialista",
    }.get(modo, "pedagogo")

    prompt = f"""
Eres el Orquestador de una arquitectura multiagente colaborativa para tutoría
socrática en Algoritmia y Programación UPAO.

Modelo usado: {AGENT_MODEL_LABELS["orquestador"]}. Es apropiado para clasificación
rápida y económica de intención, emoción y ruta.

Rol como ejecutor:
- Lee TutorState: mensaje del estudiante, historial, agentes seleccionados,
  detección local de código/bloqueo y contexto RAG del sílabo.
- Escribe TutorState: topic, difficulty_type, emotion, bloqueo, student_progress,
  out_of_syllabus, orchestrator_decision, agents_contributions y agents_debate.
- Eliges el flujo según TutorState.modo_aprendizaje.
- La detección fuera de sílabo siempre tiene prioridad.
- El respondedor final por modo es fijo: socrático=Pedagogo, tutorial=Generador,
  reto=Especialista.

Temas permitidos:
{ALLOWED_TOPICS}

Modo de aprendizaje: {modo}
Agente respondedor final: {agente_respondedor}

Agentes seleccionados por el estudiante:
{agentes_seleccionados}

Señales locales:
- contiene código/pseudocódigo/lógica: {has_code}
- bloqueo explícito: {bloqueo}
- fuera de sílabo probable: {out_of_syllabus}
- progreso local: {progreso_local}

Contexto RAG del sílabo:
{contexto}

Historial reciente:
{historial_texto}

Devuelve SOLO JSON válido:
{{
  "topic": "tema específico del curso o tema_no_identificado",
  "difficulty_type": "confusion_conceptual|error_logico|pregunta_ambigua|ninguna",
  "emotion": "neutral|frustracion|desmotivacion|ansiedad|bloqueo",
  "bloqueo": true,
  "student_progress": "avance_correcto|avance_parcial|respuesta_breve|bloqueado|sin_evidencia",
  "out_of_syllabus": false,
  "diagnostic_summary": "diagnóstico breve y específico",
  "orchestrator_decision": {{
    "ruta": "socratico|tutorial|reto|fuera_silabo",
    "motivo": "por qué este modo corresponde al turno",
    "prioridad": "{agente_respondedor}"
  }}
}}

Mensaje actual:
{mensaje}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "topic": "tema_no_identificado",
            "difficulty_type": "pregunta_ambigua",
            "emotion": "bloqueo" if bloqueo else "neutral",
            "bloqueo": bloqueo,
            "student_progress": progreso_local,
            "out_of_syllabus": out_of_syllabus,
            "diagnostic_summary": "El estudiante necesita orientación pedagógica.",
            "orchestrator_decision": {
                "ruta": modo,
                "motivo": "Se aplica el flujo fijo del modo de aprendizaje activo.",
                "prioridad": agente_respondedor,
            },
        },
    )

    topic = data.get("topic", "tema_no_identificado")
    emotion = data.get("emotion", "neutral").lower()
    bloqueo = bloqueo or bool(data.get("bloqueo")) or emotion == "bloqueo"
    if bloqueo and emotion == "neutral":
        emotion = "bloqueo"
    student_progress = data.get("student_progress", progreso_local)
    if bloqueo:
        student_progress = "bloqueado"
    attempt_count = obtener_intentos_tema(topic) + 1
    out_of_syllabus = out_of_syllabus or bool(data.get("out_of_syllabus"))

    orchestrator_decision = data.get("orchestrator_decision", {})
    if not isinstance(orchestrator_decision, dict):
        orchestrator_decision = {}
    orchestrator_decision = {
        "ruta": orchestrator_decision.get(
            "ruta", modo
        ),
        "motivo": orchestrator_decision.get(
            "motivo",
            "Se coordina apoyo, ejercicio, precisión técnica e integración final.",
        ),
        "prioridad": agente_respondedor,
    }

    activate_motivator = emotion in EMOCIONES_FRUSTRACION
    activate_technical = "especialista" in agentes_seleccionados
    activate_exercise_generator = "generador" in agentes_seleccionados
    ajustes_modo = _ajustar_por_modo(
        {
            **state,
            "activate_motivator": activate_motivator,
            "attempt_count": attempt_count,
        },
        agentes_seleccionados,
    )
    activate_motivator = ajustes_modo["activate_motivator"]
    activate_technical = ajustes_modo["activate_technical"]
    activate_exercise_generator = ajustes_modo["activate_exercise_generator"]
    contributions = dict(state.get("agents_contributions", {}))
    contributions["orquestador"] = (
        f"Tema: {topic}. Prioridad: {orchestrator_decision['prioridad']}."
    )
    debate = list(state.get("agents_debate", []))
    debate.append(
        {
            "agente": "Orquestador",
            "modelo": AGENT_MODEL_LABELS["orquestador"],
            "accion": "planificó",
            "aporte": (
                f"{orchestrator_decision['ruta']} | "
                f"{orchestrator_decision['motivo']}"
            )[:220],
        }
    )
    debate.extend(_debate_no_seleccionados(agentes_seleccionados))

    activando = []
    if activate_motivator:
        activando.append("Motivador")
    if activate_exercise_generator:
        activando.append("Generador")
    if activate_technical:
        activando.append("Especialista")
    if modo == "socratico" or (modo == "reto" and attempt_count > 2):
        activando.append("Pedagogo")
    mensaje_sse = (
        f"Detectó tema: {topic} | Nivel: {data.get('difficulty_type', 'pregunta_ambigua')} | "
        f"Modo: {modo} | Respondedor: {agente_respondedor} | "
        f"Activando: {' + '.join(activando)}"
    )
    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["orquestador"],
        modelo=modelo,
        ronda=1,
        accion="analizando",
        mensaje=mensaje_sse,
        estado="working",
    )

    agents_trace = {
        "orquestador": (
            f"Ruta: {orchestrator_decision['ruta']}. "
            f"{orchestrator_decision['motivo']} | "
            f"Prioridad: {orchestrator_decision['prioridad']}"
        ),
        "motivador": (
            "pendiente"
            if "motivador" in agentes_seleccionados and activate_motivator
            else "no activado"
        ),
        "generador_ejercicios": "pendiente" if activate_exercise_generator else "no activado",
        "especialista_tecnico": "pendiente" if activate_technical else "no activado",
        "fuera_silabo": "sí" if out_of_syllabus else "no",
        "pedagogo_socratico": (
            "pendiente"
            if modo == "socratico" or (modo == "reto" and attempt_count > 2)
            else "no activado"
        ),
    }

    return {
        "agentes_seleccionados": agentes_seleccionados,
        "topic": topic,
        "difficulty_type": data.get("difficulty_type", "pregunta_ambigua"),
        "emotion": emotion,
        "bloqueo": bloqueo,
        "student_progress": student_progress,
        "attempt_count": attempt_count,
        "has_code": has_code,
        "out_of_syllabus": out_of_syllabus,
        "activate_motivator": activate_motivator,
        "activate_technical": activate_technical,
        "activate_exercise_generator": activate_exercise_generator,
        "diagnostic_summary": data.get(
            "diagnostic_summary",
            "El estudiante necesita orientación pedagógica.",
        ),
        "orchestrator_decision": orchestrator_decision,
        "agente_respondedor": agente_respondedor,
        "rag_context": contexto,
        "agents_used": ["orquestador"],
        "agents_trace": agents_trace,
        "agents_contributions": contributions,
        "agents_debate": debate,
        "debate_events": debate_events,
        "ronda_actual": 1,
        "route": modo,
        "route_reason": orchestrator_decision["motivo"],
    }
