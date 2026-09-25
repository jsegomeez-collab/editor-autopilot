"""Tests de pipeline/construir_edl.py: reglas duras de corte."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from construir_edl import construir  # noqa: E402

FPS = 25.0
# Cinco palabras; entre la 2 y la 3 hay un silencio de 0,8 s.
PALABRAS = [(0.50, 0.90), (0.95, 1.40), (1.45, 1.80), (2.60, 3.00), (3.05, 3.50)]
TRANS = {"words": [{"text": f"p{i}", "start": s, "end": e, "type": "word"} for i, (s, e) in enumerate(PALABRAS)]}


def edl(tramos, ritmo="rapido"):
    return construir(TRANS, {"tramos": tramos}, Path("/tmp/src_x.mp4"), ritmo, 4.0, FPS)


def test_silencio_largo_se_corta():
    r = edl([{"desde": 0, "hasta": 4}])["ranges"]
    assert [x["palabras"] for x in r] == [[0, 2], [3, 4]]


def test_bordes_en_fotogramas_y_sin_invadir_palabras():
    e = edl([{"desde": 1, "hasta": 3}])
    for r in e["ranges"]:
        for t in (r["start"], r["end"]):
            assert abs(t * FPS - round(t * FPS)) < 1e-6
    primero, ultimo = e["ranges"][0], e["ranges"][-1]
    assert primero["start"] >= PALABRAS[0][1]      # no entra en la palabra 0
    assert ultimo["end"] <= PALABRAS[4][0]         # no entra en la palabra 4
    assert primero["start"] <= PALABRAS[1][0] and ultimo["end"] >= PALABRAS[3][1]


def test_duracion_total_en_fotogramas():
    e = edl([{"desde": 0, "hasta": 4}])
    assert e["total_duration_s"] * FPS == pytest.approx(round(e["total_duration_s"] * FPS))


def test_reordenar_prohibido():
    with pytest.raises(ValueError):
        edl([{"desde": 3, "hasta": 4}, {"desde": 0, "hasta": 1}])
