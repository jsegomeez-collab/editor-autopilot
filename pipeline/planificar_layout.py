"""Planifica el layout split/full sobre la línea de tiempo de SALIDA (sección 6.3).

Entradas: edl.json, transcripción corregida, caras.json, perfil y, opcionalmente,
momentos.json del LLM con el tipo de cada frase:
  {"momentos": [{"desde": <t_salida>, "hasta": <t_salida>, "tipo": "visualizable" | "personal"}]}
Sin momentos.json se usa una heurística (cifras, enumeraciones, preguntas -> visualizable).

Reglas:
  - Gancho: de 0 a la primera pausa de fin de frase entre 3 y 10 s. Empieza en split.
    Dentro del gancho se alterna con ventanas de `ventanas.gancho_s`.
  - Resto: split en momentos visualizables (`split_s`), full en los personales (`full_s`).
  - Cambios solo en límites de palabra; se prefieren cortes del EDL y fines de frase.
  - Ningún tramo supera `max_sin_cambio_s` sin cambio visual: los full largos llevan
    punch-in (zoom 1,12) en un límite de palabra.
  - La última ventana (CTA) va en full.
  - El recorte de cada ventana es ESTÁTICO (mediana de las detecciones de la ventana).
    Una ventana split sin cara pasa a full y se anota en avisos.

Salida layout.json:
  {"ancho": 1080, "alto": 1920, "duracion", "ventanas": [
     {"inicio", "fin", "tipo": "split"|"full", "zoom", "recorte": [x,y,w,h], "destello": bool, "motivo"}],
   "avisos": [...]}

Uso:
  python pipeline/planificar_layout.py --edl edl.json --transcripcion corr.json --caras caras.json \
      --perfil perfiles/jose [--momentos momentos.json] -o layout.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import Perfil, cargar  # noqa: E402

SALIDA_W, SALIDA_H = 1080, 1920
PANEL_H = 960
ZOOM_PUNCH = 1.12
FIN_FRASE = re.compile(r"[.?!…]»?$")
PISTAS_VISUALES = re.compile(
    r"\b(primero|segundo|tercero|cuarto|quinto|paso|pasos|lista|versus|vs|comparado|mientras que|"
    r"antes|después|error|errores|cuidado|peligro|riesgo)\b", re.I)


# ---------- línea de tiempo de salida ----------

def palabras_en_salida(edl: dict, transcripcion: dict) -> list[dict]:
    """Palabras con tiempos de salida: t_salida = t_fuente - inicio_rango + offset_rango."""
    ws = [w for w in transcripcion["words"] if w.get("type") == "word"]
    salida, offset = [], 0.0
    for r in edl["ranges"]:
        for w in ws:
            if w["start"] >= r["start"] and w["end"] <= r["end"]:
                salida.append({**w, "o_start": round(w["start"] - r["start"] + offset, 3),
                               "o_end": round(w["end"] - r["start"] + offset, 3)})
        offset += r["end"] - r["start"]
    return salida


def cortes_edl(edl: dict) -> list[float]:
    t, cortes = 0.0, []
    for r in edl["ranges"][:-1]:
        t += r["end"] - r["start"]
        cortes.append(round(t, 3))
    return cortes


def a_tiempo_fuente(edl: dict, t_salida: float) -> float:
    offset = 0.0
    for r in edl["ranges"]:
        dur = r["end"] - r["start"]
        if t_salida <= offset + dur:
            return r["start"] + (t_salida - offset)
        offset += dur
    return edl["ranges"][-1]["end"]


# ---------- límites candidatos ----------

def limites(ws: list[dict], cortes: list[float]) -> list[dict]:
    """Puntos donde se puede cambiar de layout (entre dos palabras), con su prioridad."""
    cands = []
    for a, b in zip(ws, ws[1:]):
        t = round((a["o_end"] + b["o_start"]) / 2, 3)
        es_corte = any(a["o_end"] - 0.01 <= c <= b["o_start"] + 0.01 for c in cortes)
        if es_corte:
            t = min(cortes, key=lambda c: abs(c - t))
        prioridad = 3 if es_corte else 2 if FIN_FRASE.search(a["text"]) else 1 if a["text"].endswith(",") else 0
        cands.append({"t": t, "prioridad": prioridad, "fin_frase": bool(FIN_FRASE.search(a["text"]))})
    return cands


def elegir_limite(cands: list[dict], desde: float, rango: tuple[float, float], fin: float) -> float:
    """Mejor límite en [desde+min, desde+max]; si no hay ninguno, el primero después del mínimo."""
    lo, hi = desde + rango[0], desde + rango[1]
    if fin - desde <= rango[1]:
        return fin
    dentro = [c for c in cands if lo <= c["t"] <= hi]
    if dentro:
        # Máxima prioridad; a igualdad, lo más cerca del centro del rango.
        centro = (lo + hi) / 2
        return max(dentro, key=lambda c: (c["prioridad"], -abs(c["t"] - centro)))["t"]
    despues = [c["t"] for c in cands if c["t"] >= lo]
    return despues[0] if despues else fin


def siguiente_fin(cands: list[dict], t: float, rango: tuple[float, float], limite: float) -> float:
    """Fin de la ventana que empieza en t sin dejar antes de `limite` un resto más corto que el mínimo."""
    fin = min(elegir_limite(cands, t, rango, limite), limite)
    resto = limite - fin
    if 0 < resto < rango[0]:
        total = limite - t
        if total <= rango[1]:
            return limite
        mitad = total / 2  # dos ventanas parecidas en vez de una larga y otra mínima
        return min(elegir_limite(cands, t, (max(rango[0], mitad - 0.4), min(rango[1], mitad + 0.4)), limite), limite)
    return fin


# ---------- tipo de contenido ----------

def es_visualizable(texto: str, palabras: list[dict]) -> bool:
    if any("valor" in w for w in palabras):
        return True
    return bool(PISTAS_VISUALES.search(texto) or "?" in texto)


def tipo_por_momentos(momentos: list[dict], ini: float, fin: float) -> str | None:
    solapes = {}
    for m in momentos:
        s = min(fin, m["hasta"]) - max(ini, m["desde"])
        if s > 0:
            solapes[m["tipo"]] = solapes.get(m["tipo"], 0) + s
    if not solapes:
        return None
    return "split" if max(solapes, key=solapes.get) == "visualizable" else "full"


# ---------- encuadre ----------

MARGEN_ZONA = 20  # px de salida entre la barbilla y la zona segura inferior


def recorte_estatico(caras: dict, edl: dict, ini: float, fin: float, tipo: str, zoom: float,
                     zona_inferior: int = 380) -> list[int] | None:
    """Recorte [x,y,w,h] en la fuente con la mediana de las caras de la ventana."""
    t0, t1 = a_tiempo_fuente(edl, ini), a_tiempo_fuente(edl, fin)
    ms = [m for m in caras["muestras"] if m["caja"] and t0 <= m["t"] <= t1]
    if not ms:
        return None
    cx = statistics.median(m["caja"][0] + m["caja"][2] / 2 for m in ms)
    ojos_y = statistics.median((m["ojos"][0][1] + m["ojos"][1][1]) / 2 for m in ms)
    barbilla = statistics.median(m["caja"][1] + m["caja"][3] for m in ms)
    W, H = caras["ancho"], caras["alto"]
    if tipo == "split":
        # Panel 1080x960 (9:8). Con fuente vertical: ancho completo, ojos a 1/3 del panel.
        w = min(W, H * 9 / 8) / zoom
        h = w * 8 / 9
        y = ojos_y - h / 3
        # La barbilla debe quedar por encima de la zona segura inferior del panel.
        escala = h / PANEL_H
        limite_panel = PANEL_H - zona_inferior - MARGEN_ZONA
        y = max(y, barbilla - limite_panel * escala)
    else:
        # Full 9:16. Si la fuente es horizontal, recorte 9:16 centrado en la cara.
        h = min(H, W * 16 / 9) / zoom
        w = h * 9 / 16
        y = ojos_y - h * 0.30 if zoom > 1 else (H - h) / 2
    x = cx - w / 2
    x = min(max(0, x), W - w)
    y = min(max(0, y), H - h)
    return [int(round(v / 2) * 2) for v in (x, y, w, h)]


# ---------- plan ----------

def fin_del_gancho(cands: list[dict], duracion: float) -> float:
    for c in cands:
        if c["fin_frase"] and 3.0 <= c["t"] <= 10.0:
            return c["t"]
    return min(duracion, 10.0)


def inicio_cta(ws: list[dict], cands: list[dict], duracion: float) -> float:
    """El CTA empieza en la frase que pide comentar/escribir (la última)."""
    for i in range(len(ws) - 1, -1, -1):
        if re.match(r"(comenta|comentá|escribe|escribí|deja)\b", ws[i]["text"].lower()):
            previos = [c["t"] for c in cands if c["t"] <= ws[i]["o_start"] + 0.01]
            return previos[-1] if previos else ws[i]["o_start"]
    return max(0.0, duracion - 3.0)


def planificar(edl: dict, transcripcion: dict, caras: dict, perfil: Perfil, momentos: list[dict] | None,
               proporcion_split: float | None = None, punch_inicio: int = 0) -> dict:
    if proporcion_split is not None:  # variantes: más o menos cámara
        perfil.layout.ventanas.proporcion_split = proporcion_split
    ws = palabras_en_salida(edl, transcripcion)
    duracion = round(edl["total_duration_s"], 3)
    cands = limites(ws, cortes_edl(edl))
    v = perfil.layout.ventanas
    t_gancho = fin_del_gancho(cands, duracion)
    t_cta = inicio_cta(ws, cands, duracion)
    avisos: list[str] = []

    # 1) Trocear en ventanas con su tipo.
    brutas, t, tipo = [], 0.0, "split"
    while t < t_gancho - 0.05:
        fin = siguiente_fin(cands, t, v.gancho_s, t_gancho)
        brutas.append({"inicio": t, "fin": fin, "tipo": tipo, "motivo": "gancho"})
        t, tipo = fin, ("full" if tipo == "split" else "split")
    while t < t_cta - 0.05:
        texto_ventana = lambda a, b: [w for w in ws if a <= w["o_start"] < b]  # noqa: E731
        # Tipo decidido por el contenido (LLM o heurística); si empata, se alterna.
        prueba_fin = elegir_limite(cands, t, v.split_s, t_cta)
        pal = texto_ventana(t, prueba_fin)
        decidido = tipo_por_momentos(momentos, t, prueba_fin) if momentos else None
        if decidido is None:
            # Sin LLM: se reparte el tiempo según proporcion_split del perfil (tras el gancho),
            # sin dos full seguidos y con preferencia por split si lo dicho es visualizable.
            hechas = [b for b in brutas if b["motivo"] != "gancho"]
            t_split = sum(b["fin"] - b["inicio"] for b in hechas if b["tipo"] == "split")
            t_total = sum(b["fin"] - b["inicio"] for b in hechas) or 1.0
            visual = es_visualizable(" ".join(w["text"] for w in pal), pal)
            falta_split = t_split / t_total < v.proporcion_split
            dos_split = len(brutas) >= 2 and brutas[-1]["tipo"] == brutas[-2]["tipo"] == "split"
            decidido = "full" if dos_split else \
                "split" if brutas[-1]["tipo"] == "full" or falta_split or visual and t_split / t_total < 0.85 else "full"
        rango = v.split_s if decidido == "split" else v.full_s
        fin = siguiente_fin(cands, t, rango, t_cta)
        if fin == t_cta:
            decidido = "split"  # el CTA va en full: la ventana previa debe contrastar
        brutas.append({"inicio": t, "fin": fin, "tipo": decidido,
                       "motivo": "momentos" if momentos else "heuristica"})
        t = fin
    brutas.append({"inicio": t_cta, "fin": duracion, "tipo": "full", "motivo": "cta"})

    # 2) Fusionar ventanas contiguas del mismo tipo (evita "cambios" invisibles),
    #    salvo que la fusión supere el máximo del tipo: dos split seguidos llevan
    #    gráficos distintos, así que el cambio sí se ve.
    maximo = {"split": v.split_s[1], "full": v.full_s[1]}
    fusion = [brutas[0]]
    for b in brutas[1:]:
        ultima = fusion[-1]
        if (b["tipo"] == ultima["tipo"] and b["motivo"] != "cta"
                and b["fin"] - ultima["inicio"] <= maximo[b["tipo"]]):
            fusion[-1]["fin"] = b["fin"]
        else:
            fusion.append(b)

    # 3) Punch-in en los full más largos que max_sin_cambio_s.
    ventanas = []
    for b in fusion:
        if b["tipo"] == "full" and b["fin"] - b["inicio"] > v.max_sin_cambio_s:
            t, zoom = b["inicio"], 1.0
            while b["fin"] - t > v.max_sin_cambio_s:
                corte = elegir_limite(cands, t, (v.full_s[0], v.max_sin_cambio_s), b["fin"])
                ventanas.append({**b, "inicio": t, "fin": corte, "zoom": zoom})
                t, zoom = corte, (ZOOM_PUNCH if zoom == 1.0 else 1.0)
            ventanas.append({**b, "inicio": t, "zoom": zoom})
        else:
            ventanas.append({**b, "zoom": 1.0})

    # 3b) Punch-in alterno: cada ventana full cambia de zoom respecto a la full anterior.
    if v.punch_alterno:
        k = punch_inicio  # variantes: el patrón de zoom empieza al revés
        for w in ventanas:
            if w["tipo"] == "full" and w["zoom"] == 1.0:
                w["zoom"] = ZOOM_PUNCH if k % 2 else 1.0
                k += 1

    # 4) Recorte estático por ventana, destellos y avisos.
    for i, w in enumerate(ventanas):
        w["inicio"], w["fin"] = round(w["inicio"], 3), round(w["fin"], 3)
        zona = perfil.zonas_seguras.inferior
        rec = recorte_estatico(caras, edl, w["inicio"], w["fin"], w["tipo"], w["zoom"], zona)
        if rec is None and w["tipo"] == "split":
            avisos.append(f"{w['inicio']:.2f}-{w['fin']:.2f}s: split sin cara detectable -> full")
            w["tipo"] = "full"
            rec = recorte_estatico(caras, edl, w["inicio"], w["fin"], "full", w["zoom"], zona)
        if rec is None:
            avisos.append(f"{w['inicio']:.2f}-{w['fin']:.2f}s: sin cara, recorte centrado")
            W, H = caras["ancho"], caras["alto"]
            h = min(H, W * 16 / 9)
            rec = [int((W - h * 9 / 16) / 2) // 2 * 2, int((H - h) / 2) // 2 * 2, int(h * 9 / 16) // 2 * 2, int(h) // 2 * 2]
        w["recorte"] = rec
        # Destello solo en cambios de bloque (cambio de beat del EDL o entrada al CTA).
        w["destello"] = perfil.layout.transicion == "destello" and i > 0 and (
            w["motivo"] == "cta" or cambia_beat(edl, ventanas[i - 1]["fin"]))
    return {"ancho": SALIDA_W, "alto": SALIDA_H, "duracion": duracion, "fin_gancho": t_gancho,
            "ventanas": ventanas, "avisos": avisos}


def cambia_beat(edl: dict, t_salida: float) -> bool:
    offset = 0.0
    for a, b in zip(edl["ranges"], edl["ranges"][1:]):
        offset += a["end"] - a["start"]
        if abs(offset - t_salida) < 0.05:
            return a.get("beat") != b.get("beat")
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", type=Path, required=True)
    ap.add_argument("--transcripcion", type=Path, required=True)
    ap.add_argument("--caras", type=Path, required=True)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--momentos", type=Path)
    ap.add_argument("--proporcion-split", type=float, help="sustituye la del perfil (variantes)")
    ap.add_argument("--punch-inicio", type=int, default=0, choices=[0, 1], help="1 = el primer full va con zoom")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    momentos = leer(args.momentos)["momentos"] if args.momentos else None
    plan = planificar(leer(args.edl), leer(args.transcripcion), leer(args.caras), cargar(args.perfil), momentos,
                      args.proporcion_split, args.punch_inicio)
    args.salida.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"guardado: {args.salida} — {len(plan['ventanas'])} ventanas, gancho hasta {plan['fin_gancho']} s")
    for w in plan["ventanas"]:
        print(f"  {w['inicio']:6.2f}-{w['fin']:6.2f} ({w['fin'] - w['inicio']:4.2f}s) {w['tipo']:5} "
              f"zoom {w['zoom']:.2f} {'✦' if w['destello'] else ' '} {w['motivo']}")
    for a in plan["avisos"]:
        print(f"  ⚠️ {a}")


if __name__ == "__main__":
    main()
