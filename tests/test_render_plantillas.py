"""Tests de la validación de pipeline/render_plantillas.py (sin renderizar)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from render_plantillas import a_numero, numeros_de_datos, validar  # noqa: E402

TODAS = ["gancho", "cifra", "lista", "comparativa", "pasos", "pregunta", "palabra_clave", "alerta", "grafico", "cta"]

# EDL de un solo rango y transcripción corregida con una cifra dicha ("$10.000").
EDL = {"ranges": [{"source": "s", "start": 0.0, "end": 4.0}]}
TRANS = {"words": [
    {"text": "gané", "start": 0.2, "end": 0.5, "type": "word"},
    {"text": "$10.000", "start": 0.6, "end": 1.4, "type": "word", "valor": 10000, "unidad": "$"},
    {"text": "al", "start": 1.5, "end": 1.6, "type": "word"},
    {"text": "mes.", "start": 1.6, "end": 1.9, "type": "word"},
]}


def test_a_numero_formato_es():
    assert a_numero("30.000") == 30000
    assert a_numero("3,5") == 3.5
    assert a_numero("93") == 93
    assert a_numero("1.000.000") == 1_000_000


def test_numeros_de_datos_ignora_tiempos():
    datos = {"titular": "Gana 300 al mes", "t_aterrizaje": 1.2, "items": [{"texto": "paso 2", "t": 0.5}]}
    assert numeros_de_datos(datos) == {300.0, 2.0}


def test_gancho_valido():
    validar({"id": "v1", "plantilla": "gancho", "inicio": 0, "duracion": 2,
             "datos": {"titular": "Gané $10.000 al mes"}}, TODAS, EDL, TRANS)


def test_cifra_inventada_rechazada():
    with pytest.raises(ValueError, match="no se dicen"):
        validar({"id": "v1", "plantilla": "gancho", "inicio": 0, "duracion": 2,
                 "datos": {"titular": "Gané $20.000 al mes"}}, TODAS, EDL, TRANS)


def test_cifra_de_otra_ventana_rechazada():
    with pytest.raises(ValueError, match="no se dicen"):
        validar({"id": "v2", "plantilla": "gancho", "inicio": 2.5, "duracion": 1.5,
                 "datos": {"titular": "Gané $10.000"}}, TODAS, EDL, TRANS)


def test_mas_de_siete_palabras_rechazado():
    import jsonschema as js
    with pytest.raises((ValueError, js.ValidationError)):  # lo para el schema o el tope global
        validar({"id": "v1", "plantilla": "gancho", "inicio": 0, "duracion": 2,
                 "datos": {"titular": "uno dos tres cuatro cinco seis siete ocho"}}, TODAS, None, None)


def test_plantilla_no_permitida():
    with pytest.raises(ValueError, match="no permitida"):
        validar({"id": "v1", "plantilla": "gancho", "inicio": 0, "duracion": 2,
                 "datos": {"titular": "hola"}}, ["cta"], None, None)


def test_max_palabras_del_schema():
    # schema de gancho: titular con maxPalabras 7; se comprueba vía la palabra clave propia.
    from render_plantillas import Validador
    import jsonschema as js
    esquema = {"type": "object", "properties": {"t": {"type": "string", "maxPalabras": 3}}}
    Validador(esquema).validate({"t": "uno dos tres"})
    with pytest.raises(js.ValidationError):
        Validador(esquema).validate({"t": "uno dos tres cuatro"})


def test_nombres_de_icono_no_son_cifras():
    assert numeros_de_datos({"icono": "trash-2", "iconos": ["share-2"], "rotulo": "a la basura"}) == set()
