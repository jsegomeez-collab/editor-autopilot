"""Corrige una transcripción de Scribe para el texto que irá a pantalla.

Hace dos cosas, sin alterar ningún timestamp:
  1. Aplica el glosario del perfil ("Cloud Code" -> "Claude Code").
  2. Convierte cifras dichas en letra a dígitos, con su unidad pegada
     ("diez mil dólares" -> "10.000 $", "diez por ciento" -> "10 %").

Cuando varias palabras se funden en un token, el token nuevo va del `start`
de la primera al `end` de la última. La transcripción original (caché de
video-use) no se toca: se escribe un JSON aparte.

Uso:
  python pipeline/corregir_transcripcion.py <transcripcion.json> -o <salida.json> [--glosario glosario.yaml]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml
from text_to_num import text2num

PUNT_INICIO = "¿¡«\"'("
PUNT_FIN = "?!.,;:»\"')…-—"

# "un/una/uno" solos son casi siempre artículos o pronombres: no se convierten.
ARTICULOS = {"un", "una", "uno"}

# Unidades que se pegan al número. Clave = palabras normalizadas.
UNIDADES = {
    ("por", "ciento"): "%",
    ("por", "cien"): "%",
    ("euros",): "€",
    ("euro",): "€",
    ("dólares",): "$",
    ("dólar",): "$",
}

MAX_PALABRAS_NUMERO = 8


def separar_puntuacion(texto: str) -> tuple[str, str, str]:
    """Devuelve (puntuación inicial, núcleo, puntuación final)."""
    i = 0
    while i < len(texto) and texto[i] in PUNT_INICIO:
        i += 1
    j = len(texto)
    while j > i and texto[j - 1] in PUNT_FIN:
        j -= 1
    return texto[:i], texto[i:j], texto[j:]


def normalizar(texto: str) -> str:
    return separar_puntuacion(texto)[1].lower()


def es_palabra_numerica(nucleo: str) -> bool:
    if nucleo in {"y", "coma"}:
        return True
    try:
        text2num(nucleo, "es")
        return True
    except ValueError:
        return False


def formatear_numero(valor: float) -> str:
    """Formato es-ES: separador de miles '.' a partir de 10.000, decimal ','."""
    if valor != int(valor):
        entero, dec = f"{valor}".split(".")
        return f"{formatear_numero(int(entero))},{dec}"
    n = int(valor)
    if n < 10000:
        return str(n)
    return f"{n:,}".replace(",", ".")


def valor_de_span(nucleos: list[str]) -> float | None:
    """Valor numérico de una secuencia de palabras, o None si no es un número."""
    if not nucleos or nucleos[-1] in {"y", "coma"} or nucleos[0] in {"y", "coma"}:
        return None
    if "coma" in nucleos:
        k = nucleos.index("coma")
        entero = valor_de_span(nucleos[:k])
        dec = valor_de_span(nucleos[k + 1:])
        if entero is None or dec is None or dec != int(dec):
            return None
        return float(f"{int(entero)}.{int(dec)}")
    try:
        return text2num(" ".join(nucleos), "es")
    except ValueError:
        return None


def fundir(palabras: list[dict], texto: str, **extra) -> dict:
    """Crea un token que abarca varias palabras conservando sus tiempos."""
    ini, _, _ = separar_puntuacion(palabras[0]["text"])
    _, _, fin = separar_puntuacion(palabras[-1]["text"])
    token = {
        "text": f"{ini}{texto}{fin}",
        "start": palabras[0]["start"],
        "end": palabras[-1]["end"],
        "type": "word",
        "original": " ".join(p["text"] for p in palabras),
    }
    if "speaker_id" in palabras[0]:
        token["speaker_id"] = palabras[0]["speaker_id"]
    token.update(extra)
    return token


def cargar_glosario(ruta: Path | None) -> list[tuple[list[str], str]]:
    """Lista de (variante normalizada en palabras, forma correcta), la más larga primero."""
    if not ruta:
        return []
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    reglas = []
    for termino in datos.get("terminos", []):
        for variante in termino.get("variantes", []):
            reglas.append((variante.lower().split(), termino["forma"]))
    reglas.sort(key=lambda r: len(r[0]), reverse=True)
    return reglas


def aplicar_glosario(palabras: list[dict], reglas) -> list[dict]:
    salida, i = [], 0
    while i < len(palabras):
        for variante, forma in reglas:
            n = len(variante)
            tramo = palabras[i:i + n]
            # Solo se funde si no hay puntuación de corte en medio del tramo.
            limpio = all(not separar_puntuacion(p["text"])[2] for p in tramo[:-1])
            if len(tramo) == n and limpio and [normalizar(p["text"]) for p in tramo] == variante:
                salida.append(fundir(tramo, forma, glosario=True))
                i += n
                break
        else:
            salida.append(palabras[i])
            i += 1
    return salida


def buscar_unidad(palabras: list[dict], j: int) -> tuple[str | None, int]:
    """Si tras la posición j hay una unidad, devuelve (símbolo, nº de palabras)."""
    for clave, simbolo in UNIDADES.items():
        tramo = palabras[j:j + len(clave)]
        if len(tramo) == len(clave) and tuple(normalizar(p["text"]) for p in tramo) == clave:
            return simbolo, len(clave)
    return None, 0


def convertir_cifras(palabras: list[dict]) -> list[dict]:
    salida, i = [], 0
    while i < len(palabras):
        mejor = None  # (fin_exclusivo, valor)
        for j in range(i + 1, min(i + MAX_PALABRAS_NUMERO, len(palabras)) + 1):
            tramo = palabras[i:j]
            nucleos = [normalizar(p["text"]) for p in tramo]
            if not es_palabra_numerica(nucleos[-1]):
                break
            valor = valor_de_span(nucleos)
            if valor is not None:
                mejor = (j, valor)
            # Una coma, punto, etc. al final de una palabra cierra el número.
            if separar_puntuacion(tramo[-1]["text"])[2]:
                break
        if mejor is None:
            salida.append(palabras[i])
            i += 1
            continue
        j, valor = mejor
        corta_por_puntuacion = bool(separar_puntuacion(palabras[j - 1]["text"])[2])
        simbolo, n_unidad = (None, 0) if corta_por_puntuacion else buscar_unidad(palabras, j)
        solo_articulo = j - i == 1 and normalizar(palabras[i]["text"]) in ARTICULOS
        if solo_articulo and not simbolo:
            salida.append(palabras[i])
            i += 1
            continue
        texto = formatear_numero(valor) + (f" {simbolo}" if simbolo else "")
        salida.append(fundir(palabras[i:j + n_unidad], texto, valor=valor, unidad=simbolo))
        i = j + n_unidad
    return salida


def corregir(transcripcion: dict, reglas) -> dict:
    palabras = [w for w in transcripcion["words"] if w.get("type") in ("word", "audio_event")]
    solo_palabras = [w for w in palabras if w["type"] == "word"]
    corregidas = convertir_cifras(aplicar_glosario(solo_palabras, reglas))
    eventos = [w for w in palabras if w["type"] == "audio_event"]
    todas = sorted(corregidas + eventos, key=lambda w: w["start"])
    return {
        "language_code": transcripcion.get("language_code"),
        "text": " ".join(w["text"] for w in corregidas),
        "words": todas,
        "origen": "corregir_transcripcion.py",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripcion", type=Path)
    ap.add_argument("-o", "--salida", type=Path, required=True)
    ap.add_argument("--glosario", type=Path)
    args = ap.parse_args()

    datos = json.loads(args.transcripcion.read_text(encoding="utf-8"))
    resultado = corregir(datos, cargar_glosario(args.glosario))
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    cambios = [w for w in resultado["words"] if "original" in w]
    print(f"guardado: {args.salida} ({len(cambios)} correcciones)")
    for w in cambios:
        print(f"  {w['start']:7.2f}s  {w['original']!r} -> {w['text']!r}")


if __name__ == "__main__":
    main()
