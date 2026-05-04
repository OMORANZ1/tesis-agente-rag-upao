from flask import Flask, render_template, request, jsonify
from agent import crear_agente, reiniciar_historial
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

agente = None

def obtener_agente():
    global agente
    if agente is None:
        agente = crear_agente()
    return agente

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        pregunta = data.get('mensaje', '').strip()
        if not pregunta:
            return jsonify({'error': 'Mensaje vacío'}), 400
        agente = obtener_agente()
        respuesta = agente(pregunta)
        return jsonify({'respuesta': respuesta})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reiniciar', methods=['POST'])
def reiniciar():
    global agente
    agente = None
    reiniciar_historial()
    return jsonify({'mensaje': 'Sesión reiniciada correctamente'})

if __name__ == '__main__':
    print("Iniciando sistema de tutoría socrática...")
    print("Abre tu navegador en: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)