"""Renderiza las plantillas HyperFrames de graficos.json en paralelo (sección 6.4).

Por cada gráfico:
  1. Valida: plantilla permitida por el perfil, datos contra plantillas/<p>/schema.json,
     ≤ 7 palabras por texto y (si se pasan EDL + transcripción) que toda cifra del gráfico
     aparezca en lo dicho en esa ventana. NUNCA se inventan cifras.
  2. Monta el slot edit/animations/slot_<id>/ (copia de la plantilla con su duración,
     _comun/ y las tipografías del perfil) y el archivo de variables.
  3. Renderiza con procesos `npx hyperframes render` simultáneos (no subagentes).
  4. Verifica dimensiones y duración con ffprobe.
Escribe overlays.json para componer.py.

graficos.json:
  {"graficos": [{"id": "v01", "plantilla": "gancho", "inicio": 0.0, "duracion": 1.32,
                 "datos": {...}}]}          # tiempos t_* de datos: relativos al inicio de la ventana

Uso:
  python pipeline/render_plantillas.py graficos.json --perfil perfiles/jose --edit <trabajo>/edit
      [--edl edl.json --transcripcion corr.json] [--concurrencia 2]
  python pipeline/render_plantillas.py --preview gancho --perfil perfiles/jose -o preview.mp4 [--duracion 4]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perfil import cargar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / "plantillas"
HYPERFRAMES = "hyperframes@0.8.77"  # versión fijada: el mismo gráfico se renderiza igual siempre
MAX_PALABRAS = 7


def _max_palabras(validador, limite, instancia, schema):
    """Palabra clave propia de los schema.json: límite de palabras de un texto."""
    if isinstance(instancia, str) and len(instancia.split()) > limite:
        yield jsonschema.ValidationError(f"«{instancia}» tiene más de {limite} palabras")


Validador = jsonschema.validators.extend(jsonschema.Draft202012Validator, {"maxPalabras": _max_palabras})
FORMATOS = {"panel": ("mp4", 1080, 960), "pantalla": ("webm", 1080, 1920)}
ICONOS = PLANTILLAS / "_iconos"


def catalogo_iconos() -> dict:
    import yaml
    return yaml.safe_load((ICONOS / "catalogo.yaml").read_text(encoding="utf-8"))["iconos"]


def iconos_usados(datos) -> set[str]:
    """Nombres de icono en cualquier campo cuyo nombre contenga 'icono' (texto, lista o dentro de objetos)."""
    usados: set[str] = set()

    def recorrer(v, clave=""):
        if isinstance(v, str) and "icono" in clave:
            usados.add(v)
        elif isinstance(v, list):
            for x in v:
                recorrer(x, clave)
        elif isinstance(v, dict):
            for k, x in v.items():
                recorrer(x, k)
    recorrer(datos)
    return usados


def svgs_en_linea(nombres: set[str]) -> dict[str, str]:
    salida = {}
    for n in sorted(nombres):
        marcado = (ICONOS / "svg" / f"{n}.svg").read_text(encoding="utf-8")
        salida[n] = re.sub(r"<!--.*?-->", "", marcado, flags=re.S).strip()
    return salida


def version_node(binario: Path) -> int:
    try:
        v = subprocess.run([str(binario), "--version"], capture_output=True, text=True, timeout=10).stdout
        return int(v.strip().lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def entorno_node() -> dict:
    """Entorno con Node ≥ 22 (HyperFrames lo exige). Busca en nvm, Homebrew (node@22) y el PATH."""
    nvm = Path.home() / ".nvm" / "versions" / "node"
    candidatos = sorted(nvm.glob("v2[2-9]*/bin")) + [Path("/opt/homebrew/opt/node@22/bin"),
                                                     Path("/usr/local/opt/node@22/bin")]
    en_path = shutil.which("node")
    if en_path:
        candidatos.append(Path(en_path).parent)
    validos = [c for c in candidatos if (c / "node").exists() and version_node(c / "node") >= 22]
    if not validos:
        raise RuntimeError("no encuentro Node ≥ 22 (nvm, Homebrew node@22 o PATH): HyperFrames lo necesita")
    env = dict(os.environ)
    env["PATH"] = f"{validos[0]}:{env['PATH']}"
    env["HYPERFRAMES_NO_UPDATE_CHECK"] = "1"
    return env


# ---------- validación ----------

TECNICOS = ("icono", "archivo", "sonido", "movimiento", "direccion", "tipo", "prompt")
POSICION = {"x", "y", "lado"}  # colocación en pantalla: no son cifras que se muestren


def textos(valor) -> list[str]:
    """Textos que se VEN en pantalla (sin nombres de icono, archivos ni otros campos técnicos)."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, dict):
        return [t for k, v in valor.items() if not any(x in k for x in TECNICOS) for t in textos(v)]
    if isinstance(valor, list):
        return [t for v in valor for t in textos(v)]
    return []


