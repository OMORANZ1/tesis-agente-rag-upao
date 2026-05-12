from typing import Literal, TypedDict


RouteOption = Literal[
    "motivador",
    "diagnosticador",
    "socratico",
    "fuera_silabo",
]


class TutorState(TypedDict, total=False):
    student_message: str
    history_text: str
    route: RouteOption
    topic: str
    difficulty_type: str
    emotion: str
    attempt_count: int
    diagnostic_summary: str
    motivational_message: str
    rag_context: str
    final_response: str
