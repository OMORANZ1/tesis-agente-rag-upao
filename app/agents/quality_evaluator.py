try:
    from ..services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from ..services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from ..state import TutorState
    from ..utils import extraer_json
except ImportError:
    from services.llm_service import AGENT_MODEL_LABELS, get_llm_for_agent
    from services.sse_service import AGENTE_NOMBRES, emitir, emitir_inicio
    from state import TutorState
    from utils import extraer_json


def agente_evaluador_calidad(state: TutorState) -> TutorState:
    llm = get_llm_for_agent("evaluador")
    modelo = AGENT_MODEL_LABELS["evaluador"]
    debate_events = emitir_inicio(
        state,
        "evaluador",
        modelo,
        ronda=3,
        mensaje="Verificando criterios pedagógicos de la respuesta final...",
    )

    respuesta = state.get("final_response", "")
    topic = state.get("topic", "tema_no_identificado")
    modo = state.get("modo_aprendizaje", "socratico")
    regen_count = state.get("quality_regen_count", 0)

    prompt = f"""
Eres el Evaluador de Calidad de un tutor socrático universitario.
Revisa la respuesta final ANTES de enviarla al estudiante.

Modo de aprendizaje: {modo}
Tema: {topic}

Criterios obligatorios:
1. NO contiene código completo ni solución directa.
2. Está alineada al curso de Algoritmia y Programación (primer ciclo).
3. Es apropiada para el nivel del estudiante (básico/intermedio).
4. Respeta el modo de aprendizaje activo.

Reglas por modo:
- socratico: solo una pregunta orientadora; no explicación ni ejemplo.
- tutorial: explicación breve + ejemplo concreto + una pregunta de verificación.
- reto: reto práctico directo; no explicación inicial; no es obligatorio hacer pregunta.
  Si attempt_count es bajo, no debe dar pistas. Si da pista, debe ser mínima.

Devuelve SOLO JSON válido:
{{
  "aprobado": true,
  "criterio_fallido": "",
  "feedback": "retroalimentación breve para regenerar si falla",
  "respuesta_correcta_estudiante": false
}}

Respuesta a evaluar:
{respuesta}
"""
    response = llm.invoke(prompt)
    data = extraer_json(
        response.content,
        {
            "aprobado": True,
            "criterio_fallido": "",
            "feedback": "",
            "respuesta_correcta_estudiante": False,
        },
    )

    aprobado = bool(data.get("aprobado", True))
    feedback = data.get("feedback", "") or data.get("criterio_fallido", "")
    respuesta_correcta = bool(data.get("respuesta_correcta_estudiante", False))

    if aprobado:
        mensaje = "Todos los criterios pedagógicos aprobados. Respuesta lista para el estudiante."
        accion = "aprobó"
        veredicto = "aprobado"
    else:
        mensaje = (
            f"Criterio fallido: {data.get('criterio_fallido', 'pedagógico')}. "
            f"{feedback}"
        )[:220]
        accion = "rechazó"
        veredicto = "rechazado"

    debate_events = emitir(
        {**state, "debate_events": debate_events},
        agente=AGENTE_NOMBRES["evaluador"],
        modelo=modelo,
        ronda=3,
        accion=accion,
        mensaje=mensaje,
        estado="working",
        veredicto=veredicto,
    )

    if not aprobado and regen_count >= 2:
        aprobado = True
        feedback = ""
        debate_events = emitir(
            {**state, "debate_events": debate_events},
            agente=AGENTE_NOMBRES["evaluador"],
            modelo=modelo,
            ronda=3,
            accion="aprobó",
            mensaje="Máximo de regeneraciones alcanzado. Se envía la mejor versión disponible.",
            estado="working",
            veredicto="aprobado_forzado",
        )

    agents_used = list(state.get("agents_used", []))
    agents_used.append("evaluador_calidad")
    agents_trace = dict(state.get("agents_trace", {}))
    agents_trace["evaluador_calidad"] = f"{accion} — {mensaje[:80]}"
    debate = list(state.get("agents_debate", []))
    debate.append(
        {
            "agente": AGENTE_NOMBRES["evaluador"],
            "modelo": modelo,
            "accion": accion,
            "aporte": mensaje[:220],
        }
    )

    return {
        "quality_approved": aprobado,
        "quality_feedback": "" if aprobado else feedback,
        "quality_regen_count": regen_count + (0 if aprobado else 1),
        "student_answer_correct": respuesta_correcta,
        "debate_events": debate_events,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
        "agents_debate": debate,
        "ronda_actual": 3,
    }
