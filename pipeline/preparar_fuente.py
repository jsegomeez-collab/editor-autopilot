"""Ingesta y normalización de un vídeo fuente (sección 6.1).

- Espera a que el archivo termine de copiarse (tamaño estable ≥ 5 s).
- Analiza con ffprobe: resolución, fps, VFR, HDR, rotación y audio.
- Crea una copia normalizada: CFR (30 fps, o 25 si la fuente es 25), HDR -> SDR
  BT.709 con tone mapping (zscale + tonemap), audio a 48 kHz, rotación aplicada,
  lado corto a 1080 px como máximo (decisión aprobada: no se conserva el 4K) y CRF 14.
- El original NUNCA se modifica. La copia se llama src_<sha1-12>.mp4, así el
  mismo contenido siempre produce el mismo nombre (y la caché de transcripción acierta).

Uso:
  python pipeline/preparar_fuente.py <video> --destino <trabajo>/fuente
Imprime la ruta de la copia normalizada y escribe ficha.json al lado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

TRANSFERENCIAS_HDR = {"arib-std-b67", "smpte2084"}
TONEMAP = (
    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
    "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
)
LADO_CORTO_MAX = 1080


def esperar_estable(ruta: Path, segundos: float = 5.0, intervalo: float = 1.0) -> None:
    """Bloquea hasta que el tamaño del archivo no cambie durante `segundos`."""
    ultimo, estable_desde = -1, time.monotonic()
    while True:
        tam = ruta.stat().st_size
        if tam != ultimo:
            ultimo, estable_desde = tam, time.monotonic()
        elif time.monotonic() - estable_desde >= segundos:
            return
        time.sleep(intervalo)


def sha1_corto(ruta: Path) -> str:
    h = hashlib.sha1()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()[:12]


def analizar(ruta: Path) -> dict:
    """Ficha técnica de la fuente a partir de ffprobe."""
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(ruta)],
        capture_output=True, text=True, check=True,
    ).stdout
    datos = json.loads(salida)
    video = next((s for s in datos["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in datos["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise ValueError("la fuente no tiene pista de vídeo")

    rotacion = 0
    for sd in video.get("side_data_list", []):
        if "rotation" in sd:
            rotacion = int(sd["rotation"])
    w, h = video["width"], video["height"]
    if abs(rotacion) % 180 == 90:
        w, h = h, w

    r = Fraction(video.get("r_frame_rate", "0/1"))
    avg = Fraction(video.get("avg_frame_rate", "0/1"))
    fps = float(avg or r)
    return {
        "archivo": str(ruta),
        "ancho": w,  # ya con la rotación aplicada
        "alto": h,
        "vertical": h >= w,
        "fps": round(fps, 3),
        # VFR: la tasa nominal y la media no coinciden (habitual en móviles).
        "vfr": bool(r and avg and abs(float(r) - float(avg)) > 0.01),
        "hdr": video.get("color_transfer") in TRANSFERENCIAS_HDR,
        "color_transfer": video.get("color_transfer"),
        "rotacion": rotacion,
        "audio": audio is not None,
        "audio_hz": int(audio["sample_rate"]) if audio else None,
        "duracion_s": float(datos["format"]["duration"]),
    }


def fps_objetivo(fps: float) -> int:
    return 25 if abs(fps - 25) < 0.5 else 30


def tamano_objetivo(ancho: int, alto: int) -> tuple[int, int]:
    """Reduce para que el lado corto sea ≤ 1080 (nunca amplía). Dimensiones pares."""
    corto = min(ancho, alto)
    escala = min(1.0, LADO_CORTO_MAX / corto)
    par = lambda x: int(round(x * escala / 2)) * 2  # noqa: E731
    return par(ancho), par(alto)


def normalizar(fuente: Path, destino: Path, ficha: dict) -> Path:
    salida = destino / f"src_{ficha['sha1']}.mp4"
    if salida.exists():
        return salida  # mismo contenido ya normalizado
    ancho, alto = tamano_objetivo(ficha["ancho"], ficha["alto"])
    filtros = [TONEMAP] if ficha["hdr"] else []
    filtros += [f"scale={ancho}:{alto}:flags=lanczos", f"fps={ficha['fps_salida']}", "format=yuv420p"]
    tmp = salida.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(fuente),  # autorotate (por defecto) aplica la rotación
        "-map", "0:v:0", "-map", "0:a:0",
        "-vf", ",".join(filtros),
        "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
        "-movflags", "+faststart", str(tmp),
    ]
    subprocess.run(cmd, check=True)
    tmp.rename(salida)
    return salida


def preparar(fuente: Path, destino: Path, esperar: bool = True) -> tuple[Path, dict]:
    if esperar:
        esperar_estable(fuente)
    ficha = analizar(fuente)
    if not ficha["audio"]:
        raise ValueError("la fuente no tiene audio: no se puede transcribir")
    ficha["sha1"] = sha1_corto(fuente)
    ficha["fps_salida"] = fps_objetivo(ficha["fps"])
    destino.mkdir(parents=True, exist_ok=True)
    normalizada = normalizar(fuente, destino, ficha)
    ficha["normalizada"] = str(normalizada)
    ficha["normalizada_ficha"] = analizar(normalizada)
    (destino / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalizada, ficha


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--destino", type=Path, required=True)
    ap.add_argument("--sin-espera", action="store_true", help="no esperar a que el tamaño sea estable")
    args = ap.parse_args()
    try:
        normalizada, ficha = preparar(args.video, args.destino, not args.sin_espera)
    except (ValueError, subprocess.CalledProcessError) as e:
        sys.exit(f"❌ {e}")
    n = ficha["normalizada_ficha"]
    print(f"{normalizada}")
    print(f"  fuente {ficha['ancho']}x{ficha['alto']} {ficha['fps']} fps vfr={ficha['vfr']} hdr={ficha['hdr']} "
          f"rot={ficha['rotacion']} -> {n['ancho']}x{n['alto']} {n['fps']} fps hdr={n['hdr']}", file=sys.stderr)


if __name__ == "__main__":
    main()
