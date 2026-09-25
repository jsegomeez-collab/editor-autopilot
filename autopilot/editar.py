"""Edita un vídeo de principio a fin sin intervención (modo individual y motor de la cola).

Flujo: normalizar → transcribir (caché) → corregir → [Claude: cortes] → EDL → cara → layout →
[Claude: gráficos + stickers] → render de plantillas → subtítulos → SFX → composición → mezcla →
exportación → QA → entrega (revision/<perfil>/ y carpeta de salida del usuario).

Informa del progreso en <trabajo>/estado.json (lo lee el frontend).

Con --variantes N ≥ 2 genera además V2…VN: variantes creativas reales para tests A/B (otro gancho, otros
gráficos, subtítulos, música, densidad de SFX, zoom y, en V3/V6, versión corta de 15–30 s) + variantes.csv.
No incluye técnicas para camuflar duplicados ni tocar metadatos (excluido por el encargo).

Uso:
  python autopilot/editar.py <video> --perfil perfiles/jose [--salida ~/Movies/Reels] [--variantes 4]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "pipeline"))
sys.path.insert(0, str(RAIZ / "autopilot"))
from decidir import LimiteDeUso, decidir_cortes, decidir_graficos, decidir_titulo, decidir_version_corta  # noqa: E402,F401
from perfil import cargar  # noqa: E402

BASE = Path.home() / "VideoAutopilot"
PY = sys.executable
CACHE = BASE / "cache_transcripciones"
ETAPAS = {  # etapa -> progreso (%) al empezarla
    "normalizando": 3, "transcribiendo": 12, "decidiendo_cortes": 22, "cara_y_layout": 32,
    "decidiendo_graficos": 40, "renderizando_graficos": 50, "montaje": 72, "audio": 84,
    "control_calidad": 92, "terminado": 100,
}


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "video"


def paso(*args: str | Path) -> str:
    """Ejecuta un script del pipeline con el Python del proyecto; si falla, lanza con su salida."""
    r = subprocess.run([PY, *map(str, args)], capture_output=True, text=True, cwd=RAIZ)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(str(args[0])).name}: {(r.stderr or r.stdout)[-1500:]}")
    return r.stdout


class Progreso:
    """Progreso global: con N versiones, cada una ocupa su tramo de 0–100 %."""

    def __init__(self, trabajo: Path, avisar=None):
        self.ruta = trabajo / "estado.json"
        self.avisar = avisar
        self.version, self.total = 1, 1

    def __call__(self, etapa: str, mensaje: str = "", progreso: int | None = None) -> None:
        local = progreso if progreso is not None else ETAPAS[etapa]
        comun = ETAPAS["decidiendo_cortes"]  # lo común (normalizar, transcribir) solo cuenta una vez
        if self.total > 1 and self.version > 1:
            local = comun + (100 - comun) * ((self.version - 1) + (local - comun) / (100 - comun)) / self.total
        elif self.total > 1:
            local = local if local <= comun else comun + (100 - comun) * (local - comun) / (100 - comun) / self.total
        if self.total > 1 and etapa != "terminado":
            mensaje = f"Versión {self.version}/{self.total} · {mensaje}"
        estado = {"etapa": etapa, "progreso": int(min(100 if etapa == "terminado" else 99, local)),
                  "mensaje": mensaje, "hora": time.strftime("%Y-%m-%dT%H:%M:%S"), "trabajo": str(self.ruta.parent)}
        self.ruta.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
        if self.avisar:
            self.avisar(estado)


# ---------- ayudas ----------

def texto_ventanas(layout: dict, palabras: list[dict]) -> str:
    lineas = []
    for i, v in enumerate(layout["ventanas"]):
        tipo = "CTA (full)" if v.get("motivo") == "cta" else v["tipo"]
        dichas = " ".join(f"{w['text']}@{w['o_start'] - v['inicio']:.2f}" for w in palabras
                          if v["inicio"] <= w["o_start"] < v["fin"])
        lineas.append(f"{i} | {tipo} | {v['inicio']:.2f}–{v['fin']:.2f} | {dichas}")
    return "\n".join(lineas)


STICKER_Y = {"motions": 470, "titulo": 760}  # en «título», junto a la cara bajo la franja


def construir_graficos(dec: dict, layout: dict, sticker_y: int = 470) -> tuple[list[dict], list[str]]:
    """Convierte la respuesta de Claude en graficos.json: ventana -> tiempos; stickers ajustados a su ventana full."""
    vs, graficos, notas = layout["ventanas"], [], []
    usadas = set()
    for g in dec.get("graficos", []):
        i = g["ventana"]
        if not 0 <= i < len(vs) or i in usadas:
            notas.append(f"gráfico descartado: ventana {i} inexistente o repetida")
            continue
        v = vs[i]
        if v["tipo"] != "split" and v.get("motivo") != "cta":
            notas.append(f"gráfico descartado: la ventana {i} es full (usa stickers)")
            continue
        usadas.add(i)
        graficos.append({"id": f"v{i:02d}", "plantilla": g["plantilla"], "inicio": v["inicio"],
                         "duracion": round(v["fin"] - v["inicio"], 3), "datos": g["datos"]})
    fin_previo = -1.0
    for j, s in enumerate(sorted(dec["stickers"], key=lambda s: s["inicio"])):
        v = next((w for w in vs if w["inicio"] <= s["inicio"] < w["fin"]), None)
        if not v or v["tipo"] not in ("full", "banda") or v.get("motivo") == "cta" or s["inicio"] < fin_previo:
            notas.append(f"sticker {s.get('icono') or s.get('archivo')} a {s['inicio']:.2f}s descartado (fuera de ventana o solapado)")
            continue
        dur = round(min(s["duracion"], v["fin"] - s["inicio"] - 0.02, 1.4), 3)
        if dur < 0.45:
            continue
        datos = {"lado": s["lado"], "rotulo": s.get("rotulo", ""), "t_aterrizaje": min(0.25, dur - 0.2), "y": sticker_y}
        if s.get("archivo"):
            datos["archivo"] = s["archivo"]
        elif s.get("icono"):
            datos["icono"] = s["icono"]
        else:
            continue
        if s.get("sonido"):
            datos["sonido"] = s["sonido"]
        graficos.append({"id": f"s{j:02d}", "plantilla": "sticker", "inicio": s["inicio"], "duracion": dur, "datos": datos})
        fin_previo = s["inicio"] + dur
    return graficos, notas


def validar_graficos(graficos: list[dict], perfil, edl: dict, corr: dict) -> list[str]:
    from render_plantillas import validar
    errores = []
    for g in graficos:
        try:
            validar(g, perfil.plantillas_permitidas, edl, corr)
        except Exception as e:  # jsonschema.ValidationError, ValueError…
            errores.append(f"{g['id']} ({g['plantilla']}, ventana a {g['inicio']:.2f}s): {str(e).splitlines()[0]}")
    return errores


def con_glosario(texto: str, perfil_dir: Path, idioma: str) -> str:
    """Aplica glosario y formato de cifras a un texto suelto (p. ej. el titular del gancho)."""
    from corregir_transcripcion import cargar_glosario, corregir
    falsa = {"words": [{"text": t, "start": i, "end": i + 0.5, "type": "word"} for i, t in enumerate(texto.split())]}
    return corregir(falsa, cargar_glosario(perfil_dir / "glosario.yaml"), idioma)["text"]


def respaldo(g: dict, motivo: str) -> dict:
    """Gráfico seguro cuando Claude no da uno válido: icono genérico, sin texto ni cifras."""
    return {**g, "plantilla": "icono", "datos": {"icono": "sparkles", "movimiento": "dibujar", "t_aterrizaje": 0.5},
            "nota_qa": f"gráfico de respaldo ({motivo})"}


# ---------- variantes ----------

def plan_variante(k: int, perfil, cortes: dict) -> dict:
    """Qué cambia en la variante k (k ≥ 2). Cada variante cambia varios ejes a la vez y son todas distintas."""
    alternativos = cortes.get("titulares_alternativos") or [cortes["titular_gancho"]]
    permitidos = list(perfil.subtitulos.estilos_permitidos)
    defecto = perfil.subtitulos.estilo_por_defecto
    estilos = [e for e in permitidos if e != defecto] + [defecto]
    return {
        "titular": alternativos[(k - 2) % len(alternativos)],
        "estilo_subtitulos": estilos[(k - 2) % len(estilos)],
        "estado_musica": cortes.get("estado_musica_alternativo", cortes["estado_musica"]) if k % 2 else cortes["estado_musica"],
        "densidad_sfx": "media" if k % 2 == 0 else "alta",
        "punch_inicio": k % 2,
        "proporcion_split": 0.5 if k % 3 == 1 else None,
        "corta": k % 3 == 0,  # V3, V6: versión corta de 15–30 s con los beats más fuertes
    }


def resumen_graficos(edit: Path) -> str:
    """Lo que ya se usó en una versión (para pedir a Claude algo distinto en la siguiente)."""
    g = json.loads((edit / "graficos.json").read_text())["graficos"]
    partes = []
    for x in g:
        d = x["datos"]
        iconos = [v for k, v in d.items() if "icono" in k and isinstance(v, str)] + d.get("iconos", [])
        partes.append(f"{x['inicio']:.1f}s {x['plantilla']} {'/'.join(iconos)}".strip())
    return "; ".join(partes)


def tramos_con_texto(seleccion: list[dict], trans: dict) -> str:
    ws = [w for w in trans["words"] if w.get("type") == "word"]
    return "\n".join(f"[{ws[t['desde']]['start']:.2f}-{ws[t['hasta']]['end']:.2f}] ({t['desde']}-{t['hasta']}) {t['beat']}: "
                     + " ".join(w["text"] for w in ws[t["desde"]:t["hasta"] + 1]) for t in seleccion)


def enlazar(origen: Path, destino: Path) -> None:
    """Copia ligera (enlace duro) de un archivo o carpeta: no ocupa disco extra."""
    if origen.is_dir():
        destino.mkdir(parents=True, exist_ok=True)
        for f in origen.iterdir():
            enlazar(f, destino / f.name)
    elif origen.exists() and not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            destino.hardlink_to(origen)
        except OSError:
            shutil.copy2(origen, destino)


# ---------- montaje de una versión ----------

def montar(t: Path, fuente: Path, trans_ruta: Path, corr_ruta: Path, caras: Path, perfil_dir: Path, perfil,
           cortes: dict, prog: Progreso, uso_claude: list, concurrencia: int, opciones: dict) -> dict:
    """Monta una versión en la carpeta t (EDL → layout → gráficos → render → subtítulos → SFX → composición →
    mezcla → exportación → QA). Devuelve veredicto, avisos y rutas. No limpia intermedios."""
    edit = t / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    enlazar(corr_ruta, edit / "transcripts_corregidas" / corr_ruta.name)
    corr = json.loads(corr_ruta.read_text())
    edl = json.loads((edit / "edl.json").read_text())
    titular = opciones.get("titular") or cortes["titular_gancho"]
    estilo_edicion = opciones.get("estilo", "motions")

    prog("cara_y_layout", "Encuadre y alternancia split/full")
    extra = []
    if opciones.get("proporcion_split"):
        extra += ["--proporcion-split", str(opciones["proporcion_split"])]
    paso(RAIZ / "pipeline/planificar_layout.py", "--edl", edit / "edl.json", "--transcripcion", corr_ruta,
         "--caras", caras, "--perfil", perfil_dir, "--punch-inicio", str(opciones.get("punch_inicio", 0)),
         "--estilo", estilo_edicion,
         *extra, "-o", edit / "layout.json")
    layout = json.loads((edit / "layout.json").read_text())

    prog("decidiendo_graficos", "Claude elige los motion graphics")
    from planificar_layout import palabras_en_salida
    ventanas_txt = texto_ventanas(layout, palabras_en_salida(edl, corr))
    errores, fallos = "", []
    titulo_video = {}
    for _ in range(2):
        if estilo_edicion == "titulo":
            dec = decidir_titulo(ventanas_txt, perfil, perfil_dir, cortes["palabra_cta"], uso_claude, errores,
                                 opciones.get("evitar", ""))
            (edit / "decision_claude.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1))  # diagnóstico
            titulo_video = {"titulo": con_glosario(opciones.get("titulo") or dec["titulo"], perfil_dir, perfil.identidad.idioma),
                            "destacado": dec["destacado"],
                            "alternativos": [con_glosario(x, perfil_dir, perfil.identidad.idioma) for x in dec["titulos_alternativos"]]}
            if opciones.get("titulo"):  # variante: su título manda; el destacado se ajusta a él
                titulo_video["destacado"] = titulo_video["titulo"].split()[-1]
            ult = len(layout["ventanas"]) - 1
            dec = {"graficos": ([{"ventana": ult, "plantilla": "cta", "datos": {**dec["cta"], "t_aterrizaje": 0.8}}]
                                if dec.get("cta") else []), "stickers": dec["stickers"]}
        else:
            dec = decidir_graficos(ventanas_txt, perfil, perfil_dir, titular, cortes["palabra_cta"], uso_claude,
                                   errores, opciones.get("evitar", ""))
            (edit / "decision_claude.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1))  # diagnóstico
        graficos, notas = construir_graficos(dec, layout, STICKER_Y[estilo_edicion])
        for g in graficos:  # el gancho de cada versión es el suyo (Claude solo lo recibe como sugerencia)
            if g["plantilla"] == "gancho":
                g["datos"]["titular"] = titular
                marcadas = g["datos"].get("destacado", "").split()
                if not marcadas or not all(m.lower() in titular.lower() for m in marcadas):
                    g["datos"]["destacado"] = titular.split()[-1]
        fallos = validar_graficos(graficos, perfil, edl, corr)
        if not fallos:
            break
        errores = "\n".join(fallos)
    malos = {f.split(" ", 1)[0] for f in fallos}
    graficos = [respaldo(g, "no pasó la validación") if g["id"] in malos and g["plantilla"] != "sticker" else g
                for g in graficos if not (g["id"] in malos and g["plantilla"] == "sticker")]
    con_grafico = {g["id"] for g in graficos}
    for i, v in enumerate(layout["ventanas"]):  # toda ventana split lleva algo (en «título» no hay splits)
        if v["tipo"] == "split" and f"v{i:02d}" not in con_grafico:
            graficos.append(respaldo({"id": f"v{i:02d}", "inicio": v["inicio"], "duracion": round(v["fin"] - v["inicio"], 3)},
                                     "ventana sin gráfico"))
    (edit / "graficos.json").write_text(json.dumps({"graficos": graficos, "notas": notas, **titulo_video},
                                                   ensure_ascii=False, indent=1))

    prog("renderizando_graficos", f"{len(graficos)} gráficos")
    paso(RAIZ / "pipeline/render_plantillas.py", edit / "graficos.json", "--perfil", perfil_dir, "--edit", edit,
         "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--concurrencia", str(concurrencia))

    prog("montaje", "Subtítulos, capas y composición")
    estilo = opciones.get("estilo_subtitulos")
    extra_subs = (["--basico", "--titulo", titulo_video["titulo"], "--destacado", titulo_video["destacado"]]
                  if estilo_edicion == "titulo" else [])
    paso(RAIZ / "pipeline/subtitulos_ass.py", "--edl", edit / "edl.json", "--transcripcion", corr_ruta,
         "--layout", edit / "layout.json", "--perfil", perfil_dir, *(["--estilo", estilo] if estilo else []),
         *extra_subs, "-o", edit / "subtitulos.ass")
    dens = opciones.get("densidad_sfx") or ("alta" if estilo_edicion == "titulo" else None)  # «título»: SFX muy frecuentes
    paso(RAIZ / "pipeline/planificar_sfx.py", "--layout", edit / "layout.json", "--graficos", edit / "graficos.json",
         "--perfil", perfil_dir, "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--semilla", t.name,
         *(["--densidad", dens] if dens else []), "-o", edit / "sfx_timeline.json")
    paso(RAIZ / "pipeline/componer.py", "--edl", edit / "edl.json", "--layout", edit / "layout.json",
         "--perfil", perfil_dir, "--overlays", edit / "overlays.json", "--ass", edit / "subtitulos.ass",
         "--fontsdir", perfil_dir / "fuentes", "-o", edit / "compuesto.mp4")

    estado_musica = opciones.get("estado_musica") or cortes["estado_musica"]
    prog("audio", f"Voz, música ({estado_musica}) y efectos")
    paso(RAIZ / "pipeline/mezcla_audio.py", "--video", edit / "base.mp4", "--perfil", perfil_dir,
         "--estado", estado_musica, "--sfx", edit / "sfx_timeline.json", "--trabajo", t.name,
         "--registrar-uso", "-o", edit / "mezcla.wav")

    prog("control_calidad", "Exportando y comprobando")
    paso(RAIZ / "pipeline/exportar.py", "--video", edit / "compuesto.mp4", "--audio", edit / "mezcla.wav",
         "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--graficos", edit / "graficos.json",
         "--perfil", perfil_dir, "--sufijo", opciones.get("sufijo", ""),
         *(["--nombre-base", opciones.get("nombre_base") or (time.strftime("%Y%m%d") + "_" + perfil_dir.name + "_"
                                                             + slug(titulo_video["titulo"]))]
           if opciones.get("nombre_base") or titulo_video else []), "-o", t / "salida")
    salida_qa = paso(RAIZ / "pipeline/qa.py", "--trabajo", t, "--perfil", perfil_dir, "--sin-limpieza")
    veredicto = "REVISAR" if "REVISAR" in salida_qa.splitlines()[0] else "LISTO"
    entregado = Path(salida_qa.strip().splitlines()[-1].split("entregado: ", 1)[-1])
    informe = (t / "salida" / "informe_qa.md").read_text(encoding="utf-8")
    musica = json.loads((edit / "mezcla.json").read_text()).get("musica", {})
    return {"veredicto": veredicto, "final": entregado, "portada": t / "salida" / "portada.jpg",
            "avisos": [l[4:].strip() for l in informe.splitlines() if l.startswith("- ⚠️")],
            "duracion_s": json.loads((edit / "edl.json").read_text())["total_duration_s"],
            "titular": titulo_video.get("titulo") or titular, "estilo_edicion": estilo_edicion,
            "titulos_alternativos": titulo_video.get("alternativos", []),
            "estilo_subtitulos": estilo or perfil.subtitulos.estilo_por_defecto,
            "estado_musica": estado_musica, "pista": musica.get("archivo"),
            "densidad_sfx": dens or perfil.audio.densidad_sfx,
            "graficos": len([g for g in graficos if g["plantilla"] != "sticker"]),
            "stickers": len([g for g in graficos if g["plantilla"] == "sticker"])}


# ---------- flujo ----------

def editar(video: Path, perfil_dir: Path, carpeta_salida: Path | None = None, avisar=None,
           mover_original: bool = False, concurrencia: int = 2, variantes: int = 1, estilo: str = "motions") -> dict:
    from qa import limpiar_trabajo
    perfil = cargar(perfil_dir)
    inicio_total = time.time()
    variantes = max(1, min(6, int(variantes)))
    trabajo = BASE / "trabajos" / f"{time.strftime('%Y%m%d-%H%M')}_{slug(video.stem)}"
    edit = trabajo / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    prog = Progreso(trabajo, avisar)
    prog.total = variantes
    uso_claude: list = []
    estilo = estilo if estilo in ("motions", "titulo") else "motions"
    resumen = {"trabajo": str(trabajo), "video": video.name, "perfil": perfil_dir.name, "variantes_pedidas": variantes,
               "estilo_edicion": estilo}

    # 1) Original: se mueve (nunca se copia ni se borra) a trabajos/<id>/original/.
    prog("normalizando", "Preparando la copia de trabajo")
    original = trabajo / "original" / video.name
    original.parent.mkdir(exist_ok=True)
    if mover_original:
        shutil.move(str(video), original)
    else:
        original = video
    fuente = Path(paso(RAIZ / "pipeline/preparar_fuente.py", original, "--destino", trabajo / "fuente").strip().splitlines()[-1])

    # 2) Transcripción (caché global por hash) + glosario y cifras.
    en_cache = (CACHE / f"{fuente.stem}.json").exists()
    prog("transcribiendo", "Desde la caché" if en_cache else "ElevenLabs Scribe")
    trans_ruta = Path(paso(RAIZ / "pipeline/transcribir.py", fuente, "--edit", edit).strip().splitlines()[-1])
    dur_fuente = json.loads((trabajo / "fuente" / "ficha.json").read_text())["duracion_s"]
    resumen["minutos_transcritos"] = 0 if en_cache else round(dur_fuente / 60, 2)
    corr_ruta = edit / "transcripts_corregidas" / trans_ruta.name
    paso(RAIZ / "pipeline/corregir_transcripcion.py", trans_ruta, "-o", corr_ruta,
         "--glosario", perfil_dir / "glosario.yaml", "--idioma", perfil.identidad.idioma)
    trans = json.loads(trans_ruta.read_text())

    # 3) Cortes (Claude) → EDL validado por construir_edl.py.
    prog("decidiendo_cortes", "Claude decide qué se queda")
    correcciones = (perfil_dir / "correcciones.md").read_text(encoding="utf-8") if (perfil_dir / "correcciones.md").exists() else ""
    errores = ""
    for intento in range(2):
        cortes = decidir_cortes(trans, perfil, correcciones, uso_claude, errores)
        (edit / "seleccion.json").write_text(json.dumps({"tramos": cortes["tramos"]}, ensure_ascii=False, indent=1))
        try:
            paso(RAIZ / "pipeline/construir_edl.py", trans_ruta, edit / "seleccion.json", "--video", fuente,
                 "--ritmo", perfil.ritmo, "-o", edit / "edl.json")
            break
        except RuntimeError as e:
            errores = str(e)[-600:]
            if intento == 1:
                raise
    cortes["titular_gancho"] = con_glosario(cortes["titular_gancho"], perfil_dir, perfil.identidad.idioma)
    cortes["titulares_alternativos"] = [con_glosario(x, perfil_dir, perfil.identidad.idioma)
                                        for x in cortes.get("titulares_alternativos", [])]
    (edit / "project.md").write_text(
        f"## Session 1 — {time.strftime('%Y-%m-%d')}\n**Strategy:** {cortes['estrategia']}\n"
        f"**Decisions:** ritmo {perfil.ritmo}; música {cortes['estado_musica']}; CTA «{cortes['palabra_cta']}»; "
        f"gancho «{cortes['titular_gancho']}»; variantes: {variantes}. Estrategia aprobada por el perfil "
        f"(sin conversación, ver PLAN.md).\n**Reasoning log:** {len(cortes['tramos'])} tramos elegidos por Claude.\n"
        f"**Outstanding:** —\n", encoding="utf-8")
    paso(RAIZ / "pipeline/detectar_cara.py", fuente, "-o", edit / "caras.json")

    # 4) Versión 1 (la edición normal).
    sufijo = "_V1" if variantes > 1 else ""
    versiones = [{"variante": "V1" if variantes > 1 else "", "cambios": "edición base",
                  **montar(trabajo, fuente, trans_ruta, corr_ruta, edit / "caras.json", perfil_dir, perfil, cortes,
                           prog, uso_claude, concurrencia, {"sufijo": sufijo, "estilo": estilo})}]

    # 5) Variantes creativas V2…Vn (reutilizan transcripción, EDL y cara; nunca re-transcriben).
    for k in range(2, variantes + 1):
        prog.version = k
        plan = plan_variante(k, perfil, cortes)
        plan["estilo"] = estilo
        if estilo == "titulo":  # en «título» la variante cambia el título en vez del gancho
            alts = versiones[0].get("titulos_alternativos") or [versiones[0]["titular"]]
            plan["titulo"] = alts[(k - 2) % len(alts)]
            plan["titular"] = plan["titulo"]
        t = trabajo / "variantes" / f"V{k}"
        (t / "edit").mkdir(parents=True, exist_ok=True)
        if plan["corta"]:
            prog("decidiendo_cortes", "Claude elige los beats para la versión corta")
            err = ""
            for intento in range(2):
                corta = decidir_version_corta(tramos_con_texto(cortes["tramos"], trans), (15, 30), uso_claude, err)
                (t / "edit" / "seleccion.json").write_text(json.dumps({"tramos": corta["tramos"]}, ensure_ascii=False))
                try:
                    paso(RAIZ / "pipeline/construir_edl.py", trans_ruta, t / "edit" / "seleccion.json", "--video", fuente,
                         "--ritmo", perfil.ritmo, "-o", t / "edit" / "edl.json")
                    dur = json.loads((t / "edit" / "edl.json").read_text())["total_duration_s"]
                    if dur <= 35:
                        break
                    err = f"La versión dura {dur:.1f} s: tiene que durar entre 15 y 30 s."
                except RuntimeError as e:
                    err = str(e)[-600:]
                if intento == 1:
                    plan["corta"] = False  # no se consiguió: variante de duración completa
            if not plan["corta"]:
                enlazar(edit / "edl.json", t / "edit" / "edl.json")
        else:
            enlazar(edit / "edl.json", t / "edit" / "edl.json")
        if not plan["corta"]:  # mismo EDL: se reutilizan los segmentos ya extraídos (sin disco extra)
            enlazar(edit / "clips", t / "edit" / "clips")
        # Mismo nombre base que la V1 para que las versiones de un vídeo vayan juntas (…_V1, …_V2, …).
        nombre_base = versiones[0]["final"].stem.removeprefix("REVISAR_").removesuffix("_V1")
        plan.update(sufijo=f"_V{k}", evitar=resumen_graficos(edit), nombre_base=nombre_base)
        r = montar(t, fuente, trans_ruta, corr_ruta, edit / "caras.json", perfil_dir, perfil, cortes, prog,
                   uso_claude, concurrencia, plan)
        cambios = [f"{'título' if estilo == 'titulo' else 'gancho'} «{plan['titular']}»", f"subtítulos {plan['estilo_subtitulos']}",
                   f"música {plan['estado_musica']}", f"SFX {plan['densidad_sfx']}",
                   "zoom invertido" if plan["punch_inicio"] else "zoom base", "gráficos distintos"]
        if plan.get("proporcion_split"):
            cambios.append("más cámara")
        if plan["corta"]:
            cambios.insert(0, "versión corta")
        versiones.append({"variante": f"V{k}", "cambios": "; ".join(cambios), **r})

    # 6) Entrega a la carpeta del usuario + variantes.csv + limpieza.
    prog.version = variantes
    peor = "REVISAR" if any(v["veredicto"] == "REVISAR" for v in versiones) else "LISTO"
    for v in versiones:
        v["salida_usuario"] = None
        if carpeta_salida:
            carpeta = Path(carpeta_salida).expanduser() / ("revisar" if v["veredicto"] == "REVISAR" else "")
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / v["final"].name.removeprefix("REVISAR_")
            shutil.copy2(v["final"], destino)
            v["salida_usuario"] = destino
    if variantes > 1:
        import csv
        filas = [{"archivo": Path(v["salida_usuario"] or v["final"]).name, "variante": v["variante"],
                  "veredicto": v["veredicto"], "duracion_s": round(v["duracion_s"], 1), "gancho": v["titular"],
                  "subtitulos": v["estilo_subtitulos"], "estado_musica": v["estado_musica"], "pista": v["pista"],
                  "densidad_sfx": v["densidad_sfx"], "graficos": v["graficos"], "stickers": v["stickers"],
                  "que_cambia": v["cambios"]} for v in versiones]
        destinos_csv = [trabajo / "variantes.csv"]
        if carpeta_salida:
            destinos_csv.append(Path(carpeta_salida).expanduser() / f"{Path(versiones[0]['final']).stem.removeprefix('REVISAR_').removesuffix('_V1')}_variantes.csv")
        for d in destinos_csv:
            with d.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0]))
                w.writeheader()
                w.writerows(filas)
    limpiar_trabajo(trabajo)

    v1 = versiones[0]
    resumen.update({
        "veredicto": peor, "avisos": [f"{v['variante'] or 'vídeo'}: {a}" if variantes > 1 else a
                                      for v in versiones for a in v["avisos"]],
        "final": str(v1["final"]), "salida_usuario": str(v1["salida_usuario"]) if v1["salida_usuario"] else None,
        "portada": str(v1["portada"]), "duracion_video_s": v1["duracion_s"],
        "versiones": [{"variante": v["variante"], "final": str(v["final"]), "veredicto": v["veredicto"],
                       "salida_usuario": str(v["salida_usuario"]) if v["salida_usuario"] else None,
                       "duracion_s": v["duracion_s"], "cambios": v["cambios"]} for v in versiones],
        "duracion_ejecucion_s": round(time.time() - inicio_total, 1), "uso_claude": uso_claude,
        "coste_claude_estimado_usd": round(sum(u.get("coste_usd_estimado") or 0 for u in uso_claude), 4),
        "modelos_claude": sorted({m for u in uso_claude for m in u["modelos"]}),
    })
    (trabajo / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    txt = f"{variantes} versiones · " if variantes > 1 else ""
    prog("terminado", f"{txt}{'⚠️ Revisar' if peor == 'REVISAR' else '✅ Listo'} en {resumen['duracion_ejecucion_s']:.0f} s")
    return resumen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--salida", type=Path, help="carpeta donde copiar el vídeo final")
    ap.add_argument("--variantes", type=int, default=1, help="1 = solo la edición; 2–6 = variantes creativas A/B")
    ap.add_argument("--estilo", choices=["motions", "titulo"], default="motions",
                    help="motions = motion graphics en split; titulo = título fijo arriba, stickers y subtítulos básicos")
    ap.add_argument("--mover-original", action="store_true")
    args = ap.parse_args()
    r = editar(args.video, args.perfil, args.salida,
               avisar=lambda e: print(f"[{e['progreso']:3d}%] {e['etapa']}: {e['mensaje']}", flush=True),
               mover_original=args.mover_original, variantes=args.variantes, estilo=args.estilo)
    print(json.dumps({k: r[k] for k in ("veredicto", "final", "salida_usuario", "duracion_ejecucion_s",
                                        "coste_claude_estimado_usd", "modelos_claude", "avisos", "versiones")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
