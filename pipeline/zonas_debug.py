"""Modo debug: dibuja las zonas seguras del perfil sobre fotogramas del vídeo.

Contorno rojo = límite de las zonas seguras (nada importante fuera de él). Línea cian = divisoria del split (y=960).
Con varios tiempos genera una hoja de contactos en fila.

Uso:
  python pipeline/zonas_debug.py <video> --perfil perfiles/jose -t 0 2.5 10 ... -o hoja.png [--layout layout.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402

W, H = 1080, 1920


def filtro_zonas(sup: int, inf: int, der: int) -> str:
    # Rectángulo del área útil (lo que queda fuera son las zonas seguras) + divisoria del split.
    return (f"drawbox=x=0:y={sup}:w={W - der}:h={H - sup - inf}:color=red@0.9:t=6,"
            f"drawbox=x=0:y=958:w={W}:h=4:color=cyan@0.8:t=fill")


def etiqueta(t: float, layout: dict | None) -> str:
    if not layout:
        return f"{t:.2f}s"
    for v in layout["ventanas"]:
        if v["inicio"] <= t < v["fin"]:
            return f"{t:.2f}s {v['tipo']}" + (" zoom" if v["zoom"] != 1 else "")
    return f"{t:.2f}s"


def hoja(video: Path, perfil_dir: Path, tiempos: list[float], salida: Path, layout: dict | None) -> Path:
    z = cargar(perfil_dir).zonas_seguras
    zonas = filtro_zonas(z.superior, z.inferior, z.derecha)
    fuente = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for k, t in enumerate(tiempos):
            f = Path(tmp) / f"f{k}.png"
            texto = etiqueta(t, layout).replace(":", "\\:")
            subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                "-vf", f"{zonas},drawtext=fontfile='{fuente}':text='{texto}':x=24:y=24:fontsize=56:"
                       f"fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=12,scale=540:960",
                str(f)], check=True)
            frames.append(f)
        entradas = [a for f in frames for a in ("-i", str(f))]
        subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas,
                        "-filter_complex", "".join(f"[{i}:v]" for i in range(len(frames))) +
                        f"hstack=inputs={len(frames)}", str(salida)], check=True)
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("-t", "--tiempos", type=float, nargs="+", required=True)
    ap.add_argument("--layout", type=Path)
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    layout = json.loads(args.layout.read_text()) if args.layout else None
    print(hoja(args.video, args.perfil, args.tiempos, args.salida, layout))


if __name__ == "__main__":
    main()
