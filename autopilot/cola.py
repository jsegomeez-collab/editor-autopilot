"""Cola persistente de vídeos (modo lote, sección 7).

- Persistente en ~/VideoAutopilot/cola.json e idempotente por hash del archivo (nunca procesa
  dos veces el mismo vídeo; un vídeo en error sí se puede volver a añadir).
- Un vídeo cada vez (concurrencia 1). Un reintento; si vuelve a fallar, el trabajo se mueve a
  ~/VideoAutopilot/errores/ con su log y el motivo, y la cola sigue.
- Si se alcanza el límite de uso de la suscripción de Claude, el vídeo vuelve a la cola como
  `pausado_por_limite` y el motor espera PAUSA_LIMITE antes de reintentar (no cuenta como fallo).
- Límite diario de vídeos (ajustes). Vigila ~/VideoAutopilot/entrada/<perfil>/ (tamaño estable ≥ 5 s).
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "pipeline"))
sys.path.insert(0, str(RAIZ / "autopilot"))

BASE = Path.home() / "VideoAutopilot"
COLA = BASE / "cola.json"
AJUSTES = BASE / "ajustes.json"
EXTENSIONES = {".mp4", ".mov", ".m4v", ".mkv"}
PAUSA_LIMITE = timedelta(minutes=30)
INTENTOS = 2  # 1 intento + 1 reintento
AJUSTES_POR_DEFECTO = {"carpeta_salida": None, "perfil_por_defecto": "jose", "limite_diario": 20}


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def perfiles() -> list[str]:
    return sorted(p.name for p in (RAIZ / "perfiles").iterdir() if p.is_dir() and not p.name.startswith("_")
                  and (p / "perfil.yaml").exists())


def leer_ajustes() -> dict:
    datos = json.loads(AJUSTES.read_text()) if AJUSTES.exists() else {}
    return {**AJUSTES_POR_DEFECTO, **datos}


def guardar_ajustes(nuevos: dict) -> dict:
    ajustes = {**leer_ajustes(), **{k: v for k, v in nuevos.items() if k in AJUSTES_POR_DEFECTO}}
    if ajustes["perfil_por_defecto"] not in perfiles():
        raise ValueError(f"perfil desconocido: {ajustes['perfil_por_defecto']}")
    ajustes["limite_diario"] = max(1, int(ajustes["limite_diario"]))
    BASE.mkdir(parents=True, exist_ok=True)
    AJUSTES.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2))
    return ajustes


class Cola:
    def __init__(self):
        self.cerrojo = threading.RLock()
        self.items: list[dict] = json.loads(COLA.read_text())["items"] if COLA.exists() else []
        self.pausado_hasta: datetime | None = None
        self.trabajando = False
        # Lo que estaba "procesando" al cerrar el programa vuelve a la cola.
        for it in self.items:
            if it["estado"] == "procesando":
                it.update(estado="pendiente", etapa="en_cola", progreso=0, mensaje="Reanudado tras reiniciar")
        self._guardar()

    # ---------- persistencia ----------
    def _guardar(self) -> None:
        BASE.mkdir(parents=True, exist_ok=True)
        tmp = COLA.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": self.items}, ensure_ascii=False, indent=1))
        tmp.replace(COLA)

    def item(self, id_: str) -> dict | None:
        return next((i for i in self.items if i["id"] == id_), None)

    # ---------- entrada ----------
    def anadir(self, archivo: Path, perfil: str) -> tuple[dict | None, bool]:
        """Añade un vídeo. Devuelve (item, es_duplicado)."""
        from preparar_fuente import sha1_corto
        h = sha1_corto(archivo)
        with self.cerrojo:
            previo = next((i for i in self.items if i["hash"] == h and i["estado"] != "error"), None)
            if previo:
                return previo, True
            it = {"id": uuid.uuid4().hex[:10], "nombre": archivo.name, "perfil": perfil, "archivo": str(archivo),
                  "hash": h, "estado": "pendiente", "etapa": "en_cola", "progreso": 0, "mensaje": "",
                  "creado": ahora(), "iniciado": None, "terminado": None, "duracion_s": None, "veredicto": None,
                  "avisos": [], "error": None, "intentos": 0, "trabajo": None, "final": None, "salida": None,
                  "portada": None, "uso": None}
            self.items.append(it)
            self._guardar()
            return it, False

    def escanear_entrada(self) -> None:
        """Vídeos soltados en entrada/<perfil>/ (ignora ocultos y archivos que aún se están copiando)."""
        conocidos = {i["archivo"] for i in self.items}
        for perfil in perfiles():
            carpeta = BASE / "entrada" / perfil
            carpeta.mkdir(parents=True, exist_ok=True)
            for f in sorted(carpeta.iterdir()):
                if f.name.startswith(".") or f.suffix.lower() not in EXTENSIONES or str(f) in conocidos:
                    continue
                if time.time() - f.stat().st_mtime < 5:  # tamaño estable ≥ 5 s
                    continue
                self.anadir(f, perfil)

    def reintentar(self, id_: str) -> bool:
        with self.cerrojo:
            it = self.item(id_)
            if not it or it["estado"] not in ("error", "pausado_por_limite"):
                return False
            it.update(estado="pendiente", etapa="en_cola", progreso=0, mensaje="Reintento manual", error=None, intentos=0)
            self._guardar()
            return True

    # ---------- motor ----------
    def hechos_hoy(self) -> int:
        hoy = datetime.now().date().isoformat()
        return sum(1 for i in self.items if i["terminado"] and i["terminado"].startswith(hoy)
                   and i["estado"] in ("listo", "revisar"))

    def siguiente(self) -> dict | None:
        with self.cerrojo:
            return next((i for i in self.items if i["estado"] in ("pendiente", "pausado_por_limite")), None)

    def procesar(self, it: dict) -> None:
        from decidir import LimiteDeUso
        from editar import editar
        ajustes = leer_ajustes()
        perfil_dir = RAIZ / "perfiles" / it["perfil"]

        def avisar(estado: dict) -> None:
            with self.cerrojo:
                it.update(etapa=estado["etapa"], progreso=estado["progreso"], mensaje=estado["mensaje"],
                          trabajo=estado["trabajo"])
                # En cuanto el original se mueve al trabajo, la cola apunta allí (sobrevive a reinicios).
                movido = Path(estado["trabajo"]) / "original" / Path(it["archivo"]).name
                if movido.exists():
                    it["archivo"] = str(movido)
                self._guardar()

        with self.cerrojo:
            it.update(estado="procesando", iniciado=ahora(), intentos=it["intentos"] + 1, error=None, trabajo=None)
            self._guardar()
        try:
            archivo = Path(it["archivo"])
            mover = archivo.parent.parent.name == "entrada"  # solo se mueve lo que está en entrada/ (una vez)
            r = editar(archivo, perfil_dir, ajustes["carpeta_salida"], avisar, mover_original=mover)
            with self.cerrojo:
                it.update(estado="revisar" if r["veredicto"] == "REVISAR" else "listo", veredicto=r["veredicto"],
                          avisos=r["avisos"], terminado=ahora(), duracion_s=r["duracion_video_s"], trabajo=r["trabajo"],
                          final=r["final"], salida=r["salida_usuario"], portada=r["portada"], progreso=100,
                          etapa="terminado", uso={"coste_claude_estimado_usd": r["coste_claude_estimado_usd"],
                                                  "modelos": r["modelos_claude"],
                                                  "minutos_transcritos": r["minutos_transcritos"],
                                                  "duracion_ejecucion_s": r["duracion_ejecucion_s"]})
                if mover:
                    it["archivo"] = str(Path(r["trabajo"]) / "original" / archivo.name)
        except LimiteDeUso as e:
            with self.cerrojo:
                self.pausado_hasta = datetime.now() + PAUSA_LIMITE
                it.update(estado="pausado_por_limite", etapa="en_cola", progreso=0, intentos=it["intentos"] - 1,
                          mensaje=f"Límite de uso de Claude: se reintenta a las {self.pausado_hasta:%H:%M}",
                          error=str(e)[:300])
        except Exception as e:  # noqa: BLE001 — cualquier fallo de un vídeo no debe parar la cola
            log = traceback.format_exc()
            with self.cerrojo:
                trabajo = self._trabajo_de(it)
                if trabajo:
                    (trabajo / "log.txt").write_text(log, encoding="utf-8")
                if it["intentos"] < INTENTOS:
                    it.update(estado="pendiente", etapa="en_cola", progreso=0, mensaje="Reintentando tras un fallo",
                              error=str(e)[:500])
                else:
                    it.update(estado="error", terminado=ahora(), mensaje="Falló dos veces", error=str(e)[:500])
                    if trabajo:
                        destino = BASE / "errores" / trabajo.name
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        (trabajo / "motivo.txt").write_text(str(e), encoding="utf-8")
                        shutil.move(str(trabajo), destino)
                        # El original viaja con el trabajo: se actualiza su ruta para poder reintentar.
                        orig = destino / "original" / Path(it["archivo"]).name
                        if orig.exists():
                            it["archivo"] = str(orig)
                        it["trabajo"] = str(destino)
        finally:
            with self.cerrojo:
                self._guardar()

    def _trabajo_de(self, it: dict) -> Path | None:
        """Carpeta de trabajo del vídeo (editar.py la comunica en su primer aviso de progreso)."""
        return Path(it["trabajo"]) if it.get("trabajo") and Path(it["trabajo"]).exists() else None

    def bucle(self, parar: threading.Event) -> None:
        """Hilo del motor: vigila la entrada y procesa los vídeos de uno en uno."""
        while not parar.is_set():
            try:
                self.escanear_entrada()
                if self.pausado_hasta and datetime.now() < self.pausado_hasta:
                    parar.wait(10)
                    continue
                self.pausado_hasta = None
                it = self.siguiente()
                if not it or self.hechos_hoy() >= leer_ajustes()["limite_diario"]:
                    self.trabajando = False
                    parar.wait(5)
                    continue
                self.trabajando = True
                self.procesar(it)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                parar.wait(10)
        self.trabajando = False
