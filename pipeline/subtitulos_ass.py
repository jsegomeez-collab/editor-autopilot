"""Subtítulos ASS palabra a palabra sobre la línea de tiempo de SALIDA (sección 6.5).

- Bloques de `palabras_por_bloque` palabras (2 por defecto). Se corta antes en fin de frase
  o en pausas ≥ 0,3 s. Un número nunca se separa de su unidad ni del sustantivo que cuenta
  ("$10.000", "10%", "4 complementos").
- MAYÚSCULAS o minúsculas según el perfil. Sin puntos, comas ni punto y coma finales.
- La palabra activa se resalta con el color de acento (un evento por palabra).
- Sin subtítulos mientras se ve la cartela del gancho (primera ventana split): no se satura el arranque.
- Posición según el layout: en split, centrados sobre la divisoria (y≈960); en full, a
  `posicion_full_pct` del alto; durante el CTA, por encima de su cartela. Siempre fuera de
  las zonas seguras.
- Estilos: caja (BorderStyle=3), contorno (borde + sombra) o mixto (caja en split, sombra en full).
- En el ASS va el nombre de familia interno de la fuente; ffmpeg recibe `fontsdir`.

Uso:
  python pipeline/subtitulos_ass.py --edl edl.json --transcripcion corr.json --layout layout.json \
      --perfil perfiles/jose [--estilo mixto] -o subtitulos.ass
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import Perfil, cargar  # noqa: E402
from planificar_layout import palabras_en_salida  # noqa: E402

W, H = 1080, 1920
PAUSA_CORTE = 0.30
HUECO_MAX_SOSTENER = 0.30  # un bloque se sostiene hasta el siguiente si el hueco es menor
Y_SPLIT = 960
Y_BANDA = 1400          # estilo «título»: bajo la cara, por encima de la zona segura inferior
TITULO_Y = (235, 505)   # franja del título (la zona segura superior acaba en 220; la banda en 520)
TITULO_X = (120, 960)   # respeta la zona segura derecha
TITULO_MAX = 92
Y_CTA = 900
TAM_FUENTE = 66
PUNTUACION_FINAL = re.compile(r"[.,;:…]+$")


def ass_color(hex_rgb: str, alfa: int = 0) -> str:
    """#RRGGBB -> &HAABBGGRR (alfa 0 = opaco, 255 = transparente)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def tiempo_ass(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def limpiar(w: dict, mayusculas: bool) -> str:
    t = PUNTUACION_FINAL.sub("", w["text"])
    if mayusculas:
        return t.upper()
    # En minúsculas se respetan los nombres del glosario ("Claude Code") y las siglas ("IA", "API").
    nucleo = re.sub(r"[^\wÁÉÍÓÚÑÜáéíóúñü]", "", t)
    if w.get("glosario") or (len(nucleo) >= 2 and nucleo.isupper()):
        return t
    return t.lower()


def bloques(palabras: list[dict], n: int) -> list[list[dict]]:
    """Agrupa palabras en bloques de n, sin separar cifras de su unidad/sustantivo."""
    salida, actual = [], []
    for i, w in enumerate(palabras):
        actual.append(w)
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else None
        cifra_sin_unidad = "valor" in w and not w.get("unidad")
        cierre = bool(re.search(r"[.?!…]»?$", w["text"]))
        pausa = siguiente is not None and siguiente["o_start"] - w["o_end"] >= PAUSA_CORTE
        lleno = len(actual) >= n
        # Una cifra sin unidad arrastra la palabra siguiente a su bloque ("4 complementos").
        if cifra_sin_unidad and siguiente and not pausa and not cierre:
            continue
        if lleno and actual and "valor" in actual[-1] and not actual[-1].get("unidad") and siguiente and not pausa:
            continue
        if lleno or cierre or pausa or siguiente is None:
            salida.append(actual)
            actual = []
    if actual:
        salida.append(actual)
    return salida


def ventana_en(layout: dict, t: float) -> dict:
    for v in layout["ventanas"]:
        if v["inicio"] <= t < v["fin"]:
            return v
    return layout["ventanas"][-1]


def posicion_y(ventana: dict, perfil: Perfil) -> int:
    if ventana.get("motivo") == "cta":
        return Y_CTA
    if ventana["tipo"] == "split":
        return Y_SPLIT
    if ventana["tipo"] == "banda":
        return Y_BANDA
    y = int(H * perfil.subtitulos.posicion_full_pct / 100)
    z = perfil.zonas_seguras
    return max(z.superior + TAM_FUENTE, min(y, H - z.inferior - TAM_FUENTE))


def estilo_de(ventana: dict, estilo: str) -> str:
    if ventana["tipo"] == "banda" and estilo == "mixto":
        return "Contorno"  # sobre la cámara: sin caja
    if estilo == "mixto":
        return "Caja" if ventana["tipo"] == "split" else "Sombra"
    return {"caja": "Caja", "contorno": "Contorno"}[estilo]


