"""Tests de pipeline/planificar_sfx.py (lógica de eventos y densidad, sin archivos de audio)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from planificar_sfx import SEPARACION_MIN, ajustar_a_palabras, aplicar_densidad, eventos_brutos  # noqa: E402

LAYOUT = {"duracion": 10.0, "ventanas": [
    {"inicio": 0.0, "fin": 2.0, "tipo": "split"},
    {"inicio": 2.0, "fin": 4.0, "tipo": "full"},
    {"inicio": 4.0, "fin": 7.0, "tipo": "split"},
    {"inicio": 7.0, "fin": 10.0, "tipo": "full"},
]}
GRAFICOS = [
    {"plantilla": "gancho", "inicio": 0.0, "duracion": 2.0, "datos": {"titular": "x", "t_aterrizaje": 0}},
    {"plantilla": "lista", "inicio": 4.0, "duracion": 3.0,
     "datos": {"items": [{"texto": "a", "t": 0.5}, {"texto": "b", "t": 1.0}, {"texto": "c", "t": 1.5}]}},
    {"plantilla": "cta", "inicio": 7.0, "duracion": 3.0, "datos": {"linea1": "Comenta", "palabra": "X", "t_aterrizaje": 0.8}},
]


def tipos(ev):
    return [e["tipo"] for e in ev]


def test_eventos_desde_lo_visual():
    ev = eventos_brutos(LAYOUT, GRAFICOS)
    assert tipos(ev) == ["impacto", "whoosh", "whoosh", "click", "click", "click", "whoosh", "notificacion"]
    assert ev[1]["t"] == 1.9  # whoosh 100 ms antes del cambio


def test_densidad_baja_solo_basicos():
    final, _ = aplicar_densidad(eventos_brutos(LAYOUT, GRAFICOS), "baja", 10.0)
    assert set(tipos(final)) <= {"impacto", "whoosh", "notificacion"}


def test_densidad_media_maximo_y_sin_solapes():
    final, descartados = aplicar_densidad(eventos_brutos(LAYOUT, GRAFICOS), "media", 10.0)
    assert len(final) <= 5 and descartados
    assert all(b["t"] - a["t"] >= SEPARACION_MIN for a, b in zip(final, final[1:]))
    assert "impacto" in tipos(final) and "notificacion" in tipos(final)


def test_efecto_dentro_de_palabra_se_adelanta():
    ev = [{"t": 1.2, "tipo": "pop"}]
    ajustar_a_palabras(ev, [{"o_start": 1.0, "o_end": 1.5}])
    assert ev[0]["t"] == 1.0


def test_sonido_con_sentido_en_plantillas_visuales():
    graficos = [
        {"plantilla": "icono", "inicio": 2.0, "duracion": 2.0, "datos": {"icono": "coins", "t_aterrizaje": 0.5}},
        {"plantilla": "icono", "inicio": 4.0, "duracion": 2.0, "datos": {"icono": "rocket", "sonido": "whoosh", "t_aterrizaje": 0.5}},
        {"plantilla": "crecimiento", "inicio": 6.0, "duracion": 2.0, "datos": {"direccion": "baja", "t_aterrizaje": 0.5}},
    ]
    ev = [e for e in eventos_brutos({"duracion": 10, "ventanas": []}, graficos)]
    assert tipos(ev) == ["moneda", "whoosh", "bajada"]


def test_preferencia_por_efectos_propios_con_rotacion():
    import random
    from planificar_sfx import elegir_variante
    rng = random.Random(0)
    # Un solo efecto propio: se alterna con los generados (nunca dos iguales seguidos).
    seq, ultima = [], None
    for _ in range(6):
        ultima = elegir_variante(rng, ["mio"], ["gen1", "gen2"], ultima)
        seq.append(ultima)
    assert seq[0] == "mio" and all(a != b for a, b in zip(seq, seq[1:])) and seq.count("mio") == 3
    # Varios propios: solo rotan los propios.
    seq, ultima = [], None
    for _ in range(6):
        ultima = elegir_variante(rng, ["mio1", "mio2"], ["gen1"], ultima)
        seq.append(ultima)
    assert set(seq) == {"mio1", "mio2"} and all(a != b for a, b in zip(seq, seq[1:]))
