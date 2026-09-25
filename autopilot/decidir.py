"""Decisiones creativas con Claude en modo headless (suscripción, claude-sonnet-5).

Dos llamadas con salida estructurada (--json-schema):
  1. cortes:   qué tramos de palabras se quedan (reglas 6.2), estrategia, estado de ánimo de la
               música, palabra del CTA y titular del gancho.
  2. graficos: plantilla y datos para cada ventana split + stickers en las ventanas full
               (plantillas/REGLAS_SELECCION.md).
Las salidas se validan fuera (construir_edl.py y render_plantillas.validar). Si hay errores,
editar.py vuelve a llamar pasando los errores.

Autenticación: SIEMPRE la suscripción. Se eliminan del entorno ANTHROPIC_API_KEY,
CLAUDE_CODE_OAUTH_TOKEN y ANTHROPIC_AUTH_TOKEN (si existieran, Claude Code facturaría por API).
Coste: system prompt propio y sin herramientas -> ~100 veces más barato que una sesión normal.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "claude-sonnet-5"
VARIABLES_PROHIBIDAS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN")
SISTEMA = ("Eres el editor de vídeo de una agencia de contenido para marcas personales. Editas reels "
           "verticales en español siguiendo reglas fijas. Respondes SOLO con el JSON pedido, sin comentarios.")
PATRON_LIMITE = re.compile(r"(usage limit|rate limit|session limit|hit your .*limit|limit reached|429)", re.I)


class LimiteDeUso(RuntimeError):
    """Se alcanzó el límite de uso de la suscripción: el trabajo vuelve a la cola en pausa."""


def entorno_claude() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in VARIABLES_PROHIBIDAS}
    # Con --setting-sources "" no se lee .claude/settings.json: el modelo se fija aquí también.
    env.update({"ANTHROPIC_DEFAULT_HAIKU_MODEL": MODELO, "CLAUDE_CODE_SUBAGENT_MODEL": MODELO})
    return env


def claude_json(prompt: str, esquema: dict, registro: list | None = None, timeout: int = 600) -> dict:
    """Llama a Claude headless y devuelve el objeto estructurado. Anota el uso en `registro`."""
    cmd = ["claude", "-p", prompt, "--model", MODELO, "--output-format", "json", "--tools", "",
           "--no-session-persistence", "--setting-sources", "", "--strict-mcp-config",
           "--system-prompt", SISTEMA, "--json-schema", json.dumps(esquema, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=entorno_claude(), timeout=timeout, cwd=RAIZ)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        texto = (r.stdout + r.stderr)[-800:]
        if PATRON_LIMITE.search(texto):
            raise LimiteDeUso(texto)
        raise RuntimeError(f"respuesta no JSON de claude (código {r.returncode}): {texto}")
    if registro is not None:
        registro.append({"coste_usd_estimado": d.get("total_cost_usd"), "turnos": d.get("num_turns"),
                         "duracion_ms": d.get("duration_ms"), "modelos": list(d.get("modelUsage", {})),
                         "usage": d.get("usage")})
    if d.get("is_error") or d.get("structured_output") is None:
        texto = str(d.get("result", ""))[:800]
        if PATRON_LIMITE.search(texto) or d.get("api_error_status") == 429:
            raise LimiteDeUso(texto)
        raise RuntimeError(f"claude devolvió error ({d.get('subtype')}): {texto}")
    return d["structured_output"]


# ---------- 1. cortes ----------

def palabras_numeradas(transcripcion: dict) -> str:
    """Frases (cortadas en pausas ≥ 0,4 s) con cada palabra numerada: 'Nunca(0) uses(1) …'."""
    ws = [w for w in transcripcion["words"] if w.get("type") == "word"]
    lineas, actual, ini = [], [], None
    for i, w in enumerate(ws):
        if actual and w["start"] - ws[i - 1]["end"] >= 0.4:
            lineas.append(f"[{ini:.2f}-{ws[i - 1]['end']:.2f}] " + " ".join(actual))
            actual = []
        if not actual:
            ini = w["start"]
        actual.append(f"{w['text']}({i})")
    if actual:
        lineas.append(f"[{ini:.2f}-{ws[-1]['end']:.2f}] " + " ".join(actual))
    return "\n".join(lineas)


def decidir_cortes(transcripcion: dict, perfil, correcciones: str, registro: list,
                   errores_previos: str = "") -> dict:
    estados = list(perfil.audio.estados_animo_permitidos)
    esquema = {
        "type": "object", "additionalProperties": False,
        "required": ["estrategia", "tramos", "estado_musica", "palabra_cta", "titular_gancho"],
        "properties": {
            "estrategia": {"type": "string", "description": "4-8 frases: qué se corta y por qué"},
            "tramos": {"type": "array", "minItems": 1, "items": {
                "type": "object", "additionalProperties": False, "required": ["desde", "hasta", "beat", "motivo"],
                "properties": {"desde": {"type": "integer"}, "hasta": {"type": "integer"},
                               "beat": {"type": "string"}, "motivo": {"type": "string"}}}},
            "estado_musica": {"enum": estados},
            "palabra_cta": {"type": ["string", "null"], "description": "palabra que pide comentar, o null"},
            "titular_gancho": {"type": "string", "description": "≤ 7 palabras literales del gancho"},
        },
    }
    prompt = f"""Decide los cortes de este vídeo de una persona hablando a cámara.