def numeros_de_datos(datos) -> set[float]:
    """Cifras que el gráfico va a mostrar: campos numéricos de contenido + números en los textos."""
    nums: set[float] = set()

    tecnicos = TECNICOS  # no se muestran como texto ("trash-2" es un icono, no la cifra 2)

    def recorrer(v, clave=""):
        if isinstance(v, bool) or any(t in clave for t in tecnicos) or clave in POSICION:
            return
        if isinstance(v, (int, float)) and not clave.startswith("t_") and clave not in ("t", "decimales"):
            nums.add(float(v))
        elif isinstance(v, str):
            for m in re.findall(r"\d[\d.,]*", v):
                nums.add(a_numero(m))
        elif isinstance(v, dict):
            for k, x in v.items():
                recorrer(x, k)
        elif isinstance(v, list):
            for x in v:
                recorrer(x, clave)
    recorrer(datos)
    return nums


def a_numero(s: str) -> float:
    """'30.000' -> 30000, '3,5' -> 3.5 (formato es)."""
    s = s.rstrip(".,")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s)


def numeros_dichos(edl: dict, transcripcion: dict, ini: float, fin: float) -> set[float]:
    from planificar_layout import palabras_en_salida
    nums = set()
    for w in palabras_en_salida(edl, transcripcion):
        if ini - 0.05 <= w["o_start"] <= fin + 0.05:
            if "valor" in w:
                nums.add(float(w["valor"]))
            for m in re.findall(r"\d[\d.,]*", w["text"]):
                nums.add(a_numero(m))
    return nums


def validar(g: dict, permitidas: list[str], edl: dict | None, transcripcion: dict | None) -> None:
    p = g["plantilla"]
    if p not in permitidas:
        raise ValueError(f"{g['id']}: plantilla '{p}' no permitida por el perfil")
    schema = json.loads((PLANTILLAS / p / "schema.json").read_text(encoding="utf-8"))
    Validador(schema).validate(g["datos"])
    for t in textos(g["datos"]):
        if len(t.split()) > MAX_PALABRAS:
            raise ValueError(f"{g['id']}: más de {MAX_PALABRAS} palabras en «{t}»")
    # Los aterrizajes de una lista (items/pasos) deben ir en orden creciente.
    for lista in (v for v in g["datos"].values() if isinstance(v, list)):
        ts = [x["t"] for x in lista if isinstance(x, dict) and "t" in x]
        if ts != sorted(ts):
            raise ValueError(f"{g['id']}: tiempos de aterrizaje desordenados {ts}")
    desconocidos = iconos_usados(g["datos"]) - set(catalogo_iconos())
    if desconocidos:
        raise ValueError(f"{g['id']}: iconos que no están en plantillas/_iconos/catalogo.yaml: {sorted(desconocidos)}")
    if edl and transcripcion:
        dichos = numeros_dichos(edl, transcripcion, g["inicio"], g["inicio"] + g["duracion"])
        inventados = {n for n in numeros_de_datos(g["datos"]) if n not in dichos}
        if inventados:
            raise ValueError(f"{g['id']}: cifras que no se dicen en la ventana: {sorted(inventados)}")


