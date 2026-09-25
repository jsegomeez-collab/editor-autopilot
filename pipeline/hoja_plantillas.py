"""Hoja de contactos de la biblioteca de plantillas (checkpoint de diseño 6.4).

Toma el frame clave de cada preview (0,5 s antes del final: todo ya ha aterrizado) y lo
coloca en contexto sobre un vídeo real ya maquetado: los paneles encima de un frame split
y las plantillas a pantalla completa (cta) sobre un frame full. Mosaico 5x2.

Uso:
  python pipeline/hoja_plantillas.py --video tests/revisiones/fase3_layout.mp4 --t-split 19.5 --t-full 50.2 \
      -o plantillas/_hoja_contactos.png
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / "plantillas"
ORDEN = ["gancho", "cifra", "lista", "comparativa", "pasos", "pregunta", "palabra_clave", "alerta", "grafico", "cta"]
FUENTE = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def duracion(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(p)], capture_output=True, text=True, check=True).stdout)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--t-split", type=float, required=True)
    ap.add_argument("--t-full", type=float, required=True)
    ap.add_argument("-o", "--salida", type=Path, default=PLANTILLAS / "_hoja_contactos.png")
    args = ap.parse_args()

    entradas, filtros, celdas = [], [], []
    for nombre in ORDEN:
        previews = sorted((PLANTILLAS / nombre).glob("preview.*"))
        if not previews:
            print(f"⚠️ {nombre}: sin preview, se omite")
            continue
        prev = previews[0]
        schema = json.loads((PLANTILLAS / nombre / "schema.json").read_text(encoding="utf-8"))
        pantalla = schema.get("formato") == "pantalla"
        t_fondo = args.t_full if pantalla else args.t_split
        k = len(celdas)
        entradas += ["-ss", f"{t_fondo}", "-i", str(args.video)]
        if prev.suffix == ".webm":
            entradas += ["-c:v", "libvpx-vp9"]  # para conservar el alfa
        entradas += ["-sseof", "-0.5", "-i", str(prev)]
        a, b = 2 * k, 2 * k + 1
        filtros.append(
            f"[{a}:v]trim=end_frame=1[f{k}];[{b}:v]trim=end_frame=1[p{k}];"
            f"[f{k}][p{k}]overlay=0:0,drawtext=fontfile='{FUENTE}':text='{nombre}':x=30:y=30:fontsize=64:"
            f"fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=14,scale=432:768[c{k}]")
        celdas.append(f"[c{k}]")
    n = len(celdas)
    columnas = min(5, n)
    filas = (n + columnas - 1) // columnas
    posiciones = "|".join(f"{(i % columnas) * 432}_{(i // columnas) * 768}" for i in range(n))
    if n == 1:
        filtros.append(f"{celdas[0]}null[out]")  # xstack necesita ≥ 2 entradas
    else:
        filtros.append("".join(celdas) + f"xstack=inputs={n}:layout={posiciones}:fill=black[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros),
                    "-map", "[out]", "-frames:v", "1", str(args.salida)], check=True)
    print(f"{args.salida} ({n} plantillas, {columnas}x{filas})")


if __name__ == "__main__":
    main()
