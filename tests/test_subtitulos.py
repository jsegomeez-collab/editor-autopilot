"""Tests de pipeline/subtitulos_ass.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from subtitulos_ass import ass_color, bloques, limpiar, tiempo_ass  # noqa: E402


def w(texto, ini, **extra):
    return {"text": texto, "o_start": ini, "o_end": ini + 0.2, **extra}


def textos(bs):
    return [[x["text"] for x in b] for b in bs]


def test_bloques_de_dos_y_cifra_con_sustantivo():
    ws = [w("estos", 0.0), w("4", 0.25, valor=4), w("complementos", 0.5), w("son", 0.75), w("clave.", 1.0)]
    assert textos(bloques(ws, 2)) == [["estos", "4", "complementos"], ["son", "clave."]]


def test_cifra_con_unidad_no_arrastra():
    ws = [w("gané", 0.0), w("$10.000", 0.25, valor=10000, unidad="$"), w("al", 0.5), w("mes", 0.75)]
    assert textos(bloques(ws, 2)) == [["gané", "$10.000"], ["al", "mes"]]


def test_pausa_y_fin_de_frase_cortan():
    ws = [w("hola.", 0.0), w("esto", 0.25), w("va", 1.0)]  # pausa de 0,55 s antes de "va"
    assert textos(bloques(ws, 2)) == [["hola."], ["esto"], ["va"]]


def test_limpiar_minusculas_respeta_glosario_y_siglas():
    assert limpiar({"text": "Estás,"}, False) == "estás"
    assert limpiar({"text": "Claude Code.", "glosario": True}, False) == "Claude Code"
    assert limpiar({"text": "IA,"}, False) == "IA"
    assert limpiar({"text": "¿ñandú?"}, True) == "¿ÑANDÚ?"


def test_formatos_ass():
    assert ass_color("#FFDB00") == "&H0000DBFF"
    assert tiempo_ass(61.234) == "0:01:01.23"
