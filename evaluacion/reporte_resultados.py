"""Generación de reportes de evaluación OE1: consola y HTML."""

from datetime import datetime
from html import escape
from pathlib import Path


def _formatear_fecha(iso_fecha: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_fecha)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return iso_fecha


def _resumir_pregunta(pregunta: str, max_len: int = 55) -> str:
    if len(pregunta) <= max_len:
        return pregunta
    return pregunta[: max_len - 3] + "..."


def _generar_conclusion(resumen: dict) -> str:
    promedio_pct = resumen["faithfulness_promedio"] * 100
    promedio_fmt = f"{resumen['faithfulness_promedio']:.2%}"

    if resumen["hipotesis_verificada"]:
        return (
            f"HIPOTESIS ESPECIFICA 1 VERIFICADA: El componente RAG "
            f"garantiza un indice de Faithfulness de {promedio_pct:.1f}% "
            f"(mu = {promedio_fmt}), significativamente superior al umbral "
            f"del 80% establecido."
        )
    return (
        f"HIPOTESIS ESPECIFICA 1 NO VERIFICADA: El indice de Faithfulness "
        f"obtenido ({promedio_pct:.1f}%) no supera el umbral del 80%."
    )


def generar_reporte_consola(resumen: dict) -> None:
    """Imprime reporte formateado en consola."""
    fecha = _formatear_fecha(resumen["fecha_evaluacion"])
    promedio = resumen["faithfulness_promedio"]
    conclusion = _generar_conclusion(resumen)

    print("\n" + "=" * 80)
    print("EVALUACION DE FIDELIDAD RAG - OE1")
    print("=" * 80)
    print(f"Fecha y hora: {fecha}")
    print("Sistema evaluado: Agentes Inteligentes con RAG - UPAO")
    print("-" * 80)
    print(f"{'ID':<4} {'Tema':<28} {'Pregunta':<40} {'Faith.':<10} {'Estado'}")
    print("-" * 80)

    for r in resumen["resultados_detalle"]:
        pregunta_res = _resumir_pregunta(r["pregunta"], 38)
        estado = "APROBADO" if r["aprobado"] else "REPROBADO"
        print(
            f"{r['id']:<4} {r['tema'][:26]:<28} {pregunta_res:<40} "
            f"{r['faithfulness_score']:.2%}    {estado}"
        )

    print("-" * 80)
    print("\nRESUMEN ESTADISTICO")
    print(f"  Total preguntas evaluadas : {resumen['total_preguntas']}")
    print(f"  Promedio Faithfulness     : {promedio:.2%}")
    print(f"  Preguntas aprobadas (>80%): {resumen['preguntas_aprobadas']}")
    print(f"  Preguntas reprobadas      : {resumen['preguntas_reprobadas']}")
    print(
        f"  Hipotesis OE1             : "
        f"{'VERIFICADA' if resumen['hipotesis_verificada'] else 'NO VERIFICADA'}"
    )
    print(f"  RAGAS disponible          : {'Si' if resumen['ragas_disponible'] else 'No'}")
    print("\nCONCLUSION")
    simbolo = "+" if resumen["hipotesis_verificada"] else "-"
    print(f"  [{simbolo}] {conclusion}")
    print("=" * 80)


