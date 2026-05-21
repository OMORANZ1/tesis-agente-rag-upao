from typing import TypedDict


class TutorState(TypedDict, total=False):
    student_message: str
    history: list[dict[str, str]]
    route: str
    route_reason: str
    topic: str
    difficulty_type: str
    emotion: str
    bloqueo: bool
    student_progress: str
    attempt_count: int
    has_code: bool
    activate_motivator: bool
    activate_technical: bool
    activate_exercise_generator: bool
    diagnostic_summary: str
    motivational_message: str
    technical_analysis: str
    generated_exercise: str
    rag_context: str
    final_response: str
    agents_used: list[str]
    agents_trace: dict[str, str]
    socratic_response_type: str
    preguntas_hechas: list[str]
    preguntas_nuevas: list[str]
