"""Servidor de prueba (solo stdlib) para revisar la interfaz sin el motor real.

Sirve los estáticos de autopilot/web/, las fuentes del perfil en /fuentes/ y
respuestas falsas del contrato /api/* con ítems en todos los estados.

Uso:
    python3 autopilot/web/_mock/servidor_mock.py [puerto]
Variables opcionales:
    MOCK_SIN_CARPETA=1  -> arranca sin carpeta de destino (muestra el aviso)
    MOCK_VACIO=1        -> sin ítems (muestra el estado vacío)
    MOCK_PAUSADO=1      -> motor pausado por límite
"""

import json
import mimetypes
import os
import sys
import uuid
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
RAIZ = WEB.parent.parent
FUENTES = RAIZ / "perfiles" / "jose" / "fuentes"
SALIDA_PRUEBA = Path("/Users/josegomezkp/VideoAutopilot/trabajos/prueba_JOSE49/salida")
PORTADA = SALIDA_PRUEBA / "portada.jpg"
VIDEO = next(iter(sorted(SALIDA_PRUEBA.glob("*.mp4"))), None) if SALIDA_PRUEBA.exists() else None

AJUSTES = {
    "carpeta_salida": None if os.environ.get("MOCK_SIN_CARPETA") else "/Users/josegomezkp/Movies/Autopilot",
    "perfil_por_defecto": "jose",
    "limite_diario": 10,
    "variantes": 2,
}

# Qué cambia en cada variante (como en variantes.csv).
CAMBIOS_VARIANTES = [
    "Edición base: gancho original, gráficos y subtítulos del perfil.",
    "Otro gancho (abre con la pregunta del minuto 0:31), subtítulos palabra a palabra y música más enérgica.",
    "Gráficos alternativos con otra paleta, zoom más agresivo en los remates y efectos de sonido distintos.",
    "Versión corta de 28 s: solo los tres puntos clave y un cierre directo.",
]


def iso(delta_min: float) -> str:
    return (datetime.now() + timedelta(minutes=delta_min)).isoformat(timespec="seconds")


def item(id_, nombre, estado, etapa, progreso, mensaje="", creado=-5, iniciado=None, terminado=None,
         duracion=None, veredicto=None, avisos=None, error=None, portada=False, variantes=1):
    salida = (f"{AJUSTES['carpeta_salida']}/{'revisar/' if veredicto == 'REVISAR' else ''}{nombre}"
              if veredicto and AJUSTES["carpeta_salida"] else None)
    versiones = []
    if veredicto:
        if variantes == 1:
            versiones = [{"indice": 0, "variante": "", "veredicto": veredicto, "duracion_s": duracion,
                          "cambios": "", "salida": salida}]
        else:
            base, ext = os.path.splitext(nombre)
            for i in range(variantes):
                ver = "REVISAR" if i == 2 else "LISTO"
                dur = 28.4 if i == variantes - 1 else round(duracion - i * 1.7, 1)
                carpeta = AJUSTES["carpeta_salida"]
                versiones.append({
                    "indice": i, "variante": f"V{i + 1}", "veredicto": ver, "duracion_s": dur,
                    "cambios": CAMBIOS_VARIANTES[i % len(CAMBIOS_VARIANTES)],
                    "salida": (f"{carpeta}/{'revisar/' if ver == 'REVISAR' else ''}{base}_V{i + 1}{ext}"
                               if carpeta else None),
                })
    return {
        "id": id_, "nombre": nombre, "perfil": "jose", "estado": estado, "etapa": etapa,
        "progreso": progreso, "mensaje": mensaje, "creado": iso(creado),
        "iniciado": iso(iniciado) if iniciado is not None else None,
        "terminado": iso(terminado) if terminado is not None else None,
        "duracion_s": duracion, "veredicto": veredicto, "avisos": avisos or [], "error": error,
        "tiene_portada": portada and PORTADA.exists(),
        "salida": salida,
        "variantes": variantes,
        "versiones": versiones,
    }