def generar_reporte_html(resumen: dict) -> Path:
    """Genera reporte HTML con tabla de resultados y resumen estadistico."""
    output_dir = Path(__file__).parent / "resultados"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "reporte_oe1.html"

    fecha = _formatear_fecha(resumen["fecha_evaluacion"])
    promedio = resumen["faithfulness_promedio"]
    promedio_pct = promedio * 100
    conclusion = _generar_conclusion(resumen)
    hipotesis_ok = resumen["hipotesis_verificada"]

    filas = []
    for r in resumen["resultados_detalle"]:
        clase_fila = "aprobado" if r["aprobado"] else "reprobado"
        estado = "Aprobado" if r["aprobado"] else "Reprobado"
        filas.append(
            f"""<tr class="{clase_fila}">
                <td>{r['id']}</td>
                <td>{escape(r['tema'])}</td>
                <td>{escape(_resumir_pregunta(r['pregunta'], 70))}</td>
                <td>{r['faithfulness_score']:.2%}</td>
                <td>{estado}</td>
            </tr>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluacion de Fidelidad RAG - OE1</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f1f5f9;
            color: #1e293b;
            padding: 2rem;
            line-height: 1.5;
        }}
        .container {{ max-width: 1100px; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #1e40af, #3b82f6);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }}
        header h1 {{ font-size: 1.75rem; margin-bottom: 0.5rem; }}
        header p {{ opacity: 0.9; font-size: 0.95rem; }}
        .resumen {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .card .valor {{
            font-size: 2rem;
            font-weight: 700;
            color: #1e40af;
        }}
        .card .etiqueta {{
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 0.25rem;
        }}
        .card.destacado {{
            border: 2px solid {'#16a34a' if hipotesis_ok else '#dc2626'};
        }}
        .card.destacado .valor {{
            color: {'#16a34a' if hipotesis_ok else '#dc2626'};
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 1.5rem;
        }}
        th {{
            background: #334155;
            color: white;
            padding: 0.75rem 1rem;
            text-align: left;
            font-size: 0.85rem;
        }}
        td {{
            padding: 0.65rem 1rem;
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.9rem;
        }}
        tr.aprobado td:last-child {{ color: #16a34a; font-weight: 600; }}
        tr.reprobado td:last-child {{ color: #dc2626; font-weight: 600; }}
        tr.aprobado {{ background: #f0fdf4; }}
        tr.reprobado {{ background: #fef2f2; }}
        .conclusion {{
            background: {'#f0fdf4' if hipotesis_ok else '#fef2f2'};
            border-left: 4px solid {'#16a34a' if hipotesis_ok else '#dc2626'};
            padding: 1.25rem 1.5rem;
            border-radius: 0 10px 10px 0;
            font-size: 1rem;
        }}
        .conclusion strong {{ display: block; margin-bottom: 0.5rem; }}
        footer {{
            margin-top: 2rem;
            text-align: center;
            color: #94a3b8;
            font-size: 0.8rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Evaluacion de Fidelidad RAG - OE1</h1>
            <p>Sistema evaluado: Agentes Inteligentes con RAG - UPAO</p>
            <p>Fecha y hora de evaluacion: {fecha}</p>
        </header>

        <div class="resumen">
            <div class="card destacado">
                <div class="valor">{promedio_pct:.1f}%</div>
                <div class="etiqueta">Faithfulness Promedio</div>
            </div>
            <div class="card">
                <div class="valor">{resumen['total_preguntas']}</div>
                <div class="etiqueta">Preguntas Evaluadas</div>
            </div>
            <div class="card">
                <div class="valor">{resumen['preguntas_aprobadas']}</div>
                <div class="etiqueta">Aprobadas (&gt; 80%)</div>
            </div>
            <div class="card">
                <div class="valor">{resumen['preguntas_reprobadas']}</div>
                <div class="etiqueta">Reprobadas</div>
            </div>
            <div class="card">
                <div class="valor">{'Si' if resumen['ragas_disponible'] else 'No'}</div>
                <div class="etiqueta">RAGAS Disponible</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Tema</th>
                    <th>Pregunta</th>
                    <th>Faithfulness</th>
                    <th>Estado</th>
                </tr>
            </thead>
            <tbody>
                {''.join(filas)}
            </tbody>
        </table>

        <div class="conclusion">
            <strong>{'Hipotesis OE1 VERIFICADA' if hipotesis_ok else 'Hipotesis OE1 NO VERIFICADA'}</strong>
            {escape(conclusion)}
        </div>

        <footer>
            Generado automaticamente por el modulo evaluacion/ - tesis-agente-rag-upao
        </footer>
    </div>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Reporte HTML generado en: {output_file}")
    return output_file
