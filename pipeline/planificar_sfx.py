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
SEPARACION_MIN = {"baja": 0.35, "media": 0.35, "alta": 0.15}  # "nunca dos a la vez" (efectos cortos)
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
                               "bajada", "transformacion", "camara", "mensaje", "engranaje")}}
# Sonido por defecto de las plantillas visuales (si datos.sonido no lo fija).
SONIDO_PLANTILLA = {"red": "red", "transformacion": "transformacion", "uno_vs_muchos": "transformacion",
                    "terminal": "teclado", "imagen": "pop", "palabra_clave": "pop", "pregunta": "pop"}
TECLEO_ANTES = 0.6  # el tecleo de la terminal suena mientras se escribe la línea
BASICOS = {"impacto", "whoosh", "notificacion"}  # densidad baja


def biblioteca_audio(perfil_dir: Path) -> Path:
    """La carpeta audio/ del perfil, si existe, sustituye a la biblioteca común."""
    propia = perfil_dir / "audio"
    return propia if (propia / "sfx").is_dir() or (propia / "musica").is_dir() else RAIZ / "biblioteca_audio"


def variantes(biblioteca: Path, tipo: str, solo_propios: bool | None = None) -> list[str]:
    """Rutas de las variantes de un tipo. solo_propios=True/False filtra por efectos del cliente."""
    cat = biblioteca / "sfx" / tipo / "catalogo.yaml"
    if not cat.exists():
        return []
    pistas = (yaml.safe_load(cat.read_text(encoding="utf-8")) or {}).get("pistas") or []
    if solo_propios is not None:
        pistas = [p for p in pistas if bool(p.get("propio")) == solo_propios]
    return [str(biblioteca / "sfx" / tipo / p["archivo"]) for p in pistas]


def elegir_variante(rng: random.Random, propios: list[str], generados: list[str], ultima: str | None) -> str:
    """Preferencia por los efectos del cliente, rotando: nunca la misma variante dos veces seguidas.
    Con un solo efecto propio se alterna con los generados; con varios, se rota entre los propios."""
    for grupo in (propios, generados):
        libres = [o for o in grupo if o != ultima]
        if libres:
            return rng.choice(libres)
    return rng.choice(propios + generados)


def sonido_icono(nombre: str) -> str | None:
    cat = RAIZ / "plantillas" / "_iconos" / "catalogo.yaml"
    iconos = yaml.safe_load(cat.read_text(encoding="utf-8"))["iconos"] if cat.exists() else {}
    return (iconos.get(nombre) or {}).get("sonido")


def limitar(t: float, dur: float) -> float:
    """Igual que HF.limitar en base.js: el último aterrizaje deja ≥ 1 s sostenido."""
    return min(max(0.0, t), max(0.0, dur - 1.0))


def subeventos(g: dict) -> list[dict]:
    """Efectos de los sub-elementos de cada gráfico (densidad alta), con los MISMOS tiempos que
    usan las plantillas por dentro (ver sus index.html). Tiempos absolutos de salida."""
    t0, dur, d, p = g["inicio"], g["duracion"], g["datos"], g["plantilla"]
    t = limitar(d.get("t_aterrizaje", 0), dur)
    ev = []
    if p == "gancho":
        ev.append({"t": t0 + 0.2, "tipo": "swipe", "motivo": "barrido del gancho"})
    elif p == "red":
        n = min(8, len(d.get("iconos", [])))
        paso = min(0.16, t * 0.55 / (n - 1)) if n > 1 else 0
        for i in range(n - 1):  # el último coincide con el aterrizaje
            ev.append({"t": t0 + max(0.0, t - (n - 1 - i) * paso), "tipo": "click", "motivo": f"red: satélite {i + 1}"})
    elif p == "uno_vs_muchos":
        n = len(d.get("iconos", []))
        pre = min(t, 0.45 + n * 0.17)
        t_fig = max(0.0, t - pre)
        paso = max(0.0, pre - 0.3) / n if n else 0
        ev.append({"t": t0 + t_fig, "tipo": "pop", "motivo": "figura"})
        for i in range(n):
            ev.append({"t": t0 + min(t, t_fig + 0.1 + paso * (i + 1)), "tipo": "click", "motivo": f"tarea {i + 1}"})
    elif p == "cifra":
        conteo = min(1.0, t)
        for k in range(TICKS_CONTEO):
            ev.append({"t": t0 + t - conteo + k * conteo / TICKS_CONTEO, "tipo": "tick", "motivo": "conteo"})
    elif p == "crecimiento" and d.get("valor") is not None:
        for k in range(TICKS_CONTEO):
            ev.append({"t": t0 + max(0.0, t - 1.0) + k * 0.25, "tipo": "tick", "motivo": "conteo de la curva"})
    elif p == "transformacion":
        T = 0.75
        ta = max(0.0, min(d["t_a"] if d.get("t_a") is not None else t - T - 0.25, t - T * 0.8))
        ev.append({"t": t0 + ta, "tipo": "pop", "motivo": "aparece A"})
        ev.append({"t": t0 + max(0.0, t - T), "tipo": "whoosh", "motivo": "A viaja hacia B"})
    elif p == "icono":
        if d.get("movimiento") in ("subir", "caer"):
            ev.append({"t": t0 + max(0.0, t - 0.5), "tipo": "whoosh", "motivo": f"icono: {d['movimiento']}"})
        if d.get("rotulo"):
            ev.append({"t": t0 + min(limitar(t + 0.35, dur), dur), "tipo": "pop", "motivo": "rótulo"})
    elif p == "palabra_clave":
        for k, _ in enumerate(d.get("texto", "").split()[:-1]):
            ev.append({"t": t0 + max(0.0, t - 0.25 * (len(d["texto"].split()) - 1 - k)), "tipo": "pop", "motivo": "palabra"})
    return ev


