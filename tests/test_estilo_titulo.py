"""Tests del estilo «título»: cámara a pantalla completa (sin franja) y título encima del vídeo."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "pipeline"))
from componer import filtro_layout  # noqa: E402
from perfil import cargar  # noqa: E402
from planificar_layout import limites, planificar_titulo  # noqa: E402
from subtitulos_ass import cabecera, titulo_ass  # noqa: E402

PERFIL = cargar(RAIZ / "perfiles" / "jose")


def palabras(n: int, paso: float = 0.5) -> list[dict]:
    ws = []
    for i in range(n):
        texto = "comenta" if i == n - 4 else ("fin." if i % 6 == 5 else "palabra")
        ws.append({"text": texto, "o_start": i * paso, "o_end": i * paso + 0.4})
    return ws


def plan(caras: dict) -> dict:
    ws = palabras(40)
    edl = {"total_duration_s": 20.0, "ranges": [{"start": 0.0, "end": 20.0}]}
    return planificar_titulo(edl, ws, limites(ws, []), caras, PERFIL)


def caras_9x16(con_cara: bool = True) -> dict:
    muestra = {"t": 0.0, "caja": [390, 700, 300, 380], "ojos": [[470, 850], [610, 850]], "score": 0.9}
    ms = [dict(muestra, t=t / 4) for t in range(80)] if con_cara else []
    return {"ancho": 1080, "alto": 1920, "muestras": ms}


def test_sin_franja_y_sin_recorte_en_9x16():
    layout = plan(caras_9x16())
    assert layout["banda_h"] == 0
    for v in layout["ventanas"]:
        assert v["tipo"] == "banda"
        if v["zoom"] == 1.0:
            assert v["recorte"] == [0, 0, 1080, 1920]  # el cuadro entero: no se corta nada


def test_sin_cara_recorte_centrado_con_proporcion_9x16():
    layout = plan(caras_9x16(con_cara=False))
    for v in layout["ventanas"]:
        x, y, w, h = v["recorte"]
        assert abs(w / h - 1080 / 1920) < 0.01
        assert 0 <= x and x + w <= 1080 and 0 <= y and y + h <= 1920
        if v["zoom"] == 1.0:
            assert v["recorte"] == [0, 0, 1080, 1920]


def test_compositor_sin_relleno_de_franja():
    grafo, _ = filtro_layout(plan(caras_9x16()), "#121827")
    assert "scale=1080:1920" in grafo
    assert "pad=1080:1920:0:0" in grafo  # relleno nulo: la cámara cubre todo el lienzo


def test_titulo_con_contorno_como_los_subtitulos():
    estilo = next(l for l in cabecera(PERFIL).splitlines() if l.startswith("Style: Titulo,"))
    campos = estilo.split(",")
    assert campos[15] == "1"  # BorderStyle 1: contorno + sombra, sin caja
    assert int(campos[16]) > 0  # grosor del contorno


def test_titulo_en_mayusculas_conserva_el_color_del_destacado():
    perfil = PERFIL.model_copy(deep=True)
    perfil.subtitulos.mayusculas = True
    texto, _ = titulo_ass("Tus clientes facturan más que tú", "facturan más", perfil)
    assert "FACTURAN" in texto
    assert "{\\c&H" in texto and "{\\C" not in texto  # etiquetas de color intactas
