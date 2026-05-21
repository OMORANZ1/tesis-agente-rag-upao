import re
import unicodedata

try:
    from ..config import ALLOWED_TOPICS
    from ..services.memory_service import registrar_intento
    from ..state import TutorState
    from ..utils import formatear_historial
except ImportError:
    from config import ALLOWED_TOPICS
    from services.memory_service import registrar_intento
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

    preguntas_con_apertura_malformada = [
        pregunta.strip()
        for pregunta in re.findall(r"\?[^?]+\?", texto or "")
        if pregunta.strip()
    ]
    if preguntas_con_apertura_malformada:
        return preguntas_con_apertura_malformada

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


def _pregunta_alternativa(topic: str, preguntas_hechas: list[str]) -> str:
    opciones = [
        "¿Cuál es la condición que debe cumplirse para que el ciclo siga repitiéndose?",
        "¿Qué dato cambia en cada repetición del bucle?",
        "¿En qué momento debería detenerse el bucle?",
        "¿Qué parte del problema indica cuántas veces debes repetir una acción?",
    ]
    if "while" in topic.lower():
        opciones = [
            "¿Cuál es la condición que mantiene activo al while?",
            "¿Qué tendría que cambiar para que la condición del while deje de cumplirse?",
            "¿En qué momento debería detenerse ese while?",
        ]
    if "for" in topic.lower():
        opciones = [
            "¿Cuántas repeticiones necesita hacer ese for?",
            "¿Qué valor toma el contador en la primera repetición?",
            "¿Qué cambia en cada vuelta del for?",
        ]

    for pregunta in opciones:
        if not _pregunta_repetida(pregunta, preguntas_hechas):
            return pregunta
    return "¿Qué paso pequeño podrías revisar primero?"


def _respuesta_bloqueo_fallback(
    topic: str,
    preguntas_hechas: list[str],
    generated_exercise: str = "",
) -> str:
    topic_lower = topic.lower()
    if "while" in topic_lower or "bucle" in topic_lower or "ciclo" in topic_lower:
        pista = (
            "Vamos por partes: un bucle repite una acción mientras se cumpla una "
            "condición. En un while, lo más importante es identificar qué condición "
            "mantiene la repetición y qué cambio hará que se detenga."
        )
    elif "for" in topic_lower:
        pista = (
            "Bien, bajémoslo a lo esencial: un for se usa cuando puedes anticipar cuántas veces se "
            "repetirá una acción. El contador cambia en cada vuelta."
        )
    elif "variable" in topic_lower:
        pista = (
            "La idea base es esta: una variable es un espacio donde guardas un dato que "
            "puede cambiar durante el algoritmo."
        )
    else:
        pista = (
            "Probemos con una pista más directa: separa el problema en entrada, proceso y salida. Primero "
            "ubica qué datos tienes y qué decisión o repetición necesitas controlar."
        )

    if generated_exercise:
        pista = (
            "Empecemos con una versión más simple del ejercicio. "
            "Primero identifica la condición o dato principal antes de intentar "
            "resolver todo."
        )

    return f"{pista}\n\n{_pregunta_alternativa(topic, preguntas_hechas)}"


def _instruccion_reconocimiento(state: TutorState) -> str:
    progress = state.get("student_progress", "sin_evidencia")
    if progress == "avance_correcto":
        return (
            "El estudiante acaba de decir algo correcto. Empieza con un reconocimiento "
            "breve y natural, por ejemplo: 'Exacto, esa idea va bien.' Luego agrega "
            "una precisión pequeña y una sola pregunta."
        )
    if progress == "avance_parcial":
        return (
            "El estudiante mostró avance parcial. Empieza validando la parte correcta "
            "sin exagerar, por ejemplo: 'Sí, vas bien por ahí.' Luego corrige o completa "
            "una sola idea y cierra con una pregunta."
        )
    if progress == "respuesta_breve":
        return (
            "El estudiante respondió de forma breve. Retoma su frase y conviértela en "
            "avance: 'Bien, esa es una parte.' Luego enfoca el siguiente paso."
        )
    return (
        "No hay evidencia clara de avance en el último mensaje. Mantén un tono cercano "
        "y evita sonar como plantilla."
    )


def _tipo_respuesta_socratica(state: TutorState, attempt_count: int) -> str:
    if state.get("generated_exercise"):
        return "integración con ejercicio personalizado"
    if state.get("bloqueo"):
        return "pista directa por bloqueo explícito"
    if state.get("technical_analysis"):
        return "guía socrática sobre código/lógica"
    if attempt_count >= 4:
        return "ejercicio simple por vacío conceptual persistente"
    if attempt_count == 3:
        return "pista conceptual directa"
    if attempt_count == 2:
        return "pregunta socrática específica"
    if state.get("motivational_message"):
        return "apoyo afectivo + preguntas orientadoras"
    return "pregunta socrática amplia"


