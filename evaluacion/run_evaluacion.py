#!/usr/bin/env python
"""
Script principal de evaluación - Objetivo Específico 1
Fidelidad RAG del Sistema de Agentes Inteligentes - UPAO

Uso: python evaluacion/run_evaluacion.py

# PASO 1: Asegúrate de tener el .env con GROQ_API_KEY y MISTRAL_API_KEY
# PASO 2: Asegúrate de que chroma_db/ existe (ejecuta la app primero)
# PASO 3: Instala dependencias opcionales: pip install ragas datasets
# PASO 4: Ejecuta: python evaluacion/run_evaluacion.py
# PASO 5: Abre evaluacion/resultados/reporte_oe1.html para ver evidencias
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluacion.reporte_resultados import generar_reporte_consola, generar_reporte_html
from evaluacion.test_faithfulness import ejecutar_evaluacion, guardar_resultados


def main():
    print("\nIniciando evaluacion de Fidelidad RAG...\n")

    try:
        resumen = ejecutar_evaluacion()
    except FileNotFoundError as e:
        print(f"\n{e}")
        sys.exit(1)
    except EnvironmentError as e:
        print(f"\n{e}")
        sys.exit(1)

    archivo_json = guardar_resultados(resumen)
    generar_reporte_consola(resumen)
    archivo_html = generar_reporte_html(resumen)

    print(f"\n{'=' * 60}")
    print("EVALUACION COMPLETADA")
    print(f"{'=' * 60}")
    print(f"Faithfulness promedio: {resumen['faithfulness_promedio']:.2%}")
    print(
        f"Preguntas aprobadas: "
        f"{resumen['preguntas_aprobadas']}/{resumen['total_preguntas']}"
    )

    if resumen["hipotesis_verificada"]:
        print("\nHIPOTESIS OE1 VERIFICADA")
        print(f"   mu = {resumen['faithfulness_promedio']:.2%} > 0.80 (umbral)")
    else:
        print("\nHIPOTESIS OE1 NO VERIFICADA")
        print(f"   mu = {resumen['faithfulness_promedio']:.2%} <= 0.80 (umbral)")

    print("\nEvidencias guardadas:")
    print(f"   JSON: {archivo_json}")
    print(f"   HTML: {archivo_html}")
    print("\nAbre el reporte HTML en tu navegador para la evidencia visual.")


if __name__ == "__main__":
    main()
