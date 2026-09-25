"""Planifica los efectos de sonido a partir de layout.json y graficos.json (sección 6.6).

Nunca por reloj: cada efecto nace de un evento visual.
  gancho en el frame 0 -> impacto (máx. 1)        cambio full <-> split -> whoosh (100 ms antes)
  cartela / palabra clave / imagen -> pop          cada punto de lista o pasos -> click
  cifra -> tick durante el conteo + ding al llegar alerta -> alerta
  cambio de lado en comparativa -> swipe           aparición del CTA -> notificacion
  punch-in -> nada
Densidad (perfil.audio.densidad_sfx):
  baja  = solo gancho, cambios de layout y CTA
  media = como máximo 1 efecto cada 2 s de media (se descartan los de menor prioridad)
  alta  = todos los eventos
Nunca dos efectos a la vez (separación mínima). Si un efecto cae dentro de una palabra, se
adelanta al inicio de esa palabra. La variante se elige de forma pseudoaleatoria reproducible,
sin repetir la misma variante dos veces seguidas.

Uso:
  python pipeline/planificar_sfx.py --layout layout.json --graficos graficos.json --perfil perfiles/jose \
      [--edl edl.json --transcripcion corr.json] --semilla <id_trabajo> -o sfx_timeline.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SEPARACION_MIN = 0.35  # s entre dos efectos: "nunca dos a la vez"
ADELANTO_WHOOSH = 0.10
TICKS_CONTEO = 4       # ticks durante el conteo de una cifra (solo densidad alta)
DURACION_CONTEO = 1.0

# Prioridad al recortar densidad (mayor = se conserva antes). Los efectos ligados a un gráfico
# van por delante de los whoosh de layout: con un ritmo rápido (un cambio cada ~2 s) los whoosh
# coparían la densidad y el resultado sería monótono.
PRIORIDAD = {"impacto": 9, "notificacion": 8, "ding": 7, "alerta": 7, "swipe": 6, "pop": 5,
             "click": 4, "whoosh": 3, "tick": 1,
             # semánticos de los motion graphics visuales: tan importantes como el propio gráfico
             **{t: 6 for t in ("moneda", "papel", "despegue", "red", "teclado", "candado", "reloj", "subida",
                               "bajada", "transformacion", "camara", "mensaje")}}
# Sonido por defecto de las plantillas visuales (si datos.sonido no lo fija).
SONIDO_PLANTILLA = {"red": "red", "transformacion": "transformacion", "uno_vs_muchos": "transformacion",
                    "terminal": "teclado", "imagen": "pop", "palabra_clave": "pop", "pregunta": "pop"}
TECLEO_ANTES = 0.6  # el tecleo de la terminal suena mientras se escribe la línea
BASICOS = {"impacto", "whoosh", "notificacion"}  # densidad baja


def biblioteca_audio(perfil_dir: Path) -> Path:
    """La carpeta audio/ del perfil, si existe, sustituye a la biblioteca común."""
    propia = perfil_dir / "audio"
    return propia if (propia / "sfx").is_dir() or (propia / "musica").is_dir() else RAIZ / "biblioteca_audio"


def variantes(biblioteca: Path, tipo: str) -> list[str]:
    cat = biblioteca / "sfx" / tipo / "catalogo.yaml"
    if not cat.exists():
        return []
    pistas = (yaml.safe_load(cat.read_text(encoding="utf-8")) or {}).get("pistas") or []
    return [str(biblioteca / "sfx" / tipo / p["archivo"]) for p in pistas]


def sonido_icono(nombre: str) -> str | None:
    cat = RAIZ / "plantillas" / "_iconos" / "catalogo.yaml"
    iconos = yaml.safe_load(cat.read_text(encoding="utf-8"))["iconos"] if cat.exists() else {}
    return (iconos.get(nombre) or {}).get("sonido")


def eventos_brutos(layout: dict, graficos: list[dict]) -> list[dict]:
    ev = []
    vs = layout["ventanas"]
    if vs and vs[0]["tipo"] == "split":
        ev.append({"t": 0.0, "tipo": "impacto", "motivo": "gancho en el frame 0"})
    for a, b in zip(vs, vs[1:]):
        if a["tipo"] != b["tipo"]:
            ev.append({"t": max(0.0, b["inicio"] - ADELANTO_WHOOSH), "tipo": "whoosh",
                       "motivo": f"cambio {a['tipo']} -> {b['tipo']}"})
    for g in graficos:
        t0, d, p = g["inicio"], g["datos"], g["plantilla"]
        propio = d.get("sonido")  # el LLM puede fijar el sonido con sentido para ese gráfico
        if p == "icono":
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": propio or sonido_icono(d["icono"]) or "pop",
                       "motivo": f"icono {d['icono']}"})
        elif p == "crecimiento":
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": propio or ("bajada" if d.get("direccion") == "baja" else "subida"),
                       "motivo": "crecimiento"})
        elif p == "terminal":
            for x in d.get("lineas", []):
                if x.get("tipo", "comando") == "comando":
                    ev.append({"t": max(t0, t0 + x["t"] - TECLEO_ANTES), "tipo": propio or "teclado", "motivo": "terminal: tecleo"})
                elif x.get("tipo") == "exito":
                    ev.append({"t": t0 + x["t"], "tipo": "ding", "motivo": "terminal: éxito"})
        elif p in ("red", "transformacion", "uno_vs_muchos"):
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": propio or SONIDO_PLANTILLA[p], "motivo": p})
        elif p == "cta":
            ev.append({"t": t0 + d.get("t_aterrizaje", 0), "tipo": "notificacion", "motivo": "CTA"})
        elif p in ("lista", "pasos"):
            for x in d.get("items") or d.get("pasos") or []:
                ev.append({"t": t0 + x["t"], "tipo": "click", "motivo": f"{p}: {x['texto']}"})
        elif p == "cifra":
            t = t0 + d["t_aterrizaje"]
            for k in range(TICKS_CONTEO):
                ev.append({"t": t - DURACION_CONTEO + k * DURACION_CONTEO / TICKS_CONTEO, "tipo": "tick",
                           "motivo": "conteo"})
            ev.append({"t": t, "tipo": "ding", "motivo": "cifra final"})
        elif p == "alerta":
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": "alerta", "motivo": "alerta"})
        elif p == "comparativa":
            ev.append({"t": t0 + d["t_derecha"], "tipo": "swipe", "motivo": "cambio de lado"})
        elif p == "grafico":
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": "pop", "motivo": "gráfico"})
        elif p != "gancho":  # el gancho ya tiene su impacto
            ev.append({"t": t0 + d.get("t_aterrizaje", 0), "tipo": propio or SONIDO_PLANTILLA.get(p, "pop"), "motivo": p})
    return sorted((e for e in ev if e["t"] >= 0), key=lambda e: e["t"])


def ajustar_a_palabras(ev: list[dict], palabras: list[dict]) -> None:
    """Un efecto que cae dentro de una palabra se adelanta al inicio de esa palabra."""
    for e in ev:
        for w in palabras:
            if w["o_start"] < e["t"] < w["o_end"]:
                e["t"] = w["o_start"]
                break


def aplicar_densidad(ev: list[dict], densidad: str, duracion: float) -> tuple[list[dict], list[dict]]:
    if densidad == "baja":
        quedan = [e for e in ev if e["tipo"] in BASICOS]
    elif densidad == "media":
        quedan = [e for e in ev if e["tipo"] != "tick"]
        maximo = max(1, int(duracion / 2))
        if len(quedan) > maximo:
            orden = sorted(quedan, key=lambda e: (-PRIORIDAD[e["tipo"]], e["t"]))
            quedan = sorted(orden[:maximo], key=lambda e: e["t"])
    else:
        quedan = list(ev)
    # Nunca dos a la vez: ante un choque se queda el de mayor prioridad.
    final: list[dict] = []
    for e in quedan:
        if final and e["t"] - final[-1]["t"] < SEPARACION_MIN:
            if PRIORIDAD[e["tipo"]] > PRIORIDAD[final[-1]["tipo"]]:
                final[-1] = e
            continue
        final.append(e)
    descartados = [e for e in ev if e not in final]
    return final, descartados


def asignar_variantes(ev: list[dict], biblioteca: Path, semilla: str) -> list[dict]:
    rng = random.Random(semilla)
    ultima: dict[str, str] = {}
    sin_archivo = []
    for e in ev:
        opciones = variantes(biblioteca, e["tipo"])
        if not opciones and e["tipo"] in PRIORIDAD and e["tipo"] not in BASICOS:
            e["motivo"] += f" (sin «{e['tipo']}» en la biblioteca: pop)"
            e["tipo"], opciones = "pop", variantes(biblioteca, "pop")
        if not opciones:
            sin_archivo.append(e)
            continue
        candidatas = [o for o in opciones if o != ultima.get(e["tipo"])] or opciones
        e["archivo"] = rng.choice(candidatas)
        ultima[e["tipo"]] = e["archivo"]
    return sin_archivo


def planificar(layout: dict, graficos: list[dict], perfil_dir: Path, semilla: str,
               palabras: list[dict] | None = None) -> dict:
    perfil = cargar(perfil_dir)
    if not perfil.audio.sfx:
        return {"eventos": [], "descartados": [], "sin_archivo": [], "densidad": "ninguna"}
    ev = eventos_brutos(layout, graficos)
    if palabras:
        ajustar_a_palabras(ev, palabras)
    final, descartados = aplicar_densidad(ev, perfil.audio.densidad_sfx, layout["duracion"])
    sin_archivo = asignar_variantes(final, biblioteca_audio(perfil_dir), semilla)
    final = [e for e in final if "archivo" in e]
    for e in final:
        e["t"] = round(e["t"], 3)
    return {"densidad": perfil.audio.densidad_sfx, "eventos": final, "descartados": descartados,
            "sin_archivo": sin_archivo}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layout", type=Path, required=True)
    ap.add_argument("--graficos", type=Path, required=True)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--edl", type=Path)
    ap.add_argument("--transcripcion", type=Path)
    ap.add_argument("--semilla", default="0")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    palabras = None
    if args.edl and args.transcripcion:
        from planificar_layout import palabras_en_salida
        palabras = palabras_en_salida(leer(args.edl), leer(args.transcripcion))
    plan = planificar(leer(args.layout), leer(args.graficos)["graficos"], args.perfil, args.semilla, palabras)
    args.salida.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"guardado: {args.salida} — {len(plan['eventos'])} efectos (densidad {plan['densidad']}), "
          f"{len(plan['descartados'])} descartados, {len(plan['sin_archivo'])} sin archivo en la biblioteca")


if __name__ == "__main__":
    main()
