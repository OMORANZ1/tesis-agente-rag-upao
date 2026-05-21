from flask import Flask, render_template, request, jsonify
import os

try:
    from .agent import crear_agente, reiniciar_historial
except ImportError:
    from agent import crear_agente, reiniciar_historial

app = Flask(__name__)
app.secret_key = os.urandom(24)

agente = None


def obtener_agente():
    global agente
    if agente is None:
        agente = crear_agente()
    return agente


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        pregunta = data.get("mensaje", "").strip()
        if not pregunta:
            return jsonify({"error": "Mensaje vacío"}), 400

        agente_fn = obtener_agente()
        resultado = agente_fn(pregunta)
        return jsonify(
            {
                "respuesta": resultado["respuesta"],
                "agents_trace": resultado.get("agents_trace", {}),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
