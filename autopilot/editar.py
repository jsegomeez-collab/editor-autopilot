"""Edita un vídeo de principio a fin sin intervención (modo individual y motor de la cola).

Flujo: normalizar → transcribir (caché) → corregir → [Claude: cortes] → EDL → cara → layout →
[Claude: gráficos + stickers] → render de plantillas → subtítulos → SFX → composición → mezcla →
exportación → QA → entrega (revision/<perfil>/ y carpeta de salida del usuario).

Informa del progreso en <trabajo>/estado.json (lo lee el frontend).

Uso:
  python autopilot/editar.py <video> --perfil perfiles/jose [--salida ~/Movies/Reels] [--mover-original]
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
from decidir import LimiteDeUso, decidir_cortes, decidir_graficos  # noqa: E402,F401
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
    def __init__(self, trabajo: Path, avisar=None):
        self.ruta = trabajo / "estado.json"
        self.avisar = avisar

    def __call__(self, etapa: str, mensaje: str = "", progreso: int | None = None) -> None:
        estado = {"etapa": etapa, "progreso": progreso if progreso is not None else ETAPAS[etapa],
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


def construir_graficos(dec: dict, layout: dict) -> tuple[list[dict], list[str]]:
    """Convierte la respuesta de Claude en graficos.json: ventana -> tiempos; stickers ajustados a su ventana full."""
    vs, graficos, notas = layout["ventanas"], [], []
    usadas = set()
    for g in dec["graficos"]:
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
        if not v or v["tipo"] != "full" or v.get("motivo") == "cta" or s["inicio"] < fin_previo:
            notas.append(f"sticker {s['icono']} a {s['inicio']:.2f}s descartado (fuera de una ventana full o solapado)")
            continue
        dur = round(min(s["duracion"], v["fin"] - s["inicio"] - 0.02, 1.4), 3)
        if dur < 0.45:
            continue
        datos = {"icono": s["icono"], "lado": s["lado"], "rotulo": s["rotulo"], "t_aterrizaje": min(0.25, dur - 0.2)}
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


# ---------- flujo ----------

def editar(video: Path, perfil_dir: Path, carpeta_salida: Path | None = None, avisar=None,
           mover_original: bool = False, concurrencia: int = 2) -> dict:
    perfil = cargar(perfil_dir)
    inicio_total = time.time()
    trabajo = BASE / "trabajos" / f"{time.strftime('%Y%m%d-%H%M')}_{slug(video.stem)}"
    edit = trabajo / "edit"
    edit.mkdir(parents=True, exist_ok=True)
    prog = Progreso(trabajo, avisar)
    uso_claude: list = []
    resumen = {"trabajo": str(trabajo), "video": video.name, "perfil": perfil_dir.name}

    # 1) Original: se mueve (nunca se copia ni se borra) a trabajos/<id>/original/.
    prog("normalizando", "Preparando la copia de trabajo")
    original_dir = trabajo / "original"
    original_dir.mkdir(exist_ok=True)
    original = original_dir / video.name
    if mover_original:
        shutil.move(str(video), original)
    else:
        original = video
    fuente = Path(paso(RAIZ / "pipeline/preparar_fuente.py", original, "--destino", trabajo / "fuente").strip().splitlines()[-1])

    # 2) Transcripción (caché global por hash).
    en_cache = (CACHE / f"{fuente.stem}.json").exists()
    prog("transcribiendo", "Desde la caché" if en_cache else "ElevenLabs Scribe")
    trans_ruta = Path(paso(RAIZ / "pipeline/transcribir.py", fuente, "--edit", edit).strip().splitlines()[-1])
    dur_fuente = json.loads((trabajo / "fuente" / "ficha.json").read_text())["duracion_s"]
    resumen["minutos_transcritos"] = 0 if en_cache else round(dur_fuente / 60, 2)
    corr_ruta = edit / "transcripts_corregidas" / trans_ruta.name
    paso(RAIZ / "pipeline/corregir_transcripcion.py", trans_ruta, "-o", corr_ruta,
         "--glosario", perfil_dir / "glosario.yaml", "--idioma", perfil.identidad.idioma)
    trans = json.loads(trans_ruta.read_text())
    corr = json.loads(corr_ruta.read_text())

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
    (edit / "project.md").write_text(
        f"## Session 1 — {time.strftime('%Y-%m-%d')}\n**Strategy:** {cortes['estrategia']}\n"
        f"**Decisions:** ritmo {perfil.ritmo}; música {cortes['estado_musica']}; CTA «{cortes['palabra_cta']}»; "
        f"gancho «{cortes['titular_gancho']}». Estrategia aprobada por el perfil (sin conversación, ver PLAN.md).\n"
        f"**Reasoning log:** {len(cortes['tramos'])} tramos elegidos por Claude.\n**Outstanding:** —\n", encoding="utf-8")
    edl = json.loads((edit / "edl.json").read_text())
    cortes["titular_gancho"] = con_glosario(cortes["titular_gancho"], perfil_dir, perfil.identidad.idioma)

    # 4) Cara + layout.
    prog("cara_y_layout", "Encuadre y alternancia split/full")
    paso(RAIZ / "pipeline/detectar_cara.py", fuente, "-o", edit / "caras.json")
    paso(RAIZ / "pipeline/planificar_layout.py", "--edl", edit / "edl.json", "--transcripcion", corr_ruta,
         "--caras", edit / "caras.json", "--perfil", perfil_dir, "-o", edit / "layout.json")
    layout = json.loads((edit / "layout.json").read_text())

    # 5) Gráficos + stickers (Claude) con validación y un reintento con los errores.
    prog("decidiendo_graficos", "Claude elige los motion graphics")
    from planificar_layout import palabras_en_salida
    ventanas_txt = texto_ventanas(layout, palabras_en_salida(edl, corr))
    errores = ""
    for intento in range(2):
        dec = decidir_graficos(ventanas_txt, perfil, perfil_dir, cortes["titular_gancho"], cortes["palabra_cta"],
                               uso_claude, errores)
        graficos, notas = construir_graficos(dec, layout)
        fallos = validar_graficos(graficos, perfil, edl, corr)
        if not fallos:
            break
        errores = "\n".join(fallos)
    malos = {f.split(" ", 1)[0] for f in fallos} if fallos else set()
    graficos = [respaldo(g, "no pasó la validación") if g["id"] in malos and g["plantilla"] != "sticker" else g
                for g in graficos if not (g["id"] in malos and g["plantilla"] == "sticker")]
    con_grafico = {g["id"] for g in graficos}
    for i, v in enumerate(layout["ventanas"]):  # toda ventana split lleva algo
        if v["tipo"] == "split" and f"v{i:02d}" not in con_grafico:
            graficos.append(respaldo({"id": f"v{i:02d}", "inicio": v["inicio"], "duracion": round(v["fin"] - v["inicio"], 3)},
                                     "ventana sin gráfico"))
    (edit / "graficos.json").write_text(json.dumps({"graficos": graficos, "notas": notas}, ensure_ascii=False, indent=1))

    # 6) Render de plantillas (procesos en paralelo).
    prog("renderizando_graficos", f"{len(graficos)} gráficos")
    paso(RAIZ / "pipeline/render_plantillas.py", edit / "graficos.json", "--perfil", perfil_dir, "--edit", edit,
         "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--concurrencia", str(concurrencia))

    # 7) Subtítulos + SFX + composición en una pasada.
    prog("montaje", "Subtítulos, capas y composición")
    paso(RAIZ / "pipeline/subtitulos_ass.py", "--edl", edit / "edl.json", "--transcripcion", corr_ruta,
         "--layout", edit / "layout.json", "--perfil", perfil_dir, "-o", edit / "subtitulos.ass")
    paso(RAIZ / "pipeline/planificar_sfx.py", "--layout", edit / "layout.json", "--graficos", edit / "graficos.json",
         "--perfil", perfil_dir, "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--semilla", trabajo.name,
         "-o", edit / "sfx_timeline.json")
    paso(RAIZ / "pipeline/componer.py", "--edl", edit / "edl.json", "--layout", edit / "layout.json",
         "--perfil", perfil_dir, "--overlays", edit / "overlays.json", "--ass", edit / "subtitulos.ass",
         "--fontsdir", perfil_dir / "fuentes", "-o", edit / "compuesto.mp4")

    # 8) Audio.
    prog("audio", f"Voz, música ({cortes['estado_musica']}) y efectos")
    paso(RAIZ / "pipeline/mezcla_audio.py", "--video", edit / "base.mp4", "--perfil", perfil_dir,
         "--estado", cortes["estado_musica"], "--sfx", edit / "sfx_timeline.json", "--trabajo", trabajo.name,
         "--registrar-uso", "-o", edit / "mezcla.wav")

    # 9) Exportación + QA + entrega.
    prog("control_calidad", "Exportando y comprobando")
    paso(RAIZ / "pipeline/exportar.py", "--video", edit / "compuesto.mp4", "--audio", edit / "mezcla.wav",
         "--edl", edit / "edl.json", "--transcripcion", corr_ruta, "--graficos", edit / "graficos.json",
         "--perfil", perfil_dir, "-o", trabajo / "salida")
    salida_qa = paso(RAIZ / "pipeline/qa.py", "--trabajo", trabajo, "--perfil", perfil_dir)
    veredicto = "REVISAR" if "REVISAR" in salida_qa.splitlines()[0] else "LISTO"
    entregado = Path(salida_qa.strip().splitlines()[-1].split("entregado: ", 1)[-1])
    informe = (trabajo / "salida" / "informe_qa.md").read_text(encoding="utf-8")
    avisos = [l[4:].strip() for l in informe.splitlines() if l.startswith("- ⚠️")]

    destino_usuario = None
    if carpeta_salida:
        carpeta = Path(carpeta_salida).expanduser() / ("revisar" if veredicto == "REVISAR" else "")
        carpeta.mkdir(parents=True, exist_ok=True)
        destino_usuario = carpeta / entregado.name.removeprefix("REVISAR_")
        shutil.copy2(entregado, destino_usuario)

    resumen.update({
        "veredicto": veredicto, "avisos": avisos, "final": str(entregado),
        "salida_usuario": str(destino_usuario) if destino_usuario else None,
        "portada": str(trabajo / "salida" / "portada.jpg"), "duracion_video_s": edl["total_duration_s"],
        "duracion_ejecucion_s": round(time.time() - inicio_total, 1), "uso_claude": uso_claude,
        "coste_claude_estimado_usd": round(sum(u.get("coste_usd_estimado") or 0 for u in uso_claude), 4),
        "modelos_claude": sorted({m for u in uso_claude for m in u["modelos"]}),
    })
    (trabajo / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    prog("terminado", f"{'⚠️ Revisar' if veredicto == 'REVISAR' else '✅ Listo'} en {resumen['duracion_ejecucion_s']:.0f} s")
    return resumen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--salida", type=Path, help="carpeta donde copiar el vídeo final")
    ap.add_argument("--mover-original", action="store_true")
    args = ap.parse_args()
    r = editar(args.video, args.perfil, args.salida,
               avisar=lambda e: print(f"[{e['progreso']:3d}%] {e['etapa']}: {e['mensaje']}", flush=True),
               mover_original=args.mover_original)
    print(json.dumps({k: r[k] for k in ("veredicto", "final", "salida_usuario", "duracion_ejecucion_s",
                                        "coste_claude_estimado_usd", "modelos_claude", "avisos")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
