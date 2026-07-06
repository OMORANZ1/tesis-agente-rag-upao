# PASO 1: Asegúrate de tener el .env con GROQ_API_KEY y MISTRAL_API_KEY
# PASO 2: Asegúrate de que chroma_db/ existe (ejecuta la app primero)
# PASO 3: Instala dependencias opcionales: pip install ragas datasets
# PASO 4: Ejecuta: python evaluacion/run_evaluacion.py
# PASO 5: Abre evaluacion/resultados/reporte_oe1.html para ver evidencias

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_mistralai import MistralAIEmbeddings

from evaluacion.preguntas_silabo import PREGUNTAS_SILABO

PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

CHROMA_ERROR_MSG = (
    "Error: Base de conocimiento RAG no encontrada. "
    "Ejecuta primero la aplicación principal para generar el índice."
)


def validar_prerequisitos():
    """Verifica que existan chroma_db y las API keys necesarias."""
    if not CHROMA_PATH.exists() or not any(CHROMA_PATH.iterdir()):
        raise FileNotFoundError(CHROMA_ERROR_MSG)
    if not GROQ_API_KEY:
        raise EnvironmentError("Error: GROQ_API_KEY no configurada en .env")
    if not MISTRAL_API_KEY:
        raise EnvironmentError("Error: MISTRAL_API_KEY no configurada en .env")


def inicializar_rag():
    """Inicializa el retriever RAG con ChromaDB."""
    validar_prerequisitos()
    embeddings = MistralAIEmbeddings(
        api_key=MISTRAL_API_KEY,
        model="mistral-embed",
    )
    vectorstore = Chroma(
        persist_directory=str(CHROMA_PATH),
        embedding_function=embeddings,
    )
    return vectorstore.as_retriever(search_kwargs={"k": 3})


def inicializar_llm():
    """Inicializa el LLM de Groq."""
    validar_prerequisitos()
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model="llama-3.1-8b-instant",
        temperature=0.1,
    )


def obtener_respuesta_con_contexto(pregunta, retriever, llm):
    """Obtiene respuesta del sistema RAG y los fragmentos recuperados."""
    docs = retriever.invoke(pregunta)
    contextos = [doc.page_content for doc in docs]
    contexto_completo = "\n\n".join(contextos)

    prompt = f"""Eres un asistente especializado en el curso de
    Algoritmia y Programación de la UPAO. Responde basándote
    ÚNICAMENTE en el siguiente contexto del sílabo. Si la
    información no está en el contexto, dilo explícitamente.

    CONTEXTO DEL SÍLABO:
    {contexto_completo}

    PREGUNTA: {pregunta}

    RESPUESTA (basada solo en el contexto):"""

    respuesta = llm.invoke(prompt)
    return respuesta.content, contextos


def calcular_faithfulness_manual(respuesta, contextos, keywords_esperadas):
    """
    Calcula faithfulness verificando:
    1. Keywords del sílabo presentes en la respuesta
    2. Si la respuesta menciona el contexto recuperado
    3. Ausencia de información inventada (no está en contextos)
    """
    respuesta_lower = respuesta.lower()
    contexto_combinado = " ".join(contextos).lower()

    keywords_encontradas = sum(
        1 for kw in keywords_esperadas if kw.lower() in respuesta_lower
    )
    score_keywords = (
        keywords_encontradas / len(keywords_esperadas) if keywords_esperadas else 0
    )

    palabras_respuesta = set(respuesta_lower.split())
    palabras_contexto = set(contexto_combinado.split())
    palabras_compartidas = palabras_respuesta.intersection(palabras_contexto)
    score_contexto = min(
        len(palabras_compartidas) / max(len(palabras_respuesta), 1), 1.0
    )

    no_encontrado = any(
        frase in respuesta_lower
        for frase in [
            "no está en el contexto",
            "no tengo información",
            "no se menciona",
            "no encuentro",
        ]
    )
    penalizacion = 0.3 if no_encontrado else 0

    faithfulness = (score_keywords * 0.5 + score_contexto * 0.5) - penalizacion
    return max(0, min(1, faithfulness))


def evaluar_con_ragas(questions, answers, contexts):
    """Intenta evaluar con RAGAS, retorna None si no está disponible."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, faithfulness

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        dataset = Dataset.from_dict(data)
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
        return result
    except ImportError:
        return None
    except Exception as e:
        print(f"RAGAS no disponible: {e}")
        return None


def ejecutar_evaluacion():
    """Ejecuta la evaluación completa de Faithfulness."""
    print("=" * 60)
    print("EVALUACIÓN DE FIDELIDAD RAG - OBJETIVO ESPECÍFICO 1")
    print("Sistema de Agentes Inteligentes con RAG - UPAO")
    print(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    retriever = inicializar_rag()
    llm = inicializar_llm()

    resultados = []
    questions = []
    answers = []
    contexts_list = []

    print(f"\nEvaluando {len(PREGUNTAS_SILABO)} preguntas del sílabo...\n")

    for item in PREGUNTAS_SILABO:
        print(
            f"[{item['id']:02d}/{len(PREGUNTAS_SILABO)}] "
            f"{item['tema']}: {item['pregunta'][:50]}..."
        )

        respuesta, contextos = obtener_respuesta_con_contexto(
            item["pregunta"], retriever, llm
        )

        faithfulness_score = calcular_faithfulness_manual(
            respuesta, contextos, item["respuesta_esperada_keywords"]
        )

        resultado = {
            "id": item["id"],
            "tema": item["tema"],
            "pregunta": item["pregunta"],
            "respuesta": respuesta,
            "contextos_recuperados": contextos,
            "keywords_esperadas": item["respuesta_esperada_keywords"],
            "faithfulness_score": round(faithfulness_score, 4),
            "aprobado": faithfulness_score > 0.80,
        }

        resultados.append(resultado)
        questions.append(item["pregunta"])
        answers.append(respuesta)
        contexts_list.append(contextos)

        estado = "APROBADO" if faithfulness_score > 0.80 else "BAJO"
        simbolo = "+" if faithfulness_score > 0.80 else "-"
        print(f"    [{simbolo}] Faithfulness: {faithfulness_score:.2%} {estado}")

    print("\nIntentando evaluación con RAGAS...")
    ragas_result = evaluar_con_ragas(questions, answers, contexts_list)

    promedio_faithfulness = sum(r["faithfulness_score"] for r in resultados) / len(
        resultados
    )
    aprobados = sum(1 for r in resultados if r["aprobado"])

    resumen = {
        "fecha_evaluacion": datetime.now().isoformat(),
        "total_preguntas": len(resultados),
        "preguntas_aprobadas": aprobados,
        "preguntas_reprobadas": len(resultados) - aprobados,
        "faithfulness_promedio": round(promedio_faithfulness, 4),
        "hipotesis_verificada": promedio_faithfulness > 0.80,
        "umbral_hipotesis": 0.80,
        "ragas_disponible": ragas_result is not None,
        "ragas_resultado": str(ragas_result) if ragas_result else "No disponible",
        "resultados_detalle": resultados,
    }

    return resumen


def guardar_resultados(resumen):
    """Guarda los resultados en JSON para evidencia."""
    output_dir = Path(__file__).parent / "resultados"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"faithfulness_rag_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print(f"\nResultados guardados en: {output_file}")
    return output_file