def items():
    if os.environ.get("MOCK_VACIO"):
        return []
    # Del más reciente al más antiguo, como el motor real.
    return [
        item("a9", "error_audio_saturado.mov", "error", "audio", 81, creado=-2, iniciado=-12,
             error="El audio original está saturado y no se pudo limpiar. Prueba con otra toma."),
        item("a8", "reel_herramientas_ia.mp4", "pendiente", "en_cola", 0, creado=-3, variantes=3),
        item("a7", "tutorial_prompts_parte2.mov", "pendiente", "en_cola", 0, creado=-4),
        item("a6", "como_automatizar_tu_negocio.mp4", "pausado_por_limite", "en_cola", 0, creado=-6,
             mensaje="Límite diario alcanzado. Continúa mañana a las 08:00."),
        item("a5", "3_errores_con_chatgpt.mp4", "procesando", "renderizando_graficos", 64, creado=-8, iniciado=-3.2,
             mensaje="Versión 2/4 · Renderizando gráfico 4 de 6: «3 errores que cometes»", variantes=4),
        item("a4", "nunca_uses_claude_code_asi.mp4", "listo", "terminado", 100, creado=-60, iniciado=-58, terminado=-50,
             duracion=48.3, veredicto="LISTO", portada=True, variantes=4),
        item("a3", "mi_rutina_de_productividad.mov", "revisar", "terminado", 100, creado=-90, iniciado=-80, terminado=-72,
             duracion=62.0, veredicto="REVISAR", portada=True,
             avisos=["La cara sale del encuadre entre 0:21 y 0:24", "Música 2 dB por encima del objetivo en el final"]),
        item("a2", "herramienta_secreta_para_editar.mp4", "listo", "terminado", 100, creado=-140, iniciado=-130, terminado=-121,
             duracion=37.6, veredicto="LISTO", portada=True),
        item("a1", "respuesta_a_comentarios.mp4", "listo", "terminado", 100, creado=-200, iniciado=-190, terminado=-182,
             duracion=54.9, veredicto="LISTO", portada=False),
    ]


def estado():
    pausado = bool(os.environ.get("MOCK_PAUSADO"))
    return {
        "motor": {"trabajando": not pausado, "pausado_hasta": iso(8 * 60) if pausado else None,
                  "hechos_hoy": 4, "limite_diario": AJUSTES["limite_diario"]},
        "perfiles": ["jose", "jose_podcast"],
        "ajustes": AJUSTES,
        "items": items(),
    }


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, *a):  # silencio
        pass

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path):
        if not ruta or not ruta.is_file():
            self.send_error(404)
            return
        datos = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(ruta.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/estado":
            return self._json(estado())
        if ruta == "/api/ajustes":
            return self._json(AJUSTES)
        if ruta.startswith("/api/portada/"):
            return self._archivo(PORTADA)
        if ruta.startswith("/api/video/"):
            return self._archivo(VIDEO)
        if ruta.startswith("/fuentes/"):
            return self._archivo(FUENTES / Path(ruta).name)
        return super().do_GET()

    def do_POST(self):
        ruta = self.path.split("?")[0]
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else b""
        if ruta == "/api/subir":
            # Campo opcional "variantes" (1–6): el mock solo lo acepta.
            n = max(1, cuerpo.count(b'name="archivos"'))
            return self._json({"añadidos": [uuid.uuid4().hex[:8] for _ in range(n)], "duplicados": []})
        if ruta == "/api/ajustes":
            AJUSTES.update(json.loads(cuerpo or b"{}"))
            return self._json(AJUSTES)
        if ruta == "/api/elegir-carpeta":
            return self._json({"ruta": "/Users/josegomezkp/Movies/Autopilot"})
        if ruta.startswith(("/api/reintentar/", "/api/abrir/")):
            return self._json({"ok": True})
        self.send_error(404)


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
    print(f"Mock en http://127.0.0.1:{puerto}/")
    ThreadingHTTPServer(("127.0.0.1", puerto), Manejador).serve_forever()
