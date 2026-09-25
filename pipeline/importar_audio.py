"""Importa audio nuevo de biblioteca_audio/_entrada/ al catálogo (sección 6.6).

Cada archivo necesita al lado un .json con su procedencia:
  {"clase": "musica"|"sfx", "categoria": "<estado de ánimo o tipo>", "fuente": "...",
   "licencia": "...", "uso_permitido": ["organico", "anuncios"]}
Sin fuente y licencia anotadas NO entra al catálogo (se informa y se deja en _entrada/).

Para cada archivo aceptado:
  - normaliza el loudness a un nivel común: música a −20 LUFS integrados (TP −2 dBTP) y
    efectos con el pico a −3 dBFS, así los niveles del pipeline son predecibles;
  - recorta el silencio inicial y final de los efectos;
  - mide duración y BPM con librosa y marca `inicio_recomendado` (primer tiempo fuerte tras la intro);
  - lo guarda en musica/<estado>/ o sfx/<tipo>/ (FLAC 48 kHz estéreo) y lo añade al catalogo.yaml de esa carpeta.
El original de _entrada/ se mueve a _entrada/importados/ (no se borra).

Uso:
  python pipeline/importar_audio.py [--biblioteca biblioteca_audio]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import yaml

RAIZ = Path(__file__).resolve().parent.parent
EXTENSIONES = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
MUSICA_LUFS, MUSICA_TP = -20.0, -2.0
SFX_PICO_DB = -3.0
PICO_MINIMO_DB = -40.0  # por debajo, la generación salió prácticamente muda y se rechaza
ESTADOS = {"energetica", "inspiradora", "tension", "neutra", "emocional"}
TIPOS_SFX = {"impacto", "whoosh", "pop", "click", "tick", "ding", "alerta", "swipe", "notificacion"}


def ffmpeg(*args: str) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return r.stderr


def loudnorm_dos_pasadas(origen: Path, destino: Path) -> None:
    filtro = f"loudnorm=I={MUSICA_LUFS}:TP={MUSICA_TP}:LRA=11"
    salida = ffmpeg("-i", str(origen), "-af", filtro + ":print_format=json", "-f", "null", "-")
    m = json.loads(salida[salida.rindex("{"):salida.rindex("}") + 1])
    medido = (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
              f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    ffmpeg("-i", str(origen), "-af", filtro + medido, "-ar", "48000", "-ac", "2", "-c:a", "flac", str(destino))


def pico_db(ruta: Path) -> float:
    m = re.search(r"max_volume: (-?[\d.]+) dB", ffmpeg("-i", str(ruta), "-af", "volumedetect", "-f", "null", "-"))
    return float(m.group(1)) if m else -120.0


def normalizar_sfx(origen: Path, destino: Path) -> None:
    # Recorta silencios de los extremos y lleva el pico a SFX_PICO_DB.
    recorte = ("silenceremove=start_periods=1:start_threshold=-60dB,"
               "areverse,silenceremove=start_periods=1:start_threshold=-60dB,areverse")
    tmp = destino.with_suffix(".tmp.wav")
    ffmpeg("-i", str(origen), "-af", recorte, "-ar", "48000", "-ac", "2", str(tmp))
    pico = pico_db(tmp)
    ffmpeg("-i", str(tmp), "-af", f"volume={SFX_PICO_DB - pico:.2f}dB", "-c:a", "flac", str(destino))
    tmp.unlink()


def analizar(ruta: Path, es_musica: bool) -> dict:
    import librosa
    y, sr = librosa.load(str(ruta), sr=22050, mono=True)
    datos = {"duracion_s": round(len(y) / sr, 3)}
    if not es_musica:
        return datos
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    while bpm > 140:  # librosa a veces duplica (o divide) el tempo: se lleva a 70–140
        bpm /= 2
    while 0 < bpm < 70:
        bpm *= 2
    tiempos = librosa.frames_to_time(beats, sr=sr)
    # Fin de la intro: primer momento en que la energía alcanza el 70 % de la mediana
    # de la parte fuerte; el inicio recomendado es el primer tiempo desde ahí.
    rms = librosa.feature.rms(y=y)[0]
    t_rms = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    umbral = 0.7 * np.median(rms[rms > np.percentile(rms, 50)])
    fin_intro = float(t_rms[np.argmax(rms >= umbral)])
    siguientes = [t for t in tiempos if t >= fin_intro]
    datos.update({"bpm": round(bpm, 1), "inicio_recomendado": round(float(siguientes[0] if siguientes else fin_intro), 3)})
    return datos


def importar(biblioteca: Path) -> None:
    entrada = biblioteca / "_entrada"
    hechos = entrada / "importados"
    for audio in sorted(p for p in entrada.iterdir() if p.suffix.lower() in EXTENSIONES):
        meta_ruta = audio.with_suffix(".json")
        meta = json.loads(meta_ruta.read_text(encoding="utf-8")) if meta_ruta.exists() else {}
        faltan = [c for c in ("clase", "categoria", "fuente", "licencia", "uso_permitido") if not meta.get(c)]
        if faltan:
            print(f"❌ {audio.name}: falta {faltan} en {meta_ruta.name}; no entra al catálogo")
            continue
        es_musica = meta["clase"] == "musica"
        validos = ESTADOS if es_musica else TIPOS_SFX
        if meta["categoria"] not in validos:
            print(f"❌ {audio.name}: categoría '{meta['categoria']}' no válida ({sorted(validos)})")
            continue
        if not es_musica and pico_db(audio) < PICO_MINIMO_DB:
            print(f"❌ {audio.name}: prácticamente mudo (pico < {PICO_MINIMO_DB:.0f} dB); no entra al catálogo")
            continue
        carpeta = biblioteca / ("musica" if es_musica else "sfx") / meta["categoria"]
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{audio.stem}.flac"
        (loudnorm_dos_pasadas if es_musica else normalizar_sfx)(audio, destino)
        ficha = {"archivo": destino.name, **analizar(destino, es_musica),
                 "fuente": meta["fuente"], "licencia": meta["licencia"], "uso_permitido": meta["uso_permitido"]}
        if meta.get("prompt"):
            ficha["prompt"] = meta["prompt"]
        cat_ruta = carpeta / "catalogo.yaml"
        catalogo = yaml.safe_load(cat_ruta.read_text(encoding="utf-8")) if cat_ruta.exists() else None
        catalogo = catalogo or {"pistas": []}
        catalogo["pistas"] = [p for p in catalogo["pistas"] if p["archivo"] != ficha["archivo"]] + [ficha]
        cat_ruta.write_text(yaml.safe_dump(catalogo, allow_unicode=True, sort_keys=False), encoding="utf-8")
        hechos.mkdir(exist_ok=True)
        shutil.move(str(audio), hechos / audio.name)
        shutil.move(str(meta_ruta), hechos / meta_ruta.name)
        extra = f", {ficha['bpm']} BPM, inicio {ficha['inicio_recomendado']} s" if es_musica else ""
        print(f"✅ {audio.name} -> {destino.relative_to(biblioteca)} ({ficha['duracion_s']} s{extra})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--biblioteca", type=Path, default=RAIZ / "biblioteca_audio")
    importar(ap.parse_args().biblioteca)


if __name__ == "__main__":
    main()
