"""Frontend local del Editor Autopilot: http://127.0.0.1:8765

Sirve la interfaz (autopilot/web/) y la API que usa: subir vídeos, ver la cola y los resultados,
ajustes (carpeta de destino con el selector nativo de macOS) y reproducción de los vídeos finales.
En el mismo proceso corre el motor (cola.py): procesa los vídeos de uno en uno.

Uso:
  python autopilot/servidor.py [--puerto 8765] [--sin-navegador]
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "autopilot"))
from cola import BASE, EXTENSIONES, Cola, guardar_ajustes, leer_ajustes, perfiles  # noqa: E402

WEB = RAIZ / "autopilot" / "web"
CAMPOS_PUBLICOS = ("id", "nombre", "perfil", "estado", "etapa", "progreso", "mensaje", "creado", "iniciado",
                   "terminado", "duracion_s", "veredicto", "avisos", "error", "salida")

cola = Cola()
parar = threading.Event()


@asynccontextmanager
async def ciclo(_: FastAPI):
    hilo = threading.Thread(target=cola.bucle, args=(parar,), daemon=True, name="motor")
    hilo.start()
    yield
    parar.set()


app = FastAPI(title="Editor Autopilot", lifespan=ciclo)


def publico(it: dict) -> dict:
    d = {k: it.get(k) for k in CAMPOS_PUBLICOS}
    d["tiene_portada"] = bool(it.get("portada") and Path(it["portada"]).exists())
    d["variantes"] = it.get("variantes") or 1
    d["versiones"] = [{"indice": k, "variante": v["variante"], "veredicto": v["veredicto"],
                       "duracion_s": v["duracion_s"], "cambios": v["cambios"], "salida": v.get("salida_usuario")}
                      for k, v in enumerate(it.get("versiones") or [])]
    return d


@app.get("/api/estado")
def estado() -> dict:
    ajustes = leer_ajustes()
    with cola.cerrojo:
        items = [publico(i) for i in reversed(cola.items)]
    return {"motor": {"trabajando": cola.trabajando,
                      "pausado_hasta": cola.pausado_hasta.isoformat(timespec="seconds") if cola.pausado_hasta else None,
                      "hechos_hoy": cola.hechos_hoy(), "limite_diario": ajustes["limite_diario"]},
            "perfiles": perfiles(), "ajustes": ajustes, "items": items}


@app.post("/api/subir")
async def subir(perfil: str = Form(...), archivos: list[UploadFile] = File(...), variantes: int | None = Form(None)) -> dict:
    if perfil not in perfiles():
        raise HTTPException(400, f"perfil desconocido: {perfil}")
    carpeta = BASE / "entrada" / perfil
    carpeta.mkdir(parents=True, exist_ok=True)
    anadidos, duplicados = [], []
    for a in archivos:
        nombre = re.sub(r"[/\\:]", "_", Path(a.filename or "video.mp4").name)
        if Path(nombre).suffix.lower() not in EXTENSIONES:
            raise HTTPException(400, f"formato no admitido: {nombre}")
        destino = carpeta / nombre
        n = 1
        while destino.exists():
            destino = carpeta / f"{Path(nombre).stem}_{n}{Path(nombre).suffix}"
            n += 1
        tmp = carpeta / f".subiendo_{destino.name}"  # el vigilante ignora los ocultos
        with tmp.open("wb") as f:
            while bloque := await a.read(8 << 20):
                f.write(bloque)
        tmp.rename(destino)
        it, dup = cola.anadir(destino, perfil)
        if dup:
            destino.unlink()  # la copia recién subida sobra: el mismo vídeo ya está en la cola (el original no se toca)
            duplicados.append(nombre)
        else:
            if variantes:
                with cola.cerrojo:
                    it["variantes"] = max(1, min(6, variantes))
                    cola._guardar()
            anadidos.append(it["id"])
    return {"añadidos": anadidos, "duplicados": duplicados}


@app.get("/api/ajustes")
def ver_ajustes() -> dict:
    return leer_ajustes()


@app.post("/api/ajustes")
def cambiar_ajustes(datos: dict) -> dict:
    try:
        return guardar_ajustes(datos)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/elegir-carpeta")
def elegir_carpeta() -> dict:
    """Abre el selector nativo de carpetas de macOS (el servidor corre en el propio Mac)."""
    r = subprocess.run(["osascript", "-e",
                        'POSIX path of (choose folder with prompt "¿Dónde guardo los vídeos editados?")'],
                       capture_output=True, text=True)
    return {"ruta": r.stdout.strip().rstrip("/") or None if r.returncode == 0 else None}


def _item(id_: str) -> dict:
    it = cola.item(id_)
    if not it:
        raise HTTPException(404, "no existe")
    return it


@app.get("/api/video/{id_}")
def video(id_: str, v: int = 0):
    it = _item(id_)
    versiones = it.get("versiones") or []
    ruta = versiones[v]["final"] if 0 <= v < len(versiones) else (it.get("final") or it.get("salida"))
    if not ruta or not Path(ruta).exists():
        raise HTTPException(404, "vídeo no disponible")
    return FileResponse(ruta, media_type="video/mp4")


@app.get("/api/portada/{id_}")
def portada(id_: str):
    it = _item(id_)
    if not it.get("portada") or not Path(it["portada"]).exists():
        raise HTTPException(404, "sin portada")
    return FileResponse(it["portada"], media_type="image/jpeg")


@app.post("/api/reintentar/{id_}")
def reintentar(id_: str) -> dict:
    return {"ok": cola.reintentar(id_)}


@app.post("/api/abrir/{id_}")
def abrir(id_: str) -> dict:
    it = _item(id_)
    ruta = it.get("salida") or it.get("final")
    if not ruta or not Path(ruta).exists():
        raise HTTPException(404, "vídeo no disponible")
    subprocess.run(["open", "-R", ruta])
    return {"ok": True}


@app.exception_handler(Exception)
async def errores(_, exc: Exception):
    return JSONResponse({"error": str(exc)}, status_code=500)


# Estáticos: tipografías del perfil por defecto y la interfaz.
app.mount("/fuentes", StaticFiles(directory=RAIZ / "perfiles" / leer_ajustes()["perfil_por_defecto"] / "fuentes"),
          name="fuentes")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-navegador", action="store_true")
    args = ap.parse_args()
    if shutil.which("claude") is None:
        print("⚠️  No encuentro 'claude' en el PATH: la edición automática fallará.")
    if not args.sin_navegador:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.puerto}")).start()
    uvicorn.run(app, host="127.0.0.1", port=args.puerto, log_level="warning")


if __name__ == "__main__":
    main()
