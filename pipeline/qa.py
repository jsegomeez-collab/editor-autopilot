"""Control de calidad automático y entrega a revision/ (sección 6.8).

Comprueba:
  - duración real vs EDL (±0,1 s); sin frames negros (blackdetect); sin silencios > 700 ms en la voz;
  - loudness a ±1 LU del objetivo y true peak ≤ −1 dBTP (sin clipping);
  - cara detectada en el punto medio de cada ventana (en split, en el panel inferior);
  - subtítulos dentro del área útil (fuera de las zonas seguras); los gráficos van por debajo
    de los subtítulos por construcción (subtítulos siempre los últimos en la cadena);
  - toda cifra de los gráficos se dice en su ventana; ningún término del glosario mal escrito en pantalla;
  - efectos dentro de la densidad del perfil y sin solapes; música del catálogo con licencia y no
    repetida en los últimos 5 vídeos del perfil;
  - duración frente a duracion_objetivo_max_s y avisos heredados (layout, gráficos).
Veredicto: ✅ LISTO o ⚠️ REVISAR (con timestamps y motivo). Ambos se copian a
~/VideoAutopilot/revision/<perfil>/ (los ⚠️ con prefijo REVISAR_). Nada se publica.
Después borra los intermedios regenerables del trabajo (clips/, música ajustada); conserva compuesto.mp4.

Uso:
  python pipeline/qa.py --trabajo <dir_trabajo> --perfil perfiles/jose [--sin-entrega]
  (lee de <trabajo>/edit: edl.json, layout.json, graficos.json, sfx_timeline.json, subtitulos.ass,
   mezcla.json, transcripts_corregidas/*.json, overlays.json y de <trabajo>/salida/exportacion.json)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402
from planificar_layout import palabras_en_salida  # noqa: E402
from planificar_sfx import SEPARACION_MIN  # noqa: E402
from render_plantillas import numeros_de_datos, numeros_dichos, textos  # noqa: E402

MODELO_CARA = Path(__file__).resolve().parent / "modelos" / "face_detection_yunet_2023mar.onnx"
REVISION = Path.home() / "VideoAutopilot" / "revision"
TOLERANCIA_DURACION = 0.1
SILENCIO_MAX = 0.7


def ff(*args: str) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", *args], capture_output=True, text=True).stderr


def sonda(ruta: Path) -> dict:
    return json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                      "-show_format", str(ruta)], capture_output=True, text=True, check=True).stdout)


class Informe:
    def __init__(self):
        self.ok: list[str] = []
        self.problemas: list[str] = []

    def comprobar(self, condicion: bool, bien: str, mal: str) -> None:
        (self.ok if condicion else self.problemas).append(bien if condicion else mal)


# ---------- comprobaciones ----------

def comprobar_tecnico(inf: Informe, final: Path, edl: dict, base: Path | None) -> None:
    s = sonda(final)
    v = next(x for x in s["streams"] if x["codec_type"] == "video")
    a = next(x for x in s["streams"] if x["codec_type"] == "audio")
    dur = float(s["format"]["duration"])
    esperado = edl["total_duration_s"]
    inf.comprobar(abs(dur - esperado) <= TOLERANCIA_DURACION, f"Duración {dur:.2f} s = EDL {esperado:.2f} s",
                  f"Duración {dur:.2f} s frente a EDL {esperado:.2f} s (> ±{TOLERANCIA_DURACION} s)")
    espec = (v["codec_name"] == "h264" and v.get("profile") == "High" and v["width"] == 1080 and v["height"] == 1920
             and v["pix_fmt"] == "yuv420p" and v.get("color_primaries") == "bt709"
             and a["codec_name"] == "aac" and a["sample_rate"] == "48000")
    inf.comprobar(espec, "Formato: H.264 High 1080x1920 yuv420p BT.709, AAC 48 kHz",
                  f"Formato fuera de especificación: {v['codec_name']} {v.get('profile')} {v['width']}x{v['height']} "
                  f"{v['pix_fmt']} {v.get('color_primaries')} / {a['codec_name']} {a['sample_rate']}")
    negros = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", ff("-i", str(final), "-vf", "blackdetect=d=0.1:pix_th=0.05",
                                                                        "-an", "-f", "null", "-"))
    inf.comprobar(not negros, "Sin frames negros", "Frames negros en: " + ", ".join(f"{a}–{b} s" for a, b in negros))
    if base:
        sil = re.findall(r"silence_start: ([\d.]+)\n.*?silence_end: ([\d.]+) \| silence_duration: ([\d.]+)",
                         ff("-i", str(base), "-af", f"silencedetect=n=-40dB:d={SILENCIO_MAX}", "-vn", "-f", "null", "-"),
                         re.S)
        inf.comprobar(not sil, f"Sin silencios de voz > {int(SILENCIO_MAX * 1000)} ms",
                      "Silencios largos en: " + ", ".join(f"{float(a):.2f} s ({float(d):.2f} s)" for a, _, d in sil))


def comprobar_loudness(inf: Informe, final: Path, objetivo: float) -> None:
    salida = ff("-i", str(final), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-")
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", salida)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", salida)[-1])
    inf.lufs, inf.true_peak = i, tp
    inf.comprobar(abs(i - objetivo) <= 1.0, f"Loudness {i} LUFS (objetivo {objetivo} ±1)",
                  f"Loudness {i} LUFS fuera de {objetivo} ±1")
    inf.comprobar(tp <= -0.9, f"True peak {tp} dBTP (sin clipping)", f"True peak {tp} dBTP: riesgo de clipping")


def comprobar_caras(inf: Informe, final: Path, layout: dict) -> None:
    cap = cv2.VideoCapture(str(final))
    det = cv2.FaceDetectorYN.create(str(MODELO_CARA), "", (540, 960), 0.7)
    fallos = []
    for v in layout["ventanas"]:
        t = (v["inicio"] + v["fin"]) / 2
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        _, caras = det.detect(cv2.resize(frame, (540, 960)))
        caras = [] if caras is None else [c for c in caras if v["tipo"] != "split" or c[1] * 2 >= 960]
        if not len(caras):
            fallos.append(f"{t:.2f} s ({v['tipo']})")
    cap.release()
    inf.comprobar(not fallos, f"Cara detectada en el punto medio de las {len(layout['ventanas'])} ventanas",
                  "Sin cara en: " + ", ".join(fallos))


def comprobar_subtitulos(inf: Informe, ass: Path, perfil) -> None:
    z = perfil.zonas_seguras
    tam = int(re.search(r"Style: Caja,[^,]+,(\d+)", ass.read_text(encoding="utf-8")).group(1))
    fuera = []
    for linea in ass.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("Dialogue:"):
            continue
        campos = linea.split(",", 9)
        m = re.search(r"\\pos\((\d+),(\d+)\)", campos[9])
        texto = re.sub(r"\{[^}]*\}", "", campos[9])
        x, y = int(m.group(1)), int(m.group(2))
        ancho = len(texto) * tam * 0.58
        arriba, abajo = y - tam * 0.7, y + tam * 0.7
        derecha = x + ancho / 2
        if arriba < z.superior or abajo > 1920 - z.inferior or derecha > 1080 - z.derecha or x - ancho / 2 < 0:
            fuera.append(f"{campos[1]} «{texto}»")
    inf.comprobar(not fuera, "Subtítulos dentro del área útil",
                  f"{len(fuera)} subtítulos tocan zonas seguras (p. ej. {fuera[0] if fuera else ''})")


def comprobar_contenido(inf: Informe, graficos: list[dict], edl: dict, trans: dict, glosario: Path, ass: Path) -> None:
    inventadas = []
    for g in graficos:
        dichos = numeros_dichos(edl, trans, g["inicio"], g["inicio"] + g["duracion"])
        malos = [n for n in numeros_de_datos(g["datos"]) if n not in dichos]
        if malos:
            inventadas.append(f"{g['id']} ({g['plantilla']}, {g['inicio']:.2f} s): {malos}")
    inf.comprobar(not inventadas, "Todas las cifras de los gráficos se dicen en su ventana",
                  "Cifras no dichas: " + "; ".join(inventadas))
    variantes = []
    if glosario.exists():
        for t in (yaml.safe_load(glosario.read_text(encoding="utf-8")) or {}).get("terminos", []):
            variantes += [(v, t["forma"]) for v in t.get("variantes", []) if v.lower() != t["forma"].lower()]
    pantalla = " ".join(textos([g["datos"] for g in graficos])) + " " + re.sub(r"\{[^}]*\}", "", ass.read_text(encoding="utf-8"))
    mal_escritos = sorted({f"«{v}» (debe ser «{f}»)" for v, f in variantes
                           if re.search(rf"\b{re.escape(v)}\b", pantalla, re.I)})
    inf.comprobar(not mal_escritos, "Términos del glosario bien escritos en pantalla",
                  "Términos mal escritos: " + ", ".join(mal_escritos))
    respaldo = [g for g in graficos if g.get("nota_qa")]
    for g in respaldo:
        inf.problemas.append(f"{g['inicio']:.2f} s: {g['nota_qa']}")


def comprobar_audio(inf: Informe, sfx: dict, mezcla: dict, duracion: float) -> None:
    ev = sfx.get("eventos", [])
    sep = SEPARACION_MIN.get(sfx.get("densidad"), 0.3) - 0.001  # la misma regla que el planificador
    solapes = [f"{a['t']:.2f}/{b['t']:.2f} s" for a, b in zip(ev, ev[1:]) if b["t"] - a["t"] < sep]
    inf.comprobar(not solapes, f"{len(ev)} efectos sin solapes", "Efectos solapados: " + ", ".join(solapes))
    if sfx.get("densidad") == "media":
        inf.comprobar(len(ev) <= max(1, int(duracion / 2)), "Densidad de efectos dentro de «media»",
                      f"{len(ev)} efectos en {duracion:.0f} s: supera la densidad media")
    if sfx.get("sin_archivo"):
        tipos = sorted({e["tipo"] for e in sfx["sin_archivo"]})
        inf.problemas.append(f"Faltan efectos en la biblioteca: {tipos}")
    m = mezcla.get("musica")
    if m:
        inf.comprobar(bool(m.get("licencia") and m.get("fuente")), f"Música del catálogo con licencia: {m['archivo']}",
                      f"Música sin licencia anotada: {m['archivo']}")
        inf.comprobar(not m.get("repetida_reciente"), "Música no repetida en los últimos 5 vídeos del perfil",
                      f"Música repetida (todas las pistas de «{m['estado']}» se usaron hace poco)")


# ---------- informe y entrega ----------

def escribir_informe(inf: Informe, destino: Path, extra: list[str]) -> str:
    veredicto = "⚠️ REVISAR" if inf.problemas else "✅ LISTO"
    lineas = [f"# Informe QA — {veredicto}", ""]
    if inf.problemas:
        lineas += ["## Revisar", *[f"- ⚠️ {p}" for p in inf.problemas], ""]
    lineas += ["## Correcto", *[f"- ✅ {o}" for o in inf.ok], ""]
    if extra:
        lineas += ["## Datos", *[f"- {e}" for e in extra], ""]
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return veredicto


def entregar(trabajo: Path, perfil: str, exportacion: dict, informe: Path, veredicto: str, limpiar: bool = True) -> Path:
    carpeta = REVISION / perfil
    carpeta.mkdir(parents=True, exist_ok=True)
    final = Path(exportacion["final"])
    prefijo = "REVISAR_" if veredicto.startswith("⚠️") else ""
    base = prefijo + final.stem
    shutil.move(str(final), carpeta / f"{base}.mp4")  # mover, no copiar: una sola copia del final
    shutil.copy2(exportacion["portada"], carpeta / f"{base}_portada.jpg")
    shutil.copy2(informe, carpeta / f"{base}_informe_qa.md")
    shutil.copy2(exportacion["transcripcion"], carpeta / f"{base}_transcripcion.txt")
    # Intermedios regenerables (decisión aprobada): se borran; el original nunca se toca.
    edit = trabajo / "edit"
    if not limpiar:
        return _registrar_final(salida_de(trabajo), exportacion, carpeta / f"{base}.mp4")
    # Solo quedan el original y las decisiones (JSON, ASS, transcripciones): todo lo demás se regenera
    # desde el original. Imprescindible con poco disco (decisión aprobada: borrar intermedios).
    salida = trabajo / "salida"
    for p in (edit / "clips", edit / "musica_ajustada.wav", edit / "base.mp4", edit / "compuesto.mp4",
              edit / "mezcla.wav", edit / "animations", *(trabajo / "fuente").glob("src_*.mp4")):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    return _registrar_final(salida, exportacion, carpeta / f"{base}.mp4")


def salida_de(trabajo: Path) -> Path:
    return trabajo / "salida"


def limpiar_trabajo(trabajo: Path) -> None:
    """Borra los intermedios regenerables de un trabajo (y de sus variantes)."""
    for t in [trabajo, *sorted((trabajo / "variantes").glob("V*"))]:
        edit = t / "edit"
        for p in (edit / "clips", edit / "musica_ajustada.wav", edit / "base.mp4", edit / "compuesto.mp4",
                  edit / "mezcla.wav", edit / "animations", *(t / "fuente").glob("src_*.mp4")):
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()


def _registrar_final(salida: Path, exportacion: dict, final: Path) -> Path:
    exportacion["final"] = str(final)
    (salida / "exportacion.json").write_text(json.dumps(exportacion, ensure_ascii=False, indent=2), encoding="utf-8")
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trabajo", type=Path, required=True)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--sin-entrega", action="store_true")
    ap.add_argument("--sin-limpieza", action="store_true", help="no borrar intermedios (quedan variantes por hacer)")
    args = ap.parse_args()
    edit = args.trabajo / "edit"
    leer = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}  # noqa: E731
    perfil = cargar(args.perfil)
    edl, layout = leer(edit / "edl.json"), leer(edit / "layout.json")
    graficos = leer(edit / "graficos.json").get("graficos", [])
    trans = leer(next((edit / "transcripts_corregidas").glob("*.json")))
    exportacion = leer(args.trabajo / "salida" / "exportacion.json")
    final = Path(exportacion["final"])
    ass = edit / "subtitulos.ass"
    base = edit / "base.mp4"

    inf = Informe()
    comprobar_tecnico(inf, final, edl, base if base.exists() else None)
    comprobar_loudness(inf, final, perfil.audio.niveles.voz_lufs)
    comprobar_caras(inf, final, layout)
    comprobar_subtitulos(inf, ass, perfil)
    comprobar_contenido(inf, graficos, edl, trans, args.perfil / "glosario.yaml", ass)
    comprobar_audio(inf, leer(edit / "sfx_timeline.json"), leer(edit / "mezcla.json"), edl["total_duration_s"])
    for a in layout.get("avisos", []):
        inf.problemas.append(a)
    if edl["total_duration_s"] > perfil.duracion_objetivo_max_s:
        inf.problemas.append(f"Duración {edl['total_duration_s']:.1f} s supera el objetivo de "
                             f"{perfil.duracion_objetivo_max_s} s (no se ha recortado contenido)")
    m = leer(edit / "mezcla.json").get("musica", {})
    extra = [f"Loudness final: {getattr(inf, 'lufs', '?')} LUFS, true peak {getattr(inf, 'true_peak', '?')} dBTP",
             f"Música: {m.get('estado', '—')}/{m.get('archivo', 'sin música')}",
             f"Ventanas de layout: {len(layout['ventanas'])}; gráficos: {len(graficos)}"]
    informe = args.trabajo / "salida" / "informe_qa.md"
    veredicto = escribir_informe(inf, informe, extra)
    print(f"{veredicto} — {len(inf.problemas)} avisos, {len(inf.ok)} comprobaciones correctas -> {informe}")
    if not args.sin_entrega:
        print(f"entregado: {entregar(args.trabajo, args.perfil.name, exportacion, informe, veredicto, not args.sin_limpieza)}")


if __name__ == "__main__":
    main()
