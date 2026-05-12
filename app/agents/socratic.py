try:
    from ..services.memory_service import registrar_intento
    from ..state import TutorState
except ImportError:
    from services.memory_service import registrar_intento
    from state import TutorState


def agente_socratico(state: TutorState, llm, retriever, system_prompt: str) -> TutorState:
    attempt_count = registrar_intento(state.get("topic", "tema_no_identificado"))

    consulta_rag = f"{state['student_message']} {state.get('topic', '')}"
    docs = retriever.invoke(consulta_rag)
    contexto = "\n\n".join([d.page_content for d in docs])

    ayuda_progresiva = (
        "El estudiante ya realizo varios intentos. Puedes dar una pista "
        "mas directa o una solucion parcial conceptual, pero no entregues "
        "codigo completo ni pseudocodigo completamente resuelto."
        if attempt_count > 3
        else "Guia con preguntas orientadoras y pistas graduales. No des "
        "la respuesta directa."
    )

    prompt = f"""
{system_prompt}

Actuas como el Agente Socratico, nucleo del sistema multiagente.
Usa el contexto del silabo para guiar al estudiante.

Regla de ayuda progresiva:
{ayuda_progresiva}

No entregues codigo completo. Enfocate en conceptos, razonamiento y preguntas.

Contexto del silabo:
{contexto}

Historial de conversacion:
{state.get("history_text", "")}

Diagnostico:
- Tema: {state.get("topic", "tema_no_identificado")}
- Dificultad: {state.get("difficulty_type", "pregunta_ambigua")}
- Resumen: {state.get("diagnostic_summary", "Sin diagnostico previo.")}
- Intentos en el tema: {attempt_count}

Mensaje motivador previo, si existe:
{state.get("motivational_message", "")}

Pregunta del estudiante:
{state["student_message"]}

Respuesta final:
"""
    response = llm.invoke(prompt)
    respuesta = response.content.strip()
    if state.get("motivational_message"):
        respuesta = f"{state['motivational_message']}\n\n{respuesta}"

    return {
        "attempt_count": attempt_count,
        "rag_context": contexto,
        "final_response": respuesta,
    }