def _instruccion_progresiva(state: TutorState, attempt_count: int) -> str:
    if attempt_count >= 4:
        return (
            "Intento 4 o superior: el estudiante necesita reforzar la base. "
            "Presenta un ejercicio más simple o modular si está disponible, da una "
            "pista inicial concreta y cierra con exactamente UNA pregunta breve para "
            "que identifique el primer paso. No resuelvas el ejercicio."
        )

    if state.get("bloqueo"):
        return (
            "Bloqueo explícito detectado: el estudiante pidió ayuda directa o dijo "
            "que no entiende. No sigas solo con preguntas abiertas. Da una pista "
            "conceptual concreta, breve y accionable, sin código resuelto ni solución "
            "completa. Cierra con exactamente UNA pregunta específica de verificación. "
            "No uses siempre la etiqueta 'Pista concreta:'; úsala solo si ayuda."
        )

    if attempt_count == 1:
        return (
            "Intento 1: formula una pregunta socrática amplia para activar reflexión "
            "general. No des la respuesta directa."
        )
    if attempt_count == 2:
        return (
            "Intento 2: formula una pregunta socrática específica que enfoque al "
            "estudiante en el concepto clave. Evita repetir la pregunta del intento 1."
        )
    if attempt_count == 3:
        return (
            "Intento 3: da una pista conceptual directa, sin código, más concreta que "
            "antes. Cierra con exactamente UNA pregunta específica."
        )

    return (
        "Guía con una sola pregunta orientadora y una pista mínima. No des la "
        "respuesta directa."
    )


def _reparar_respuesta_si_necesario(
    respuesta: str,
    llm,
    preguntas_hechas: list[str],
    instruccion_progresiva: str,
    state: TutorState,
) -> str:
    preguntas = _extraer_preguntas(respuesta)
    tiene_repetida = any(
        _pregunta_repetida(pregunta, preguntas_hechas) for pregunta in preguntas
    )
    respuesta_normalizada = _normalizar_pregunta(respuesta)
    frase_prohibida = "puedes pensar" in respuesta_normalizada
    empieza_preguntando = respuesta.lstrip().startswith(("¿", "?"))

    if state.get("bloqueo") and (frase_prohibida or empieza_preguntando):
        return _respuesta_bloqueo_fallback(
            state.get("topic", "tema_no_identificado"),
            preguntas_hechas,
            state.get("generated_exercise", ""),
        )

    plantilla_excesiva = respuesta.count("Pista concreta:") > 0 and not state.get("bloqueo")

    if (
        len(preguntas) == 1
        and not tiene_repetida
        and not frase_prohibida
        and not plantilla_excesiva
    ):
        return respuesta

    prompt_reparacion = f"""
Reescribe la respuesta del Pedagogo Socrático corrigiendo SOLO estos problemas:
- Debe contener exactamente UNA pregunta.
- Esa pregunta NO debe repetir ni reformular una pregunta ya hecha.
- No uses la frase "puedes pensar".
- Evita sonar como plantilla. No uses "Pista concreta:" salvo bloqueo explícito.
- Si el estudiante dijo algo correcto o parcialmente correcto, reconócelo en una frase breve.
- Mantén una pista progresiva acorde a esta estrategia:
{instruccion_progresiva}
- No entregues código resuelto ni solución completa.
- No agregues varias preguntas en una lista.

Preguntas ya hechas en esta sesión:
{_formatear_preguntas_hechas(preguntas_hechas)}

Respuesta anterior a corregir:
{respuesta}

Respuesta corregida para el estudiante:
"""
    response = llm.invoke(prompt_reparacion)
    return response.content.strip()


