"""Prepara biblioteca_audio/_escucha/ para el checkpoint de escucha (sección 6.6).

Genera:
  - muestrario_sfx.wav: todos los efectos seguidos (tipo por tipo, 0,6 s de pausa) + orden en el listado;
  - muestrario_musica.wav: 12 s de cada pista desde su inicio_recomendado, con fundidos;
  - listado.md: catálogo legible (estado/tipo, archivo, duración, BPM, inicio, fuente, licencia, uso).
El vídeo de prueba ya mezclado se copia aparte (lo genera el pipeline normal).

Uso:
  python pipeline/muestrario_audio.py [--biblioteca biblioteca_audio]
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
TROZO_MUSICA = 12.0
PAUSA_SFX = 0.6


def catalogos(biblioteca: Path, clase: str) -> list[tuple[str, Path, dict]]:
    salida = []
    for cat in sorted((biblioteca / clase).glob("*/catalogo.yaml")):
        for p in (yaml.safe_load(cat.read_text(encoding="utf-8")) or {}).get("pistas") or []:
            salida.append((cat.parent.name, cat.parent / p["archivo"], p))
    return salida


def concatenar(trozos: list[tuple[Path, float, float]], salida: Path, pausa: float, fundido: float) -> None:
    """Concatena (archivo, inicio, duración) con fundidos y silencio entre trozos."""
    entradas, filtros, etiquetas = [], [], []
    for k, (ruta, ini, dur) in enumerate(trozos):
        entradas += ["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", str(ruta)]
        f = f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo"
        if fundido:
            f += f",afade=t=in:d={fundido},afade=t=out:st={max(0, dur - fundido):.3f}:d={fundido}"
        filtros.append(f + f",apad=pad_dur={pausa}[a{k}]")
        etiquetas.append(f"[a{k}]")
    filtros.append("".join(etiquetas) + f"concat=n={len(trozos)}:v=0:a=1[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros),
                    "-map", "[out]", str(salida)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--biblioteca", type=Path, default=RAIZ / "biblioteca_audio")
    bib = ap.parse_args().biblioteca
    destino = bib / "_escucha"
    destino.mkdir(exist_ok=True)
    musica, sfx = catalogos(bib, "musica"), catalogos(bib, "sfx")

    lineas = ["# Catálogo de audio", "", f"{len(musica)} pistas de música y {len(sfx)} efectos.", "",
              "## Música (orden del muestrario: 12 s de cada una)", "",
              "| # | Estado | Archivo | Duración | BPM | Inicio rec. | Uso | Fuente / licencia |", "|---|---|---|---|---|---|---|---|"]
    for i, (estado, _, p) in enumerate(musica, 1):
        lineas.append(f"| {i} | {estado} | {p['archivo']} | {p['duracion_s']:.0f} s | {p.get('bpm', '—')} | "
                      f"{p.get('inicio_recomendado', 0):.1f} s | {', '.join(p['uso_permitido'])} | {p['fuente']} / {p['licencia']} |")
    lineas += ["", "## Efectos (orden del muestrario)", "", "| # | Tipo | Archivo | Duración |", "|---|---|---|---|"]
    for i, (tipo, _, p) in enumerate(sfx, 1):
        lineas.append(f"| {i} | {tipo} | {p['archivo']} | {p['duracion_s']:.2f} s |")
    (destino / "listado.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    if musica:
        concatenar([(r, float(p.get("inicio_recomendado", 0)), min(TROZO_MUSICA, p["duracion_s"]))
                    for _, r, p in musica], destino / "muestrario_musica.wav", 0.5, 0.4)
    if sfx:
        concatenar([(r, 0.0, p["duracion_s"]) for _, r, p in sfx], destino / "muestrario_sfx.wav", PAUSA_SFX, 0)
    print(f"{destino}: listado.md, muestrario_musica.wav ({len(musica)}), muestrario_sfx.wav ({len(sfx)})")


if __name__ == "__main__":
    main()