def titulo_ass(titulo: str, destacado: str, perfil: Perfil) -> tuple[str, int]:
    """Texto ASS del título en la franja superior: tamaño que cabe en ≤ 3 líneas y saltos de línea manuales."""
    ancho = TITULO_X[1] - TITULO_X[0]
    alto = TITULO_Y[1] - TITULO_Y[0]
    palabras = titulo.split()
    for tam in range(TITULO_MAX, 40, -2):
        lineas, actual = [], []
        for p in palabras:
            prueba = " ".join(actual + [p])
            if actual and len(prueba) * tam * 0.56 > ancho:
                lineas.append(actual)
                actual = [p]
            else:
                actual.append(p)
        lineas.append(actual)
        if len(lineas) <= 3 and len(lineas) * tam * 1.12 <= alto and all(len(" ".join(l)) * tam * 0.56 <= ancho for l in lineas):
            break
    acento = ass_color(perfil.colores.acentos[0])
    blanco = ass_color(perfil.colores.primario)
    marcar = {m.lower().strip(".,¿?¡!") for m in destacado.split()}
    fmt = lambda w: f"{{\\c{acento}}}{w}{{\\c{blanco}}}" if w.lower().strip(".,¿?¡!") in marcar else w  # noqa: E731
    texto = "\\N".join(" ".join(fmt(w) for w in l) for l in lineas)
    if perfil.subtitulos.mayusculas:
        texto = texto.upper()
    return texto, tam


def cabecera(perfil: Perfil) -> str:
    fam = perfil.tipografias.subtitulos.familia
    blanco = ass_color(perfil.colores.primario)
    caja = ass_color("#1E222C", 0x50)       # gris oscuro semitransparente (como en sus vídeos)
    sombra = ass_color("#000000", 0x60)
    negro = ass_color("#000000")
    comun = f"{fam},{TAM_FUENTE},{blanco},{blanco}"
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caja,{comun},{caja},{caja},1,0,0,0,100,100,0,0,3,14,0,5,60,180,0,1
Style: Sombra,{comun},{negro},{sombra},1,0,0,0,100,100,0,0,1,0,4,5,60,180,0,1
Style: Contorno,{comun},{negro},{sombra},1,0,0,0,100,100,0,0,1,4,2,5,60,180,0,1
Style: Titulo,{perfil.tipografias.titulares.familia},{TITULO_MAX},{blanco},{blanco},{negro},{sombra},1,0,0,0,100,100,0,0,1,0,3,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generar(edl: dict, transcripcion: dict, layout: dict, perfil: Perfil, estilo: str | None = None,
            basico: bool = False, titulo: str = "", destacado: str = "") -> str:
    estilo = estilo or perfil.subtitulos.estilo_por_defecto
    if estilo not in perfil.subtitulos.estilos_permitidos:
        raise ValueError(f"estilo '{estilo}' no permitido por el perfil")
    ws = palabras_en_salida(edl, transcripcion)
    acento = ass_color(perfil.colores.acentos[0])
    blanco = ass_color(perfil.colores.primario)
    lineas = [cabecera(perfil)]
    primera = layout["ventanas"][0]
    fin_gancho = primera["fin"] if primera["tipo"] == "split" else 0.0
    ws = [w for w in ws if w["o_start"] >= fin_gancho - 0.01]
    grupos = bloques(ws, perfil.subtitulos.palabras_por_bloque)
    for k, b in enumerate(grupos):
        ini = b[0]["o_start"]
        fin = b[-1]["o_end"]
        if k + 1 < len(grupos) and grupos[k + 1][0]["o_start"] - fin < HUECO_MAX_SOSTENER:
            fin = grupos[k + 1][0]["o_start"]  # sin parpadeos entre bloques seguidos
        fin = min(fin, layout["duracion"])
        textos = [limpiar(w, perfil.subtitulos.mayusculas) for w in b]
        for j, w in enumerate(b):
            t0 = ini if j == 0 else w["o_start"]
            t1 = b[j + 1]["o_start"] if j + 1 < len(b) else fin
            if t1 <= t0:
                continue
            v = ventana_en(layout, (t0 + t1) / 2)
            if v["tipo"] == "banda" and v.get("motivo") == "cta":
                continue  # «título»: durante el CTA habla su cartela; los subtítulos la pisarían
            if basico and j > 0:
                continue  # subtítulos básicos: un solo evento por bloque, sin palabra activa
            if basico:
                t1 = fin
            partes = textos if basico else [(f"{{\\c{acento}}}{t}{{\\c{blanco}}}" if i == j else t) for i, t in enumerate(textos)]
            texto = f"{{\\an5\\pos({W // 2},{posicion_y(v, perfil)})}}" + " ".join(partes)
            lineas.append(f"Dialogue: 0,{tiempo_ass(t0)},{tiempo_ass(t1)},{estilo_de(v, estilo)},,0,0,0,,{texto}")
    if titulo:  # título fijo en la franja superior durante todo el vídeo (estilo «título»)
        texto, tam = titulo_ass(titulo, destacado, perfil)
        cy = (TITULO_Y[0] + TITULO_Y[1]) // 2
        lineas.append(f"Dialogue: 1,{tiempo_ass(0)},{tiempo_ass(layout['duracion'])},Titulo,,0,0,0,,"
                      f"{{\\an5\\pos({(TITULO_X[0] + TITULO_X[1]) // 2},{cy})\\fs{tam}\\fad(150,0)}}{texto}")
    return "\n".join(lineas) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edl", type=Path, required=True)
    ap.add_argument("--transcripcion", type=Path, required=True)
    ap.add_argument("--layout", type=Path, required=True)
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--estilo", choices=["caja", "contorno", "mixto"])
    ap.add_argument("--basico", action="store_true", help="sin palabra activa resaltada (estilo «título»)")
    ap.add_argument("--titulo", default="", help="título fijo en la franja superior (estilo «título»)")
    ap.add_argument("--destacado", default="", help="palabras del título en color de acento")
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731
    ass = generar(leer(args.edl), leer(args.transcripcion), leer(args.layout), cargar(args.perfil), args.estilo,
                  args.basico, args.titulo, args.destacado)
    args.salida.write_text(ass, encoding="utf-8")
    print(f"guardado: {args.salida} ({ass.count('Dialogue:')} eventos)")


if __name__ == "__main__":
    main()
