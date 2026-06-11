import json
import os
import threading
from queue import Empty, Queue

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

try:
    import config  # noqa: F401 — carga .env al iniciar Flask
    from .agent import crear_agente, reiniciar_historial
    from .services.progress_service import obtener_progreso, TEMAS_ETIQUETAS
except ImportError:
    import config  # noqa: F401
    from agent import crear_agente, reiniciar_historials
    from services.progress_service import obtener_progreso, TEMAS_ETIQUETAS

app = Flask(__name__)
app.secret_key = os.urandom(24)

agente = None


def obtener_agente():
    global agente
    if agente is None:
        agente = crear_agente()
    return agente


def _mensaje_error_usuario(error: Exception) -> str:
    detalle = str(error)
    error_type = type(error).__name__
    texto_error = f"{error_type}: {detalle}".lower()

    if (
        "retryerror" in texto_error
        or "httpstatuserror" in texto_error
        or "rate limit" in texto_error
        or "429" in texto_error
        or "503" in texto_error
        or "502" in texto_error
        or "504" in texto_error
    ):
        return (
            "El servicio de IA está tardando o está temporalmente ocupado. "
            "Intenta enviar tu mensaje nuevamente en unos segundos."
        )

    return detalle


def _extraer_payload_chat():
    data = request.get_json(silent=True) or {}
    pregunta = (data.get("message") or data.get("mensaje") or "").strip()
    allowed_agents = data.get("allowed_agents") or data.get("agentes_seleccionados")
    modo = data.get("modo") or data.get("modo_aprendizaje") or "socratico"
    return pregunta, allowed_agents, modo


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/progress")
def progress():
    progreso = obtener_progreso()
    return jsonify(
        {
            "topic_progress": progreso,
            "labels": TEMAS_ETIQUETAS,
        }
    )


@app.route("/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        pregunta, allowed_agents, modo = _extraer_payload_chat()
        if not pregunta:
            return jsonify({"error": "Mensaje vacío"}), 400

        agente_fn = obtener_agente()
        resultado = agente_fn(pregunta, allowed_agents, modo)
        return jsonify(
            {
                "respuesta": resultado["respuesta"],
                "response": resultado["respuesta"],
                "agents_trace": resultado.get("agents_trace", {}),
                "executed_agents": resultado.get("executed_agents", []),
                "agents_debate": resultado.get("agents_debate", []),
                "agents_contributions": resultado.get("agents_contributions", {}),
                "orchestrator_decision": resultado.get("orchestrator_decision", {}),
                "debate_events": resultado.get("debate_events", []),
                "topic_progress": resultado.get("topic_progress", {}),
                "modo_aprendizaje": resultado.get("modo_aprendizaje", modo),
            }
        )
    except Exception as e:
        return jsonify({"error": _mensaje_error_usuario(e)}), 500


@app.route("/chat/stream", methods=["POST"])
@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    pregunta, allowed_agents, modo = _extraer_payload_chat()
    if not pregunta:
        return jsonify({"error": "Mensaje vacío"}), 400

    event_queue: Queue = Queue()
    resultado_holder: dict = {}
    error_holder: dict = {}

    def ejecutar_grafo():
        try:
            agente_fn = obtener_agente()
            resultado_holder["data"] = agente_fn(
                pregunta,
                allowed_agents,
                modo,
                event_queue=event_queue,
            )
        except Exception as exc:
            error_holder["error"] = exc
        finally:
            event_queue.put({"tipo": "_stream_end"})

    thread = threading.Thread(target=ejecutar_grafo, daemon=True)
    thread.start()

    def generar():
        while True:
            try:
                evento = event_queue.get(timeout=180)
            except Empty:
                yield f"data: {json.dumps({'tipo': 'error', 'mensaje': 'Tiempo de espera agotado', 'estado': 'error'}, ensure_ascii=False)}\n\n"
                break

            if evento.get("tipo") == "_stream_end":
                if error_holder.get("error"):
                    payload = {
                        "tipo": "error",
                        "mensaje": _mensaje_error_usuario(error_holder["error"]),
                        "estado": "error",
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break

            yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

            if evento.get("tipo") == "respuesta_final" or evento.get("estado") == "done":
                break

        thread.join(timeout=5)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(
        stream_with_context(generar()),
        mimetype="text/event-stream",
        headers=headers,
    )


@app.route("/reiniciar", methods=["POST"])
def reiniciar():
    global agente
    agente = None
    reiniciar_historial()
    return jsonify({"mensaje": "Sesión reiniciada correctamente"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("Iniciando sistema de tutoría socrática multiagente...")
    print(f"Abre tu navegador en: http://localhost:{port}")
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", host="0.0.0.0", port=port)
