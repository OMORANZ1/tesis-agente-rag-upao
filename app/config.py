from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
SILABO_PATH = BASE_DIR / "docs" / "silabo.pdf"
CHROMA_PATH = BASE_DIR / "chroma_db"
PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"

load_dotenv(dotenv_path=BASE_DIR / ".env")

ALLOWED_TOPICS = (
    "pensamiento algoritmico, variables, constantes, tipos de datos, "
    "operadores, expresiones logicas, estructuras secuenciales, "
    "condicionales if/else, bucles for/while, contadores, acumuladores, "
    "pseudocodigo conceptual, diagramas de flujo y prueba de escritorio"
)