# ---------- slots y render ----------

def catalogo_imagenes(perfil_dir: Path) -> list[dict]:
    """Imágenes de la marca (perfiles/<marca>/imagenes/catalogo.yaml)."""
    import yaml
    ruta = perfil_dir / "imagenes" / "catalogo.yaml"
    if not ruta.exists():
        return []
    return (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}).get("imagenes") or []


def resolver_imagen(archivo: str, perfil_dir: Path, preview: bool) -> Path:
    """Ruta real de una imagen: solo del catálogo del perfil (o de tests/ en previews)."""
    if any(i["archivo"] == archivo for i in catalogo_imagenes(perfil_dir)):
        ruta = perfil_dir / "imagenes" / archivo
    elif preview:
        ruta = RAIZ / "tests" / "fixtures" / "imagenes" / archivo
    else:
        raise ValueError(f"imagen '{archivo}' no está en {perfil_dir / 'imagenes' / 'catalogo.yaml'}")
    if not ruta.is_file():
        raise FileNotFoundError(ruta)
    return ruta


def preparar_slot(g: dict, perfil_dir: Path, dir_animaciones: Path, perfil,
                  preview: bool = False) -> tuple[Path, Path, str]:
    schema = json.loads((PLANTILLAS / g["plantilla"] / "schema.json").read_text(encoding="utf-8"))
    ext, ancho, alto = FORMATOS[schema.get("formato", "panel")]
    slot = dir_animaciones / f"slot_{g['id']}"
    if slot.exists():
        shutil.rmtree(slot)
    shutil.copytree(PLANTILLAS / g["plantilla"], slot, ignore=shutil.ignore_patterns("preview.*", "*.md"))
    shutil.copytree(PLANTILLAS / "_comun", slot / "_comun")
    fuentes = slot / "fuentes"
    fuentes.mkdir()
    t = perfil.tipografias
    for nombre, fuente in (("titulares", t.titulares), ("enfasis", t.enfasis or t.titulares), ("texto", t.subtitulos)):
        shutil.copy2(perfil_dir / fuente.archivo, fuentes / f"{nombre}.ttf")
    datos = dict(g["datos"])
    # Valores por defecto del schema (p. ej. icono_persona = "user"): así también se inyectan sus SVG.
    for clave, prop in schema.get("properties", {}).items():
        if "default" in prop:
            datos.setdefault(clave, prop["default"])
    if "archivo" in datos:  # plantilla imagen: la imagen viaja con el slot
        origen = resolver_imagen(datos["archivo"], perfil_dir, preview)
        (slot / "media").mkdir()
        shutil.copy2(origen, slot / "media" / origen.name)
        datos["archivo"] = f"media/{origen.name}"
    html = slot / "index.html"
    duracion = f"{g['duracion']:.3f}"
    html.write_text(re.sub(r'data-duration="[\d.]+"', f'data-duration="{duracion}"',
                           html.read_text(encoding="utf-8")), encoding="utf-8")
    variables = {"fondo": perfil.colores.fondo, "primario": perfil.colores.primario,
                 "acento": perfil.colores.acentos[0], "duracion": g["duracion"],
                 "datos": json.dumps(datos, ensure_ascii=False),
                 "svgs": json.dumps(svgs_en_linea(iconos_usados(datos)), ensure_ascii=False)}
    (slot / "variables.json").write_text(json.dumps(variables, ensure_ascii=False), encoding="utf-8")
    return slot, slot / f"render.{ext}", f"{ancho}x{alto}"


