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

OUT_OF_SYLLABUS_PATTERNS = (
    r"\bmedicina\b",
    r"\bm[eé]dic[ao]s?\b",
    r"\banatom[ií]a\b",
    r"\bfisiolog[ií]a\b",
    r"\bfarmacolog[ií]a\b",
    r"\bcirug[ií]a\b",
    r"\bderecho\b",
    r"\bcontabilidad\b",
    r"\bmarketing\b",
    r"\bfinanzas\b",
    r"\bhistoria\b",
    r"\bbiolog[ií]a\b",
    r"\bqu[ií]mica\b",
    r"\bf[ií]sica\s+(?!b[aá]sica\b)",
    r"\bred(es)?\s+neuronal(es)?\b",
    r"\binteligencia\s+artificial\b",
    r"\bmachine\s+learning\b",
    r"\bdeep\s+learning\b",
    r"\baprendizaje\s+automatico\b",
    r"\baprendizaje\s+automático\b",
    r"\bcomputaci[oó]n\s+cu[aá]ntica\b",
    r"\bqu[aá]ntic[ao]s?\b",
    r"\bbase(s)?\s+de\s+datos\b",
    r"\bdesarrollo\s+web\b",
    r"\bhtml\b",
    r"\bcss\b",
    r"\bjavascript\b",
    r"\breact\b",
    r"\bciberseguridad\b",
    r"\bredes\s+inform[aá]ticas\b",
)

SYLLABUS_PATTERNS = (
    r"\bvariable(s)?\b",
    r"\btipo(s)?\s+de\s+dato(s)?\b",
    r"\bdato(s)?\b",
    r"\bconstante(s)?\b",
    r"\boperador(es)?\b",
    r"\baritm[eé]tic[ao]s?\b",
    r"\brelacional(es)?\b",
    r"\bl[oó]gic[ao]s?\b",
    r"\bexpresi[oó]n(es)?\b",
    r"\bsecuencial(es)?\b",
    r"\bestructura(s)?\s+secuencial(es)?\b",
    r"\bcondicional(es)?\b",
    r"\bif\b",
    r"\belse\b",
    r"\bsi\b",
    r"\bentonces\b",
    r"\bbucle(s)?\b",
    r"\bciclo(s)?\b",
    r"\bfor\b",
    r"\bwhile\b",
    r"\bpara\b",
    r"\bmientras\b",
    r"\bcontador(es)?\b",
    r"\bacumulador(es)?\b",
    r"\bdescomposici[oó]n\b",
    r"\bpseudoc[oó]digo\b",
    r"\bdiagrama(s)?\s+de\s+flujo\b",
    r"\balgoritm(ia|o|os|ico|ica|icos|icas)\b",
    r"\bprueba\s+de\s+escritorio\b",
)


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


def detectar_fuera_silabo(mensaje: str) -> bool:
    texto = (mensaje or "").lower()
    return any(
        re.search(patron, texto, re.IGNORECASE)
        for patron in OUT_OF_SYLLABUS_PATTERNS
    )


def detectar_tema_silabo(mensaje: str) -> bool:
    texto = (mensaje or "").lower()
    if detectar_codigo(texto):
        return True
    return any(
        re.search(patron, texto, re.IGNORECASE)
        for patron in SYLLABUS_PATTERNS
    )


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