def eventos_brutos(layout: dict, graficos: list[dict], alta: bool = False) -> list[dict]:
    ev = []
    vs = layout["ventanas"]
    if vs and vs[0]["tipo"] == "split":
        ev.append({"t": 0.0, "tipo": "impacto", "motivo": "gancho en el frame 0"})
    for a, b in zip(vs, vs[1:]):
        if a["tipo"] != b["tipo"] or (alta and a.get("zoom") != b.get("zoom")):
            ev.append({"t": max(0.0, b["inicio"] - ADELANTO_WHOOSH), "tipo": "whoosh",
                       "motivo": f"cambio {a['tipo']} -> {b['tipo']}" + (" (punch-in)" if a["tipo"] == b["tipo"] else "")})
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
        elif p == "sticker":
            ev.append({"t": t0 + d.get("t_aterrizaje", 0), "tipo": propio or "pop", "motivo": f"sticker {d['icono']}"})
        elif p == "grafico":
            ev.append({"t": t0 + d["t_aterrizaje"], "tipo": "pop", "motivo": "gráfico"})
        elif p != "gancho":  # el gancho ya tiene su impacto
            ev.append({"t": t0 + d.get("t_aterrizaje", 0), "tipo": propio or SONIDO_PLANTILLA.get(p, "pop"), "motivo": p})
    if alta:
        for g in graficos:
            ev += subeventos(g)
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
    separacion = SEPARACION_MIN[densidad]
    for e in quedan:
        if final and e["t"] - final[-1]["t"] < separacion:
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
        e["archivo"] = elegir_variante(rng, variantes(biblioteca, e["tipo"], True),
                                       variantes(biblioteca, e["tipo"], False), ultima.get(e["tipo"]))
        ultima[e["tipo"]] = e["archivo"]
    return sin_archivo


def planificar(layout: dict, graficos: list[dict], perfil_dir: Path, semilla: str,
               palabras: list[dict] | None = None, densidad: str | None = None) -> dict:
    perfil = cargar(perfil_dir)
    if densidad:  # variantes: otra densidad de efectos
        perfil.audio.densidad_sfx = densidad
    if not perfil.audio.sfx:
        return {"eventos": [], "descartados": [], "sin_archivo": [], "densidad": "ninguna"}
    ev = eventos_brutos(layout, graficos, alta=perfil.audio.densidad_sfx == "alta")
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
    ap.add_argument("--densidad", choices=["baja", "media", "alta"], help="sustituye la del perfil (variantes)")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    palabras = None
    if args.edl and args.transcripcion:
        from planificar_layout import palabras_en_salida
        palabras = palabras_en_salida(leer(args.edl), leer(args.transcripcion))
    plan = planificar(leer(args.layout), leer(args.graficos)["graficos"], args.perfil, args.semilla, palabras,
                      args.densidad)
    args.salida.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"guardado: {args.salida} — {len(plan['eventos'])} efectos (densidad {plan['densidad']}), "
          f"{len(plan['descartados'])} descartados, {len(plan['sin_archivo'])} sin archivo en la biblioteca")


if __name__ == "__main__":
    main()
