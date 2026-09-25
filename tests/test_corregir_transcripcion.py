"""Tests de pipeline/corregir_transcripcion.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from corregir_transcripcion import corregir  # noqa: E402

REGLAS = [(["cloud", "code"], "Claude Code"), (["cloud"], "Claude")]


def transcripcion(frase: str) -> dict:
    """Crea una transcripción falsa con una palabra cada 0,5 s."""
    palabras = [
        {"text": t, "start": i * 0.5, "end": i * 0.5 + 0.4, "type": "word"}
        for i, t in enumerate(frase.split())
    ]
    return {"language_code": "spa", "words": palabras}


def textos(frase: str, reglas=()) -> list[str]:
    return [w["text"] for w in corregir(transcripcion(frase), list(reglas))["words"]]


def test_articulos_no_se_convierten():
    assert textos("una sola persona y un negocio") == ["una", "sola", "persona", "y", "un", "negocio"]


def test_cifras_con_unidad():
    assert textos("gané diez mil dólares mensuales") == ["gané", "10.000 $", "mensuales"]
    assert textos("el diez por ciento") == ["el", "10 %"]
    assert textos("pagué trescientos euros.") == ["pagué", "300 €."]
    assert textos("un euro") == ["1 €"]


def test_miles_y_decimales():
    assert textos("mil quinientos pisos") == ["1500", "pisos"]
    assert textos("un millón") == ["1.000.000"]
    assert textos("tres coma cinco por ciento") == ["3,5 %"]


def test_puntuacion_corta_el_numero():
    assert textos("tengo cuatro, cinco pisos") == ["tengo", "4,", "5", "pisos"]


def test_glosario_y_puntuacion():
    assert textos("¿Usas Cloud Code? Cloud mola", REGLAS) == ["¿Usas", "Claude Code?", "Claude", "mola"]
    assert textos("¿Cloud Code?", REGLAS) == ["¿Claude Code?"]


def test_timestamps_se_conservan():
    res = corregir(transcripcion("gané diez mil dólares"), [])
    token = res["words"][1]
    assert (token["start"], token["end"]) == (0.5, 1.9)
    assert token["valor"] == 10000 and token["unidad"] == "$"


def test_formato_latam():
    res = corregir(transcripcion("gané treinta mil dólares con un noventa y tres por ciento"), [], "es-LatAm")
    assert [w["text"] for w in res["words"]] == ["gané", "$30.000", "con", "un", "93%"]