REGLAS (obligatorias):
- Elimina el preámbulo (saludos, "hoy te voy a contar…") antes de la primera frase con contenido: el vídeo empieza en la primera palabra del gancho.
- Elimina falsos comienzos (palabras cortadas, marcadas con "--"), frases repetidas (quédate con la ÚLTIMA toma limpia y completa) y muletillas de vacilación que no aporten ("eh", "em", "este…", "o sea", "bueno", "pues", "vale", "¿vale?", "¿no?", "digamos", "en plan", "tipo"){", y además: " + ", ".join(perfil.muletillas_extra) if perfil.muletillas_extra else ""}.
- No cortes nunca: {", ".join(perfil.palabras_a_no_cortar) or "(nada especial)"}.
- PROHIBIDO reordenar ideas, eliminar ideas completas o cambiar el sentido. Los tramos van en orden creciente y sin solaparse.
- Los silencios los recorta el sistema; tú eliges PALABRAS (índices entre paréntesis, ambos incluidos).
- estado_musica según el tono: educativo/informativo → neutra; motivacional/logro → inspiradora; errores/riesgos → tension; historia personal → emocional; ritmo alto/listas rápidas → energetica (solo entre: {", ".join(estados)}; por defecto {perfil.audio.estado_animo_por_defecto}).
- palabra_cta: la palabra que se pide comentar/escribir al final (tal cual, sin comillas), o null si no hay.

