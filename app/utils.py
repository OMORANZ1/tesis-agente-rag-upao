import json
import re


CODE_PATTERNS = [
    r"\b(def|class|import|return|print|elif|int|float|str|void|main)\b",
    r"\b(if|else|for|while)\s*(\(|:)",
    r"[{};]|:=|=>|<-",
    r"^\s*(#|//|/\*)",
    r"\b(pseudocodigo|pseudocódigo|algoritmo)\b.*\b(inicio|fin|mientras|repetir|si|entonces)\b",
    r"```",
    r"\bO\s*\(\s*n",
]

PSEUDOCODE_KEYWORDS = {
    "inicio",
    "fin",
    "mientras",
    "repetir",
    "si",
    "entonces",
    "hacer",
    "leer",
    "escribir",
    "para",
}


def extraer_json(texto: str, fallback: dict) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if not match:
            return fallback
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return fallback


def normalizar_tema(tema: str) -> str:
    tema = (tema or "tema_no_identificado").strip().lower()
    tema = re.sub(r"[^a-z0-9áéíóúñü\s_-]", "", tema)
    tema = re.sub(r"\s+", "_", tema)
    return tema or "tema_no_identificado"


def detectar_codigo(mensaje: str) -> bool:
    texto = (mensaje or "").strip()
    if not texto:
        return False
    for patron in CODE_PATTERNS:
        if re.search(patron, texto, re.IGNORECASE | re.MULTILINE):
            return True
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    pasos_enumerados = sum(1 for linea in lineas if re.match(r"^\d+\.", linea))
    if len(lineas) >= 2 and pasos_enumerados >= 2:
        return True
    palabras = set(re.findall(r"\b[a-záéíóúñü]+\b", texto.lower()))
    pseudocode_hits = palabras.intersection(PSEUDOCODE_KEYWORDS)
    tiene_operadores = bool(re.search(r"(==|!=|<=|>=|=|\+|-|\*|/|%)", texto))
    if len(pseudocode_hits) >= 2 and (len(lineas) >= 2 or tiene_operadores):
        return True
    return False


def formatear_historial(history: list[dict[str, str]] | None) -> str:
    if not history:
        return "Sin historial previo."
    lineas = []
    for turno in history:
        rol = turno.get("role", "desconocido")
        contenido = turno.get("content", "")
        etiqueta = "Estudiante" if rol == "student" else "Tutor"
        lineas.append(f"{etiqueta}: {contenido}")
    return "\n".join(lineas)
