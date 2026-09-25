"""Compositor: EDL + layout (+ overlays + subtítulos) -> vídeo (secciones 6.3–6.5).

Replica las reglas duras de video-use sin llamar a su render.py (ver PLAN.md §2.6):
  1. Extracción por segmento (re-encode) con fades de audio de 30 ms en cada borde.
  2. Concat sin pérdida con `-c copy` -> base.mp4 (sin doble codificación).
  3. UNA pasada final: layout -> motion graphics -> subtítulos (siempre los últimos).

El layout se aplica con tres cadenas que avanzan a la vez sobre una sola decodificación:
  full   : recorte 9:16 (x,y variables por ventana, tamaño fijo) -> 1080x1920
  punch  : recorte 9:16 con zoom 1,12 -> 1080x1920, visible solo en ventanas con zoom
  split  : recorte 9:8 de la cara -> panel inferior 1080x960 sobre el color de fondo
Cada cadena tiene un recorte de tamaño fijo y posición por ventana, así no hay que
trocear el vídeo en N ramas (lo que obligaría a ffmpeg a acumular frames en memoria).

Uso:
  python pipeline/componer.py --edl edl.json --layout layout.json --perfil perfiles/jose -o salida.mp4
      [--overlays graficos_render.json] [--ass subtitulos.ass --fontsdir DIR]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402

W, H, PANEL_H = 1080, 1920, 960
FADE_AUDIO = 0.03
DESTELLO_S = (0.08, 0.22)  # subida y bajada del destello
COLOR_DESTELLO = "0xFFE3A3"
OPACIDAD_DESTELLO = 0.55  # velo de luz: la imagen se sigue viendo debajo


def ffprobe_fps(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=avg_frame_rate", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True).stdout.strip()
    n, d = r.split("/")
    return float(n) / float(d)


# ---------- 1 y 2: segmentos + concat ----------

def extraer_segmentos(edl: dict, dir_clips: Path, fps: float) -> list[Path]:
    dir_clips.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, r in enumerate(edl["ranges"]):
        fuente = edl["sources"][r["source"]]
        dur = r["end"] - r["start"]
        salida = dir_clips / f"seg_{i:02d}.mp4"
        clips.append(salida)
        if salida.exists():
            continue
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-ss", f"{r['start']:.3f}", "-i", fuente, "-t", f"{dur:.3f}",
            "-af", f"afade=t=in:st=0:d={FADE_AUDIO},afade=t=out:st={dur - FADE_AUDIO:.3f}:d={FADE_AUDIO}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", str(salida),
        ], check=True)
    return clips


def concatenar(clips: list[Path], salida: Path) -> Path:
    lista = salida.with_suffix(".txt")
    lista.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", "-movflags", "+faststart", str(salida)], check=True)
    lista.unlink()
    return salida


# ---------- 3: pasada final ----------

def por_ventana(ventanas: list[dict], valor, defecto) -> str:
    """Expresión ffmpeg por tramos: valor(v) mientras t < fin de la ventana v."""
    expr = str(defecto)
    for v in reversed(ventanas):
        expr = f"if(lt(t,{v['fin']:.3f}),{valor(v)},{expr})"
    return expr


def activo(ventanas: list[dict]) -> str:
    """Expresión enable= que vale 1 dentro de cualquiera de las ventanas."""
    return "+".join(f"between(t,{v['inicio']:.3f},{v['fin'] - 0.001:.3f})" for v in ventanas) or "0"


def filtro_layout(layout: dict, fondo: str) -> tuple[str, str]:
    """Devuelve (filtergraph, etiqueta de salida) para el layout sobre [0:v]."""
    vs = layout["ventanas"]
    full = [v for v in vs if v["tipo"] == "full" and v["zoom"] == 1.0]
    punch = [v for v in vs if v["tipo"] == "full" and v["zoom"] != 1.0]
    split = [v for v in vs if v["tipo"] == "split"]
    partes, n = [], 1 + bool(punch) + bool(split)
    partes.append(f"[0:v]split={n}" + "".join(f"[c{i}]" for i in range(n)))

    def cadena(entrada: str, grupo: list[dict], salida: str, destino: tuple[int, int], extra: str = "") -> None:
        cw, ch = grupo[0]["recorte"][2], grupo[0]["recorte"][3]
        x = por_ventana(grupo, lambda v: v["recorte"][0], grupo[0]["recorte"][0])
        y = por_ventana(grupo, lambda v: v["recorte"][1], grupo[0]["recorte"][1])
        partes.append(f"[{entrada}]crop=w={cw}:h={ch}:x='{x}':y='{y}',"
                      f"scale={destino[0]}:{destino[1]}:flags=lanczos,setsar=1{extra}[{salida}]")

    base_grupo = full or punch or split
    if base_grupo is split:
        # Sin ventanas full: el fondo es un lienzo del color de marca.
        partes.append(f"color=c={fondo}:s={W}x{H}:r=30,format=yuv420p[fullv];[c0]nullsink")
    else:
        cadena("c0", full or punch, "fullv", (W, H))
    actual, i = "fullv", 1
    if punch and full:
        cadena(f"c{i}", punch, "punchv", (W, H))
        partes.append(f"[{actual}][punchv]overlay=0:0:enable='{activo(punch)}'[l{i}]")
        actual, i = f"l{i}", i + 1
    if split:
        cadena(f"c{i}", split, "carav", (W, PANEL_H), f",pad={W}:{H}:0:{PANEL_H}:color={fondo}")
        partes.append(f"[{actual}][carav]overlay=0:0:enable='{activo(split)}'[l{i}]")
        actual = f"l{i}"
    return ";".join(partes), actual


def filtro_destellos(layout: dict, entrada: str, duracion: float) -> tuple[str, str]:
    """Un destello de luz (capa de color con fundido de alfa) al inicio de cada ventana marcada."""
    partes, actual = [], entrada
    subida, bajada = DESTELLO_S
    for k, v in enumerate(w for w in layout["ventanas"] if w.get("destello")):
        t = v["inicio"]
        partes.append(
            f"color=c={COLOR_DESTELLO}:s={W}x{H}:d={duracion:.3f},format=rgba,"
            f"fade=t=in:st={max(0, t - subida):.3f}:d={subida}:alpha=1,"
            f"fade=t=out:st={t:.3f}:d={bajada}:alpha=1,colorchannelmixer=aa={OPACIDAD_DESTELLO}[d{k}];"
            f"[{actual}][d{k}]overlay=0:0:enable='between(t,{max(0, t - subida):.3f},{t + bajada:.3f})'[f{k}]")
        actual = f"f{k}"
    return ";".join(partes), actual


def filtro_overlays(overlays: list[dict], entrada: str, primer_indice: int) -> tuple[str, str]:
    """Motion graphics: setpts=PTS-STARTPTS+T/TB para que su frame 0 caiga al inicio de su ventana."""
    partes, actual = [], entrada
    for k, o in enumerate(overlays):
        idx = primer_indice + k
        t, fin = o["inicio"], o["inicio"] + o["duracion"]
        partes.append(f"[{idx}:v]setpts=PTS-STARTPTS+{t:.3f}/TB[o{k}];"
                      f"[{actual}][o{k}]overlay={o.get('x', 0)}:{o.get('y', 0)}:"
                      f"enable='between(t,{t:.3f},{fin:.3f})'[m{k}]")
        actual = f"m{k}"
    return ";".join(partes), actual


def componer(edl: dict, layout: dict, perfil_dir: Path, trabajo: Path, salida: Path,
             overlays: list[dict] | None = None, ass: Path | None = None, fontsdir: Path | None = None) -> Path:
    perfil = cargar(perfil_dir)
    fuente = Path(next(iter(edl["sources"].values())))
    fps = ffprobe_fps(fuente)
    base = concatenar(extraer_segmentos(edl, trabajo / "clips", fps), trabajo / "base.mp4")
    duracion = layout["duracion"]

    fondo = "0x" + perfil.colores.fondo.lstrip("#")
    grafo, actual = filtro_layout(layout, fondo)
    g_dest, actual = filtro_destellos(layout, actual, duracion)
    entradas = ["-i", str(base)]
    overlays = overlays or []
    for o in overlays:
        if o["archivo"].endswith(".webm"):
            entradas += ["-c:v", "libvpx-vp9"]  # sin esto ffmpeg descarta el alfa del VP9
        entradas += ["-i", o["archivo"]]
    g_ov, actual = filtro_overlays(overlays, actual, 1)
    partes = [grafo, g_dest, g_ov]
    if ass:  # subtítulos SIEMPRE los últimos
        esc = lambda p: str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")  # noqa: E731
        partes.append(f"[{actual}]subtitles=filename='{esc(ass)}':fontsdir='{esc(fontsdir)}'[subs]")
        actual = "subs"
    partes.append(f"[{actual}]format=yuv420p[vout]")
    grafo_total = ";".join(p for p in partes if p)
    (trabajo / "filtro_final.txt").write_text(grafo_total, encoding="utf-8")
    # "-/opción archivo" lee el valor de un archivo (ffmpeg ≥ 7; -filter_complex_script ya no existe).
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", *entradas, "-/filter_complex", str(trabajo / "filtro_final.txt"),
        "-map", "[vout]", "-map", "0:a", "-r", f"{fps:g}", "-t", f"{duracion:.4f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "copy", "-movflags", "+faststart", str(salida),
    ], check=True)
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", type=Path, required=True)
    ap.add_argument("--layout", type=Path, required=True)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--overlays", type=Path)
    ap.add_argument("--ass", type=Path)
    ap.add_argument("--fontsdir", type=Path)
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    overlays = leer(args.overlays)["overlays"] if args.overlays else None
    salida = componer(leer(args.edl), leer(args.layout), args.perfil, args.edl.parent, args.salida,
                      overlays, args.ass, args.fontsdir)
    print(salida)


if __name__ == "__main__":
    main()
