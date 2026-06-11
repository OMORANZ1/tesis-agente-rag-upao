from queue import Queue
from typing import Any, TypedDict


class TutorState(TypedDict, total=False):
    student_message: str
    modo_aprendizaje: str
    allowed_agents: dict[str, bool]
    agentes_seleccionados: list[str]
    history: list[dict[str, str]]
    event_queue: Queue
    route: str
    route_reason: str
    topic: str
    difficulty_type: str
    emotion: str
    bloqueo: bool
    student_progress: str
    attempt_count: int
    has_code: bool
    out_of_syllabus: bool
    activate_motivator: bool
    activate_technical: bool
    activate_exercise_generator: bool
    orchestrator_decision: dict[str, str]
    diagnostic_summary: str
    motivational_message: dict[str, str]
    technical_analysis: dict[str, str]
    generated_exercise: dict[str, str]
    critic_of_motivator: str
    critic_of_exercise: str
    corrected_exercise: dict[str, str]
    rag_context: str
    final_response: str
    quality_feedback: str
    quality_approved: bool
    quality_regen_count: int
    student_answer_correct: bool
    topic_progress: dict[str, int]
    debate_events: list[dict[str, Any]]
    ronda_actual: int
    agents_used: list[str]
    agents_trace: dict[str, str]
    agents_contributions: dict[str, str]
    agents_debate: list[dict[str, str]]
    socratic_response_type: str
    preguntas_hechas: list[str]
    preguntas_nuevas: list[str]
