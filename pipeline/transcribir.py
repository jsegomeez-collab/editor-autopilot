"""Transcribe la copia normalizada con el helper de video-use, con caché global.

La caché de video-use vive en <edit>/transcripts/<stem>.json, es decir, es por
trabajo. Aquí se añade una caché global indexada por el hash del contenido
(el stem src_<sha1-12> de preparar_fuente.py): si el mismo vídeo se reprocesa en
otro trabajo, no se vuelve a transcribir.

Uso:
  python pipeline/transcribir.py <src_xxx.mp4> --edit <trabajo>/edit [--cache DIR]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_USE = Path.home() / "Developer" / "video-use"
PYTHON_VIDEO_USE = VIDEO_USE / ".venv" / "bin" / "python"
CACHE_POR_DEFECTO = Path.home() / "VideoAutopilot" / "cache_transcripciones"


def transcribir(video: Path, edit: Path, cache: Path) -> Path:
    destino = edit / "transcripts" / f"{video.stem}.json"
    en_cache = cache / f"{video.stem}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if en_cache.exists() and not destino.exists():
        shutil.copy2(en_cache, destino)  # video-use lo verá como "cached"
    subprocess.run(
        [str(PYTHON_VIDEO_USE), str(VIDEO_USE / "helpers" / "transcribe.py"), str(video),
         "--edit-dir", str(edit), "--language", "es", "--num-speakers", "1"],
        check=True,
    )
    cache.mkdir(parents=True, exist_ok=True)
    if not en_cache.exists():
        shutil.copy2(destino, en_cache)
    return destino


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--edit", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=CACHE_POR_DEFECTO)
    args = ap.parse_args()
    if not args.video.stem.startswith("src_"):
        sys.exit("❌ transcribe solo copias normalizadas (src_<hash>.mp4) para que la caché sea fiable")
    print(transcribir(args.video, args.edit, args.cache))


if __name__ == "__main__":
    main()