def agente_pedagogo_socratico(
    state: TutorState, llm, retriever, system_prompt: str
) -> TutorState:
    topic = state.get("topic", "tema_no_identificado")
    attempt_count = registrar_intento(topic)
    historial_texto = _limitar_texto(formatear_historial(state.get("history", [])[-6:]), 1400)
    preguntas_hechas = state.get("preguntas_hechas", [])
    preguntas_hechas_texto = _formatear_preguntas_hechas(preguntas_hechas)

    if state.get("rag_context"):
        contexto = state["rag_context"]
    else:
        consulta_rag = f"{state['student_message']} {topic}"
        docs = retriever.invoke(consulta_rag)
        contexto = "\n\n".join([d.page_content for d in docs])
    contexto = _limitar_texto(contexto, 1200)

    ayuda_progresiva = _instruccion_progresiva(state, attempt_count)
    reconocimiento = _instruccion_reconocimiento(state)

    bloques_internos = []
    if state.get("motivational_message"):
        bloques_internos.append(
            f"Apoyo afectivo previo (integra con naturalidad, sin repetir textualmente):\n"
            f"{state['motivational_message']}"
        )
    if state.get("technical_analysis"):
        bloques_internos.append(
            f"Análisis técnico interno (usa para formular preguntas, no lo copies):\n"
            f"{state['technical_analysis']}"
        )
    if state.get("generated_exercise"):
        bloques_internos.append(
            f"Ejercicio generado (preséntalo de forma socrática, sin resolverlo):\n"
            f"{state['generated_exercise']}"
        )

    contexto_agentes = (
        "\n\n".join(bloques_internos)
        if bloques_internos
        else "Sin aportes previos de otros agentes."
    )
    contexto_agentes = _limitar_texto(contexto_agentes, 1000)
    system_prompt_compacto = _limitar_texto(system_prompt, 1200)

    prompt = f"""
{system_prompt_compacto}

Actúas como el Agente Pedagogo Socrático, núcleo conductor del sistema.
Eres el ÚNICO que responde directamente al estudiante.

Temas permitidos: {ALLOWED_TOPICS}

Reglas:
- Resguarda la Zona de Desarrollo Próximo (ZDP).
- NUNCA entregues respuestas directas ni código resuelto.
- Integra de forma natural los aportes internos de otros agentes.
- Usa el contexto del sílabo para preguntas reflexivas y pistas conceptuales.
- Haz exactamente UNA pregunta por respuesta. No hagas dos o más preguntas.
- No repitas ninguna pregunta ya hecha en esta sesión, ni con palabras similares.
- Si hay bloqueo explícito, da una pista directa y concreta antes de la pregunta.
- Si el estudiante dice "no entiendo", "explícame", "ayúdame" o similar, NO abras con una pregunta. Primero explica una pista concreta.
- Evita la frase "puedes pensar". Suena repetitiva y no ayuda al bloqueo.
- Si el estudiante dijo algo correcto, reconócelo brevemente antes de avanzar.
- No felicites de forma exagerada. Usa frases humanas y sobrias como "Sí, vas bien", "Exacto", "Esa parte está bien".
- No uses siempre la etiqueta "Pista concreta:". Varía la redacción: "Vamos por partes", "La idea clave es", "Bien, ahora afinemos".
- Responde en máximo 120 palabras.

Formato si hay bloqueo explícito:
[frase cercana + explicación breve y directa, sin código resuelto]

[UNA sola pregunta de verificación]

Ayuda progresiva:
{ayuda_progresiva}

Reconocimiento del avance del estudiante:
{reconocimiento}

Preguntas ya hechas en esta sesión (NO repetir):
{preguntas_hechas_texto}

Contexto del sílabo (RAG):
{contexto}

Historial completo de la conversación:
{historial_texto}

Plan del orquestador:
- Ruta: {state.get("route", "ruta_pedagogica_principal")}
- Motivo: {state.get("route_reason", "")}
- Tema: {topic}
- Dificultad: {state.get("difficulty_type", "pregunta_ambigua")}
- Emoción: {state.get("emotion", "neutral")}
- Bloqueo explícito: {"sí" if state.get("bloqueo") else "no"}
- Progreso del estudiante: {state.get("student_progress", "sin_evidencia")}
- Intentos en el tema: {attempt_count}
- Resumen diagnóstico: {state.get("diagnostic_summary", "")}

Aportes internos de otros agentes:
{contexto_agentes}

Pregunta actual del estudiante:
{state["student_message"]}

Respuesta final para el estudiante:
"""
    response = llm.invoke(prompt)
    respuesta = _reparar_respuesta_si_necesario(
        response.content.strip(),
        llm,
        preguntas_hechas,
        ayuda_progresiva,
        state,
    )
    preguntas_nuevas = _extraer_preguntas(respuesta)[:1]
    tipo_respuesta = _tipo_respuesta_socratica(state, attempt_count)

    agents_used = list(state.get("agents_used", []))
    agents_used.append("pedagogo_socratico")
    agents_trace = dict(state.get("agents_trace", {}))
    agents_trace["pedagogo_socratico"] = f"activo — {tipo_respuesta}"

    return {
        "attempt_count": attempt_count,
        "rag_context": contexto,
        "final_response": respuesta,
        "socratic_response_type": tipo_respuesta,
        "preguntas_nuevas": preguntas_nuevas,
        "agents_used": agents_used,
        "agents_trace": agents_trace,
    }
