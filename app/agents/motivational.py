try:
    from ..state import TutorState
except ImportError:
    from state import TutorState


def agente_motivador(state: TutorState, llm) -> TutorState:
    prompt = f"""
Eres el Agente Motivador de un tutor universitario.
Responde con una frase breve de apoyo para un estudiante de primer ciclo.
No expliques todavia el contenido academico. No uses exageraciones.

Mensaje del estudiante:
{state["student_message"]}
"""
    response = llm.invoke(prompt)
    return {"motivational_message": response.content.strip()}
