import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

try:
    from ..config import BASE_DIR  # noqa: F401 — asegura load_dotenv del proyecto
except ImportError:
    from config import BASE_DIR  # noqa: F401


_GEMINI_ENV_VARS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
)

# Gemini 1.5 fue retirado (404). Modelos actuales recomendados por Google:
_DEFAULT_GEMINI_MODELS = {
    "especialista": "gemini-2.5-flash-lite",
    "pedagogo": "gemini-2.5-flash",
}

_BASE_LABELS = {
    "orquestador": "llama-3.1-8b-instant (Groq)",
    "motivador": "llama-3.3-70b-versatile (Groq)",
    "generador": "llama-3.3-70b-versatile (Groq)",
    "evaluador": "llama-3.1-8b-instant (Groq)",
}

_GROQ_FALLBACK_LABELS = {
    "especialista": "llama-3.1-8b-instant (Groq)",
    "pedagogo": "llama-3.3-70b-versatile (Groq)",
}


def obtener_gemini_api_key() -> str:
    for nombre in _GEMINI_ENV_VARS:
        valor = (os.getenv(nombre) or "").strip().strip('"').strip("'")
        if valor:
            return valor
    return ""


def gemini_disponible() -> bool:
    return bool(obtener_gemini_api_key())


def _modelo_gemini(agent_name: str) -> str:
    agent_name = (agent_name or "").lower()
    env_key = f"GEMINI_MODEL_{agent_name.upper()}"
    personalizado = (os.getenv(env_key) or "").strip()
    if personalizado:
        return personalizado
    return _DEFAULT_GEMINI_MODELS.get(agent_name, "gemini-2.5-flash")


def obtener_etiqueta_modelo(agent_name: str) -> str:
    agent_name = (agent_name or "").lower()
    if agent_name in _DEFAULT_GEMINI_MODELS and gemini_disponible():
        return f"{_modelo_gemini(agent_name)} (Google)"
    if agent_name in _GROQ_FALLBACK_LABELS and not gemini_disponible():
        return _GROQ_FALLBACK_LABELS[agent_name]
    return _BASE_LABELS.get(agent_name, "sin modelo")


class _ModelLabels:
    def get(self, agent_name: str, default: str = "sin modelo") -> str:
        return obtener_etiqueta_modelo(agent_name) if agent_name else default

    def __getitem__(self, agent_name: str) -> str:
        return obtener_etiqueta_modelo(agent_name)


AGENT_MODEL_LABELS = _ModelLabels()


def _groq_llm(model: str, temperature: float = 0.2, max_tokens: int = 550):
    return ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _gemini_llm(model: str, temperature: float = 0.2, max_tokens: int = 700):
    api_key = obtener_gemini_api_key()
    if not api_key:
        nombres = ", ".join(_GEMINI_ENV_VARS)
        raise ValueError(
            f"Falta la API key de Gemini en .env. Usa una de estas variables: {nombres}"
        )
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )


def get_llm_for_agent(agent_name: str):
    agent_name = (agent_name or "").lower()
    if agent_name == "orquestador":
        return _groq_llm("llama-3.1-8b-instant", temperature=0.1, max_tokens=450)
    if agent_name == "motivador":
        return _groq_llm("llama-3.3-70b-versatile", temperature=0.4, max_tokens=350)
    if agent_name == "especialista":
        if gemini_disponible():
            return _gemini_llm(
                _modelo_gemini("especialista"),
                temperature=0.1,
                max_tokens=500,
            )
        return _groq_llm("llama-3.1-8b-instant", temperature=0.1, max_tokens=500)
    if agent_name == "generador":
        return _groq_llm("llama-3.3-70b-versatile", temperature=0.3, max_tokens=650)
    if agent_name == "pedagogo":
        if gemini_disponible():
            return _gemini_llm(
                _modelo_gemini("pedagogo"),
                temperature=0.25,
                max_tokens=700,
            )
        return _groq_llm("llama-3.3-70b-versatile", temperature=0.25, max_tokens=700)
    if agent_name == "evaluador":
        return _groq_llm("llama-3.1-8b-instant", temperature=0.0, max_tokens=300)

    raise ValueError(f"Agente sin modelo configurado: {agent_name}")


def crear_llm(temperature: float = 0.2):
    return _groq_llm(
        "llama-3.1-8b-instant",
        temperature=temperature,
        max_tokens=450,
    )
