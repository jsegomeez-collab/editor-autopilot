"""Exportación final (sección 6.7).

- Vídeo: el de componer.py ya cumple la especificación (H.264 High, 1080x1920, 25/30 fps, yuv420p,
  CRF 18, BT.709 etiquetado), así que se copia sin recodificar. Audio: la mezcla en AAC 48 kHz
  192 kbps. `-movflags +faststart`.
- portada.jpg: frame del gancho con la cartela ya visible.
- transcripcion.txt: texto limpio de lo que queda en el vídeo (para escribir el copy del post).
- Nombre: <AAAAMMDD>_<perfil>_<slug-del-gancho>.mp4
- Metadatos limpios: sin datos del dispositivo, GPS ni fecha de grabación (privacidad). No se añaden
  metadatos falsos de ningún tipo.

Uso:
  python pipeline/exportar.py --video compuesto.mp4 --audio mezcla.wav --edl edl.json \
      --transcripcion corr.json --graficos graficos.json --perfil perfiles/jose -o <trabajo>/salida
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from planificar_layout import palabras_en_salida  # noqa: E402

T_PORTADA = 0.8        # el barrido del gancho termina antes de 0,8 s
PAUSA_PARRAFO = 0.8


def slug(texto: str, max_palabras: int = 6) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    palabras = re.findall(r"[a-z0-9]+", t)[:max_palabras]
    return "-".join(palabras) or "video"


def texto_limpio(edl: dict, transcripcion: dict) -> str:
    ws = palabras_en_salida(edl, transcripcion)
    parrafos, actual = [], []
    for a, b in zip(ws, ws[1:] + [None]):
        actual.append(a["text"])
        if b is None or (b["o_start"] - a["o_end"] > PAUSA_PARRAFO and re.search(r"[.?!]»?$", a["text"])):
            parrafos.append(" ".join(actual))
            actual = []
    return "\n\n".join(parrafos) + "\n"


def exportar(video: Path, audio: Path, edl: dict, transcripcion: dict, graficos: list[dict], perfil: str,
             destino: Path, sufijo: str = "", nombre_base: str | None = None) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    gancho = next((g for g in graficos if g["plantilla"] == "gancho"), None)
    titulo = gancho["datos"]["titular"] if gancho else texto_limpio(edl, transcripcion).split(".")[0]
    nombre = f"{nombre_base or time.strftime('%Y%m%d') + '_' + perfil + '_' + slug(titulo)}{sufijo}"
    final = destino / f"{nombre}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    # Metadatos limpios: nada del dispositivo, ubicación ni fecha de grabación.
                    "-map_metadata", "-1", "-map_chapters", "-1",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                    "-movflags", "+faststart", str(final)], check=True)
    t_portada = min(T_PORTADA, gancho["duracion"] - 0.05) if gancho else 0.5
    portada = destino / "portada.jpg"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t_portada:.3f}", "-i", str(final),
                    "-frames:v", "1", "-q:v", "2", str(portada)], check=True)
    transcripcion_txt = destino / "transcripcion.txt"
    transcripcion_txt.write_text(texto_limpio(edl, transcripcion), encoding="utf-8")
    return {"final": str(final), "portada": str(portada), "transcripcion": str(transcripcion_txt)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--edl", type=Path, required=True)
    ap.add_argument("--transcripcion", type=Path, required=True)
    ap.add_argument("--graficos", type=Path)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("-o", "--destino", type=Path, required=True)
    ap.add_argument("--sufijo", default="", help="p. ej. _V2 en las variantes")
    ap.add_argument("--nombre-base", help="nombre común de todas las versiones de un vídeo (sin sufijo)")
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    graficos = leer(args.graficos)["graficos"] if args.graficos else []
    r = exportar(args.video, args.audio, leer(args.edl), leer(args.transcripcion), graficos,
                 args.perfil.name, args.destino, args.sufijo, args.nombre_base)
    (args.destino / "exportacion.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(r["final"])


if __name__ == "__main__":
    main()