CORRECCIONES DEL CLIENTE (prioridad sobre el perfil):
{correcciones.strip() or "(ninguna)"}
{("ERRORES DE TU RESPUESTA ANTERIOR (corrígelos):\n" + errores_previos) if errores_previos else ""}
TRANSCRIPCIÓN (frases con [inicio-fin] en segundos; cada palabra con su índice):
{palabras_numeradas(transcripcion)}
"""
    return claude_json(prompt, esquema, registro)


# ---------- 2. gráficos ----------

def catalogo_plantillas(permitidas: list[str]) -> str:
    bloques = []
    for p in permitidas:
        carpeta = RAIZ / "plantillas" / p
        schema = json.loads((carpeta / "schema.json").read_text(encoding="utf-8"))
        readme = (carpeta / "README.md").read_text(encoding="utf-8") if (carpeta / "README.md").exists() else ""
        cuando = next((l.split("**Cuándo:**", 1)[1].strip() for l in readme.splitlines() if "**Cuándo:**" in l), "")
        campos = []
        for k, v in schema.get("properties", {}).items():
            tipo = v.get("enum") or v.get("type", "")
            req = "*" if k in schema.get("required", []) else ""
            campos.append(f"{k}{req}:{tipo}")
        bloques.append(f"- {p} [{schema.get('formato', 'panel')}]: {cuando}\n  campos (* obligatorio): {', '.join(campos)}\n"
                       f"  ejemplo: {json.dumps(schema.get('ejemplo', {}), ensure_ascii=False)}")
    return "\n".join(bloques)


def catalogo_iconos() -> str:
    iconos = yaml.safe_load((RAIZ / "plantillas" / "_iconos" / "catalogo.yaml").read_text(encoding="utf-8"))["iconos"]
    return "\n".join(f"{n}: {', '.join(v['etiquetas'])}" for n, v in iconos.items())


def catalogo_imagenes(perfil_dir: Path) -> str:
    ruta = perfil_dir / "imagenes" / "catalogo.yaml"
    if not ruta.exists():
        return "(ninguna)"
    imgs = (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}).get("imagenes") or []
    return "\n".join(f"{i['archivo']} ({i['tipo']}): {', '.join(i['terminos'])}" for i in imgs) or "(ninguna)"


def decidir_graficos(ventanas_txt: str, perfil, perfil_dir: Path, titular_gancho: str, palabra_cta: str | None,
                     registro: list, errores_previos: str = "") -> dict:
    esquema = {
        "type": "object", "additionalProperties": False, "required": ["graficos", "stickers"],
        "properties": {
            "graficos": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["ventana", "plantilla", "datos"],
                "properties": {"ventana": {"type": "integer"}, "plantilla": {"enum": list(perfil.plantillas_permitidas)},
                               "datos": {"type": "object"}}}},
            "stickers": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["inicio", "duracion", "icono", "lado", "rotulo"],
                "properties": {"inicio": {"type": "number"}, "duracion": {"type": "number"},
                               "icono": {"type": "string"}, "lado": {"enum": ["izquierda", "derecha"]},
                               "rotulo": {"type": "string"}, "sonido": {"type": "string"}}}},
        },
    }
    reglas = (RAIZ / "plantillas" / "REGLAS_SELECCION.md").read_text(encoding="utf-8")
    cta = f'La palabra del CTA es "{palabra_cta.upper()}".' if palabra_cta else "No hay palabra de CTA: usa la cta con el texto de cierre dicho."
    prompt = f"""Elige los motion graphics de este vídeo.

{reglas}

Titular sugerido para el gancho: "{titular_gancho}". {cta}
Formato de cifras del perfil: {perfil.identidad.idioma} ({"$30.000, 93%" if perfil.identidad.idioma == "es-LatAm" else "30.000 $, 93 %"}).

PLANTILLAS DISPONIBLES:
{catalogo_plantillas([p for p in perfil.plantillas_permitidas if p != "sticker"])}
- sticker: va en la lista "stickers" (inicio ABSOLUTO en segundos del vídeo, duración, icono, lado, rótulo de 1–2 palabras). Aterriza 0,25 s tras su inicio.

ICONOS (nombre: significado):
{catalogo_iconos()}

IMÁGENES DE LA MARCA (plantilla imagen, campo archivo):
{catalogo_imagenes(perfil_dir)}
{("ERRORES DE TU RESPUESTA ANTERIOR (corrígelos, conserva lo que estaba bien):\n" + errores_previos) if errores_previos else ""}
VENTANAS DEL VÍDEO (índice, tipo, inicio–fin en segundos del vídeo; palabras con su segundo RELATIVO al inicio de la ventana):
{ventanas_txt}

Devuelve un gráfico para CADA ventana split y para la ventana del CTA, y los stickers de las ventanas full."""
    return claude_json(prompt, esquema, registro)
