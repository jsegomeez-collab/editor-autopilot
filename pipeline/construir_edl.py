"""Convierte la selección de palabras del LLM en un edl.json de video-use.

El LLM decide QUÉ se queda (tramos de índices de palabra, en orden). Este script
decide DÓNDE se corta exactamente, garantizando las reglas duras:
  - nunca se corta dentro de una palabra (los bordes se ajustan a palabras de Scribe);
  - padding según el ritmo (rapido: 40/60 ms, natural: 60/100 ms), dentro de 30–200 ms
    y sin invadir la palabra vecina;
  - dentro de un tramo se eliminan los silencios ≥ umbral (rapido: 300 ms, natural: 500 ms);
  - cada borde se alinea a la rejilla de fotogramas (sin entrar en la palabra vecina), para
    que cada segmento dure un número entero de fotogramas y audio y vídeo no se desfasen.

Entrada (seleccion.json):
  {"tramos": [{"desde": 0, "hasta": 14, "beat": "GANCHO", "motivo": "..."}, ...]}
  (índices sobre las palabras de tipo "word" de la transcripción, ambos incluidos)

Uso:
  python pipeline/construir_edl.py <transcripcion.json> <seleccion.json> --video <src.mp4> --ritmo rapido -o edl.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RITMOS = {
    "rapido": {"silencio": 0.30, "pad_antes": 0.040, "pad_despues": 0.060},
    "natural": {"silencio": 0.50, "pad_antes": 0.060, "pad_despues": 0.100},
}


def palabras(transcripcion: dict) -> list[dict]:
    return [w for w in transcripcion["words"] if w.get("type") == "word"]


def rangos_de_tramo(ws: list[dict], desde: int, hasta: int, ritmo: dict) -> list[tuple[int, int]]:
    """Parte un tramo de palabras en sub-tramos separados por silencios largos."""
    partes, inicio = [], desde
    for i in range(desde, hasta):
        if ws[i + 1]["start"] - ws[i]["end"] >= ritmo["silencio"]:
            partes.append((inicio, i))
            inicio = i + 1
    partes.append((inicio, hasta))
    return partes


def con_padding(ws: list[dict], i: int, j: int, ritmo: dict, duracion: float, fps: float) -> tuple[float, float]:
    """Bordes del rango [palabra i, palabra j] con padding, en fotogramas enteros, sin tocar palabras vecinas."""
    import math
    tope_ini = ws[i - 1]["end"] if i > 0 else 0.0
    tope_fin = ws[j + 1]["start"] if j + 1 < len(ws) else duracion
    ini = max(ws[i]["start"] - ritmo["pad_antes"], tope_ini)
    fin = min(ws[j]["end"] + ritmo["pad_despues"], tope_fin)
    # Alinear a fotogramas: el más cercano, y si invade la palabra vecina, hacia dentro.
    f_ini = round(ini * fps)
    if f_ini / fps < tope_ini:
        f_ini = math.ceil(ini * fps)
    f_fin = round(fin * fps)
    if f_fin / fps > tope_fin:
        f_fin = math.floor(fin * fps)
    f_fin = max(f_fin, f_ini + 1)
    return round(f_ini / fps, 4), round(f_fin / fps, 4)


def construir(transcripcion: dict, seleccion: dict, video: Path, ritmo_nombre: str, duracion: float,
              fps: float) -> dict:
    ws = palabras(transcripcion)
    ritmo = RITMOS[ritmo_nombre]
    fuente = video.stem
    ranges, ultimo_fin = [], -1
    for tramo in seleccion["tramos"]:
        desde, hasta = tramo["desde"], tramo["hasta"]
        if not 0 <= desde <= hasta < len(ws):
            raise ValueError(f"tramo fuera de rango: {tramo}")
        if desde <= ultimo_fin:
            raise ValueError(f"tramos solapados o reordenados (prohibido): {tramo}")
        ultimo_fin = hasta
        for i, j in rangos_de_tramo(ws, desde, hasta, ritmo):
            ini, fin = con_padding(ws, i, j, ritmo, duracion, fps)
            ranges.append({
                "source": fuente, "start": ini, "end": fin,
                "beat": tramo.get("beat", ""),
                "quote": " ".join(w["text"] for w in ws[i:j + 1]),
                "reason": tramo.get("motivo", ""),
                "palabras": [i, j],
            })
    total = round(sum(round((r["end"] - r["start"]) * fps) for r in ranges) / fps, 4)
    return {"version": 1, "sources": {fuente: str(video.resolve())}, "ranges": ranges,
            "ritmo": ritmo_nombre, "fps": fps, "total_duration_s": total}


def main() -> None:
    import subprocess
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripcion", type=Path)
    ap.add_argument("seleccion", type=Path)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--ritmo", choices=RITMOS, default="rapido")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    sonda = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate:format=duration",
         "-of", "json", str(args.video)], capture_output=True, text=True, check=True).stdout
    info = json.loads(sonda)
    duracion = float(info["format"]["duration"])
    num, den = info["streams"][0]["avg_frame_rate"].split("/")
    edl = construir(json.loads(args.transcripcion.read_text()), json.loads(args.seleccion.read_text()),
                    args.video, args.ritmo, duracion, float(num) / float(den))
    args.salida.write_text(json.dumps(edl, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"guardado: {args.salida} — {len(edl['ranges'])} rangos, {edl['total_duration_s']} s")


if __name__ == "__main__":
    main()
