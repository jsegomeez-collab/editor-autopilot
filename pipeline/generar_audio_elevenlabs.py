"""Genera música (Eleven Music) y efectos (Sound Effects) con la API de ElevenLabs (sección 6.6).

Endpoints verificados en la documentación oficial (2026-09-25):
  POST /v1/music              {prompt, music_length_ms (3000–600000), model_id, force_instrumental}, ?output_format
  POST /v1/sound-generation   {text, duration_seconds (0,5–30), prompt_influence (0–1), model_id}, ?output_format
Licencia: el plan Starter o superior incluye uso comercial de música y efectos (comprobado en /v1/user/subscription).

Cada pista generada se guarda en biblioteca_audio/_entrada/ junto a un .json con su procedencia
(fuente, licencia, uso_permitido, prompt), que importar_audio.py exige para aceptarla en el catálogo.
Es idempotente: no regenera un archivo que ya existe. Informa de los créditos gastados.

Uso:
  python pipeline/generar_audio_elevenlabs.py plan_audio.yaml [--solo ID ...] [--limite-creditos N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "biblioteca_audio" / "_entrada"
API = "https://api.elevenlabs.io/v1"
ENV = Path.home() / "Developer" / "video-use" / ".env"  # la clave vive solo ahí
# Coste estimado (centro de ayuda de ElevenLabs y medido en el piloto). El contador de
# /v1/user/subscription no refleja la música, así que el límite se controla por estimación.
CREDITOS_MUSICA_MIN = 900
CREDITOS_SFX_S = 11


def coste(item: dict) -> float:
    if item["clase"] == "musica":
        return item["duracion_s"] / 60 * CREDITOS_MUSICA_MIN
    return max(item["duracion_s"], 0.5) * CREDITOS_SFX_S


def clave() -> str:
    for linea in ENV.read_text().splitlines():
        if linea.startswith("ELEVENLABS_API_KEY="):
            return linea.split("=", 1)[1].strip()
    sys.exit("❌ falta ELEVENLABS_API_KEY en ~/Developer/video-use/.env")


def suscripcion(k: str) -> dict:
    r = requests.get(f"{API}/user/subscription", headers={"xi-api-key": k}, timeout=30)
    r.raise_for_status()
    return r.json()


def generar(k: str, item: dict) -> bytes:
    cab = {"xi-api-key": k}
    if item["clase"] == "musica":
        cuerpo = {"prompt": item["prompt"], "music_length_ms": int(item["duracion_s"] * 1000),
                  "model_id": item.get("model_id", "music_v1"), "force_instrumental": True}
        url = f"{API}/music?output_format=mp3_44100_192"
    else:
        cuerpo = {"text": item["prompt"], "duration_seconds": item["duracion_s"],
                  "prompt_influence": item.get("prompt_influence", 0.5)}
        url = f"{API}/sound-generation?output_format=mp3_44100_192"
    for intento in range(3):
        r = requests.post(url, headers=cab, json=cuerpo, timeout=600)
        if r.status_code == 200:
            return r.content
        if r.status_code in (429, 500, 502, 503) and intento < 2:
            time.sleep(10 * (intento + 1))
            continue
        raise RuntimeError(f"{item['id']}: HTTP {r.status_code} {r.text[:300]}")
    raise RuntimeError(f"{item['id']}: sin respuesta válida")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--solo", nargs="*", help="generar solo estos IDs")
    ap.add_argument("--limite-creditos", type=int, default=30000, help="para si el gasto estimado supera esta cifra")
    args = ap.parse_args()

    plan = yaml.safe_load(args.plan.read_text(encoding="utf-8"))
    k = clave()
    sub = suscripcion(k)
    if sub.get("tier") == "free":
        sys.exit("❌ plan Free: sin licencia comercial para música/efectos. Hace falta Starter o superior.")
    inicial = sub["character_count"]
    estimado = 0.0
    ENTRADA.mkdir(parents=True, exist_ok=True)
    licencia = f"ElevenLabs plan {sub['tier']} — uso comercial incluido"

    for item in plan["items"]:
        if args.solo and item["id"] not in args.solo:
            continue
        destino = ENTRADA / f"{item['id']}.mp3"
        if destino.exists():
            print(f"= {item['id']} (ya existe)")
            continue
        if estimado + coste(item) > args.limite_creditos:
            sys.exit(f"🛑 el gasto estimado superaría {args.limite_creditos} créditos; paro antes de {item['id']}")
        destino.write_bytes(generar(k, item))
        estimado += coste(item)
        meta = {"clase": item["clase"], "categoria": item["categoria"], "prompt": item["prompt"],
                "fuente": "ElevenLabs " + ("Eleven Music" if item["clase"] == "musica" else "Sound Effects"),
                "licencia": licencia, "uso_permitido": ["organico", "anuncios"],
                "generado": time.strftime("%Y-%m-%d")}
        destino.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"+ {item['id']} ({item['duracion_s']} s)")

    final = suscripcion(k)["character_count"]
    print(f"créditos estimados en esta ejecución: {estimado:.0f} | contador de la API: +{final - inicial} "
          f"(no incluye música) | usados en el periodo: {final}")


if __name__ == "__main__":
    main()
