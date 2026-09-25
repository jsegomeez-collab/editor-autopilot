"""Mezcla de audio: voz + música + efectos (sección 6.6).

Voz:     paso alto 80 Hz; afftdn solo si el suelo de ruido medido supera −58 dB.
Música:  pista del estado de ánimo (perfil + rotación: nunca una de las últimas 5 del perfil),
         empieza en `inicio_recomendado`, bucle con crossfade de ~1 compás si es corta, fade in 0,5 s
         y fade out que termina con el vídeo. Ducking con sidechaincompress disparado por la voz:
         sin voz queda ~14 dB por debajo; con voz, ~20 dB (perfil.audio.niveles.musica_db_bajo_voz).
Efectos: cada uno en su instante, con microfades de 5/8 ms y el pico ≥ 6 dB por debajo del pico
         de la voz en ese momento.
Final:   loudnorm en dos pasadas a −14 LUFS integrados y −1 dBTP sobre la mezcla completa (ganancia
         lineal: no altera las relaciones de nivel anteriores).

Uso:
  python pipeline/mezcla_audio.py --video <edit>/base.mp4 --perfil perfiles/jose --estado neutra \
      --sfx sfx_timeline.json --trabajo <id> -o <edit>/mezcla.wav [--anuncios] [--sin-musica]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402
from planificar_sfx import biblioteca_audio  # noqa: E402

SR = 48000
ROTACION = 5
MUSICA_CATALOGO_LUFS = -20.0   # nivel común de importar_audio.py
SFX_CATALOGO_PICO = -3.0
REDUCCION_DUCKING_DB = 6.0     # medido en JOSE49: la música baja ~6 dB cuando hablas (threshold -30 dBFS, ratio 6)
UMBRAL_RUIDO_DB = -58.0
# El AAC sube los picos al codificar (medido: +2,6 dB en JOSE49). Limitador de picos
# tras loudnorm (−1,5 dBFS) para que el true peak final quede ≤ −1 dBTP.
LIMITE_PICO = 0.841  # −1,5 dBFS


def ffmpeg(*args: str) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-y", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1200:])
    return r.stderr


def duracion(ruta: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                 "csv=p=0", str(ruta)], capture_output=True, text=True, check=True).stdout)


def lufs(ruta: Path, filtro_previo: str = "") -> float:
    salida = ffmpeg("-i", str(ruta), "-af", (filtro_previo + "," if filtro_previo else "") + "ebur128",
                    "-vn", "-f", "null", "-")
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", salida)[-1])


def suelo_de_ruido(ruta: Path) -> float:
    salida = ffmpeg("-i", str(ruta), "-af", "astats=measure_overall=Noise_floor:measure_perchannel=none",
                    "-vn", "-f", "null", "-")
    m = re.findall(r"Noise floor dB:\s+(-?[\d.inf]+)", salida)
    try:
        return float(m[-1])
    except (IndexError, ValueError):
        return -120.0


def muestras_voz(ruta: Path) -> np.ndarray:
    crudo = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-vn", "-ac", "1", "-ar", str(SR),
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(crudo, dtype=np.float32)


# ---------- música ----------

def elegir_pista(perfil_dir: Path, estado: str, trabajo: str, anuncios: bool) -> dict:
    """Pista del estado pedido que no esté entre las últimas 5 usadas por el perfil."""
    bib = biblioteca_audio(perfil_dir)
    cat = bib / "musica" / estado / "catalogo.yaml"
    pistas = (yaml.safe_load(cat.read_text(encoding="utf-8")) or {}).get("pistas") if cat.exists() else None
    if not pistas:
        raise FileNotFoundError(f"no hay música en {cat}")
    if anuncios:
        pistas = [p for p in pistas if "anuncios" in p.get("uso_permitido", [])]
        if not pistas:
            raise ValueError(f"ninguna pista de '{estado}' tiene uso_permitido: anuncios")
    historial = [h for h in leer_uso(perfil_dir) if h["trabajo"] != trabajo]
    recientes = [h["archivo"] for h in historial[-ROTACION:]]
    ultimo_uso = {h["archivo"]: i for i, h in enumerate(historial)}
    libres = [p for p in pistas if f"{estado}/{p['archivo']}" not in recientes]
    candidatas = libres or pistas  # si todas se usaron hace poco, la menos reciente (se avisa en QA)
    elegida = min(candidatas, key=lambda p: ultimo_uso.get(f"{estado}/{p['archivo']}", -1))
    return {**elegida, "estado": estado, "ruta": str(bib / "musica" / estado / elegida["archivo"]),
            "repetida_reciente": not libres}


def leer_uso(perfil_dir: Path) -> list[dict]:
    ruta = perfil_dir / "uso_audio.json"
    return json.loads(ruta.read_text(encoding="utf-8"))["historial"] if ruta.exists() else []


def registrar_uso(perfil_dir: Path, pista: dict, trabajo: str) -> None:
    """Un registro por trabajo (rehacer un vídeo no duplica la entrada)."""
    historial = [h for h in leer_uso(perfil_dir) if h["trabajo"] != trabajo]
    historial.append({"archivo": f"{pista['estado']}/{pista['archivo']}", "trabajo": trabajo,
                      "fecha": time.strftime("%Y-%m-%d %H:%M")})
    (perfil_dir / "uso_audio.json").write_text(json.dumps({"historial": historial}, ensure_ascii=False, indent=2),
                                               encoding="utf-8")


def musica_ajustada(pista: dict, dur: float, destino: Path) -> Path:
    """Música desde inicio_recomendado, en bucle con crossfade de ~1 compás hasta cubrir `dur`."""
    inicio = float(pista.get("inicio_recomendado", 0))
    util = float(pista["duracion_s"]) - inicio
    compas = min(4 * 60 / float(pista.get("bpm") or 120), util / 3)
    copias = 1
    while util * copias - compas * (copias - 1) < dur + 0.5:
        copias += 1
    entradas = []
    for _ in range(copias):
        entradas += ["-ss", f"{inicio:.3f}", "-i", pista["ruta"]]
    if copias == 1:
        filtro = "[0:a]anull[m]"
    else:
        filtro, actual = "", "0:a"
        for k in range(1, copias):
            filtro += f"[{actual}][{k}:a]acrossfade=d={compas:.3f}:c1=tri:c2=tri[x{k}];"
            actual = f"x{k}"
        filtro = filtro.rstrip(";").rsplit("[", 1)[0] + "[m]"
    ffmpeg(*entradas, "-filter_complex", filtro, "-map", "[m]", "-t", f"{dur:.3f}", "-ar", str(SR), "-ac", "2",
           str(destino))
    return destino


# ---------- mezcla ----------

def ganancia_sfx(voz: np.ndarray, t: float, pico_global_db: float, margen_db: float) -> float:
    """dB a aplicar al efecto (pico de catálogo −3 dBFS) para quedar ≥ margen por debajo de la voz."""
    a, b = max(0, int((t - 0.3) * SR)), int((t + 0.5) * SR)
    trozo = voz[a:b]
    pico = float(np.max(np.abs(trozo))) if len(trozo) else 0.0
    pico_db = 20 * np.log10(pico) if pico > 1e-4 else pico_global_db
    objetivo = min(pico_db, pico_global_db) - margen_db - 1.0  # 1 dB extra de seguridad
    return objetivo - SFX_CATALOGO_PICO


def mezclar(video: Path, perfil_dir: Path, estado: str | None, sfx: list[dict], trabajo: str, salida: Path,
            anuncios: bool = False) -> dict:
    perfil = cargar(perfil_dir)
    niveles = perfil.audio.niveles
    dur = duracion(video)
    tmp = salida.parent
    informe: dict = {"duracion_s": round(dur, 3)}

    ruido = suelo_de_ruido(video)
    cadena_voz = "highpass=f=80"
    if ruido > UMBRAL_RUIDO_DB:
        cadena_voz += f",afftdn=nf={max(-80, min(-20, round(ruido)))}"
    informe["voz"] = {"suelo_ruido_db": round(ruido, 1), "afftdn": ruido > UMBRAL_RUIDO_DB}
    voz_lufs = lufs(video, cadena_voz)
    voz = muestras_voz(video)
    pico_global = 20 * np.log10(max(1e-4, float(np.percentile(np.abs(voz), 99.9))))

    entradas = ["-i", str(video)]
    filtros = [f"[0:a]{cadena_voz},aresample={SR},aformat=channel_layouts=stereo,asplit=2[voz][sc]"]
    mezcla = ["[voz]"]

    usar_musica = perfil.audio.musica and estado is not None
    if usar_musica:
        if estado not in perfil.audio.estados_animo_permitidos:
            estado = perfil.audio.estado_animo_por_defecto
        pista = elegir_pista(perfil_dir, estado, trabajo, anuncios)
        ajustada = musica_ajustada(pista, dur, tmp / "musica_ajustada.wav")
        # Sin voz: (musica_db_bajo_voz − reducción del ducking) por debajo; con voz, ~musica_db_bajo_voz.
        g = (voz_lufs - (niveles.musica_db_bajo_voz - REDUCCION_DUCKING_DB)) - MUSICA_CATALOGO_LUFS
        entradas += ["-i", str(ajustada)]
        filtros.append(f"[1:a]volume={g:.2f}dB,afade=t=in:d=0.5,afade=t=out:st={max(0, dur - 1.5):.3f}:d=1.5[mus]")
        filtros.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350:makeup=1[musd]")
        mezcla.append("[musd]")
        informe["musica"] = {k: pista[k] for k in ("estado", "archivo", "fuente", "licencia", "uso_permitido",
                                                    "repetida_reciente")}
        informe["musica"]["ganancia_db"] = round(g, 2)
    else:
        filtros.append("[sc]anullsink")

    base = len(entradas) // 2
    informe["sfx"] = []
    for k, e in enumerate(sfx):
        g = ganancia_sfx(voz, e["t"], pico_global, niveles.sfx_db_bajo_pico_voz)
        d = duracion(Path(e["archivo"]))
        ms = int(round(e["t"] * 1000))
        entradas += ["-i", e["archivo"]]
        filtros.append(f"[{base + k}:a]aresample={SR},aformat=channel_layouts=stereo,"
                       f"afade=t=in:d=0.005,afade=t=out:st={max(0, d - 0.008):.3f}:d=0.008,"
                       f"volume={g:.2f}dB,adelay={ms}|{ms}[s{k}]")
        mezcla.append(f"[s{k}]")
        informe["sfx"].append({**e, "ganancia_db": round(g, 2)})

    filtros.append("".join(mezcla) + f"amix=inputs={len(mezcla)}:normalize=0:duration=first[mix]")
    premezcla = tmp / "premezcla.wav"
    ffmpeg(*entradas, "-filter_complex", ";".join(filtros), "-map", "[mix]", "-t", f"{dur:.3f}",
           "-ar", str(SR), "-c:a", "pcm_s24le", str(premezcla))

    # loudnorm en dos pasadas sobre la mezcla completa.
    objetivo = f"loudnorm=I={niveles.voz_lufs}:TP=-1:LRA=11"
    m = ffmpeg("-i", str(premezcla), "-af", objetivo + ":print_format=json", "-f", "null", "-")
    j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    ffmpeg("-i", str(premezcla), "-af",
           objetivo + f":measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
           f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,"
           f"alimiter=limit={LIMITE_PICO}:attack=3:release=60:level=false",
           "-ar", str(SR), "-c:a", "pcm_s24le", str(salida))
    premezcla.unlink()
    informe["lufs_final"] = lufs(salida)
    (salida.with_suffix(".json")).write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    return informe


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", type=Path, required=True, help="vídeo con la voz ya cortada (base.mp4)")
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--estado", help="estado de ánimo de la música (lo decide el LLM por el tono)")
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--anuncios", action="store_true", help="solo música con uso_permitido: anuncios")
    ap.add_argument("--sfx", type=Path, help="sfx_timeline.json")
    ap.add_argument("--trabajo", required=True, help="id del trabajo (rotación y semilla)")
    ap.add_argument("--registrar-uso", action="store_true", help="anota la pista en uso_audio.json del perfil")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    sfx = json.loads(args.sfx.read_text(encoding="utf-8"))["eventos"] if args.sfx else []
    estado = None if args.sin_musica else (args.estado or cargar(args.perfil).audio.estado_animo_por_defecto)
    inf = mezclar(args.video, args.perfil, estado, sfx, args.trabajo, args.salida, args.anuncios)
    if args.registrar_uso and "musica" in inf:
        registrar_uso(args.perfil, {"estado": inf["musica"]["estado"], "archivo": inf["musica"]["archivo"]}, args.trabajo)
    print(f"guardado: {args.salida} — {inf['lufs_final']} LUFS, música: "
          f"{inf.get('musica', {}).get('archivo', 'sin música')}, {len(inf['sfx'])} efectos")


if __name__ == "__main__":
    main()