def renderizar(slot: Path, salida: Path, fps: float, env: dict) -> None:
    formato = salida.suffix.lstrip(".")
    cmd = ["npx", "--yes", HYPERFRAMES, "render", str(slot), "-o", str(salida), "--format", formato,
           "--fps", f"{fps:g}", "--workers", "1", "--variables-file", str(slot / "variables.json"), "--quiet"]
    r = subprocess.run(cmd, cwd=slot, env=env, capture_output=True, text=True)
    (slot / "render.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0 or not salida.exists():
        raise RuntimeError(f"falló el render de {slot.name} (ver {slot / 'render.log'})")


def verificar(salida: Path, tam: str, duracion: float, fps: float) -> None:
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", str(salida)],
        capture_output=True, text=True, check=True).stdout)
    s = info["streams"][0]
    real = f"{s['width']}x{s['height']}"
    dur = float(info["format"]["duration"])
    if real != tam:
        raise RuntimeError(f"{salida}: tamaño {real}, se esperaba {tam}")
    if abs(dur - duracion) > 1.5 / fps:
        raise RuntimeError(f"{salida}: dura {dur:.3f}s, se esperaba {duracion:.3f}s")


def render_todos(graficos: list[dict], perfil_dir: Path, edit: Path, fps: float, concurrencia: int,
                 edl: dict | None = None, transcripcion: dict | None = None, preview: bool = False) -> list[dict]:
    perfil = cargar(perfil_dir)
    for g in graficos:
        validar(g, perfil.plantillas_permitidas, edl, transcripcion)
    env = entorno_node()
    trabajos = [(g, *preparar_slot(g, perfil_dir, edit / "animations", perfil, preview)) for g in graficos]

    def uno(item):
        g, slot, salida, tam = item
        renderizar(slot, salida, fps, env)
        verificar(salida, tam, g["duracion"], fps)
        return {"id": g["id"], "plantilla": g["plantilla"], "archivo": str(salida),
                "inicio": g["inicio"], "duracion": g["duracion"], "x": 0, "y": 0}

    with ThreadPoolExecutor(max_workers=concurrencia) as ex:
        return list(ex.map(uno, trabajos))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graficos", type=Path, nargs="?")
    ap.add_argument("--perfil", type=Path, required=True)
    ap.add_argument("--edit", type=Path)
    ap.add_argument("--edl", type=Path)
    ap.add_argument("--transcripcion", type=Path)
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--concurrencia", type=int, default=2)
    ap.add_argument("--preview", help="renderiza una plantilla con sus datos de ejemplo")
    ap.add_argument("--duracion", type=float, default=4.0)
    ap.add_argument("-o", "--salida", type=Path)
    args = ap.parse_args()
    leer = lambda p: json.loads(p.read_text(encoding="utf-8"))  # noqa: E731

    if args.preview:
        schema = leer(PLANTILLAS / args.preview / "schema.json")
        g = {"id": f"preview_{args.preview}", "plantilla": args.preview, "inicio": 0.0,
             "duracion": args.duracion, "datos": schema["ejemplo"]}
        tmp = (args.salida.parent if args.salida else PLANTILLAS / args.preview) / ".preview"
        [o] = render_todos([g], args.perfil, tmp, args.fps, 1, preview=True)
        destino = args.salida or PLANTILLAS / args.preview / f"preview{Path(o['archivo']).suffix}"
        shutil.move(o["archivo"], destino)
        shutil.rmtree(tmp)
        print(destino)
        return

    if not (args.graficos and args.edit):
        sys.exit("❌ faltan graficos.json y --edit")
    edl = leer(args.edl) if args.edl else None
    trans = leer(args.transcripcion) if args.transcripcion else None
    fps = edl["fps"] if edl and "fps" in edl else args.fps
    overlays = render_todos(leer(args.graficos)["graficos"], args.perfil, args.edit, fps, args.concurrencia, edl, trans)
    (args.edit / "overlays.json").write_text(json.dumps({"overlays": overlays}, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    print(f"✅ {len(overlays)} gráficos renderizados -> {args.edit / 'overlays.json'}")


if __name__ == "__main__":
    main()
