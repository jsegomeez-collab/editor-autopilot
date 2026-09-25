"""Esquema y validación del perfil de marca (`perfiles/<marca>/perfil.yaml`).

Uso:
  python pipeline/perfil.py perfiles/<marca>          # valida esquema y archivos
"""
from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

HEX = r"^#[0-9A-Fa-f]{6}$"

PLANTILLAS = Literal[
    "gancho", "cifra", "lista", "comparativa", "pasos",
    "pregunta", "palabra_clave", "alerta", "grafico", "cta",
]
ESTADOS_ANIMO = Literal["energetica", "inspiradora", "tension", "neutra", "emocional"]
# caja: bloques de 2 palabras sobre caja oscura semitransparente (6.5, por defecto).
# contorno: mismos bloques, sin caja, con contorno y sombra (alternativa para variantes).
ESTILOS_SUBTITULOS = Literal["caja", "contorno"]


class Estricto(BaseModel):
    """Base que rechaza claves desconocidas para detectar erratas en el YAML."""
    model_config = ConfigDict(extra="forbid")


class Identidad(Estricto):
    nombre: str
    idioma: Literal["es-ES", "es-LatAm"] = "es-ES"
    plataformas: list[Literal["instagram", "tiktok", "youtube_shorts"]] = Field(min_length=1)


class Colores(Estricto):
    fondo: str = Field(pattern=HEX)
    primario: str = Field(pattern=HEX)
    acentos: list[Annotated[str, Field(pattern=HEX)]] = Field(min_length=1, max_length=2)


class Fuente(Estricto):
    archivo: str  # relativo a perfiles/<marca>/
    familia: str  # nombre de familia interno (el que usa el ASS), no el del archivo


class Tipografias(Estricto):
    titulares: Fuente
    subtitulos: Fuente
    respaldo: Fuente


class Logo(Estricto):
    archivo: str
    uso: Literal["solo_cta"] = "solo_cta"  # nunca al inicio


class Layout(Estricto):
    patron: Literal["split-hook-oscilante"] = "split-hook-oscilante"
    transicion: Literal["corte", "push"] = "corte"


class Subtitulos(Estricto):
    estilos_permitidos: list[ESTILOS_SUBTITULOS] = ["caja", "contorno"]
    estilo_por_defecto: ESTILOS_SUBTITULOS = "caja"

    @model_validator(mode="after")
    def _defecto_permitido(self):
        if self.estilo_por_defecto not in self.estilos_permitidos:
            raise ValueError("estilo_por_defecto debe estar en estilos_permitidos")
        return self


class Niveles(Estricto):
    voz_lufs: float = -14.0
    musica_db_bajo_voz: float = Field(20.0, ge=18, le=22)
    sfx_db_bajo_pico_voz: float = Field(6.0, ge=6)


class Audio(Estricto):
    musica: bool = True
    estados_animo_permitidos: list[ESTADOS_ANIMO] = ["energetica", "inspiradora", "tension", "neutra", "emocional"]
    estado_animo_por_defecto: ESTADOS_ANIMO = "neutra"
    sfx: bool = True
    estilo_sfx: Literal["minimal", "energetico"] = "minimal"
    densidad_sfx: Literal["baja", "media", "alta"] = "media"
    niveles: Niveles = Niveles()

    @model_validator(mode="after")
    def _defecto_permitido(self):
        if self.estado_animo_por_defecto not in self.estados_animo_permitidos:
            raise ValueError("estado_animo_por_defecto debe estar en estados_animo_permitidos")
        return self


class ZonasSeguras(Estricto):
    superior: int = 220
    inferior: int = 380
    derecha: int = 120


class Perfil(Estricto):
    identidad: Identidad
    colores: Colores
    tipografias: Tipografias
    logo: Logo
    ritmo: Literal["rapido", "natural"] = "rapido"
    layout: Layout = Layout()
    subtitulos: Subtitulos = Subtitulos()
    audio: Audio = Audio()
    cta_por_defecto: str
    ctas_alternativos: list[str] = []
    duracion_objetivo_max_s: int = Field(gt=0)
    muletillas_extra: list[str] = []
    palabras_a_no_cortar: list[str] = []
    zonas_seguras: ZonasSeguras = ZonasSeguras()
    plantillas_permitidas: list[PLANTILLAS] = [
        "gancho", "cifra", "lista", "comparativa", "pasos",
        "pregunta", "palabra_clave", "alerta", "grafico", "cta",
    ]

    @field_validator("plantillas_permitidas")
    @classmethod
    def _obligatorias(cls, v: list[str]) -> list[str]:
        # gancho, cta y palabra_clave (respaldo) son necesarias para el pipeline.
        faltan = {"gancho", "cta", "palabra_clave"} - set(v)
        if faltan:
            raise ValueError(f"faltan plantillas obligatorias: {sorted(faltan)}")
        return v


def cargar(dir_perfil: Path) -> Perfil:
    """Carga y valida el perfil, incluidos los archivos que referencia."""
    datos = yaml.safe_load((dir_perfil / "perfil.yaml").read_text(encoding="utf-8"))
    perfil = Perfil.model_validate(datos)
    t = perfil.tipografias
    archivos = [t.titulares.archivo, t.subtitulos.archivo, t.respaldo.archivo, perfil.logo.archivo]
    faltan = [a for a in archivos if not (dir_perfil / a).is_file()]
    if faltan:
        raise FileNotFoundError(f"faltan archivos del perfil: {faltan}")
    return perfil


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dir_perfil = Path(sys.argv[1])
    try:
        perfil = cargar(dir_perfil)
    except (ValidationError, FileNotFoundError, ValueError) as e:
        sys.exit(f"❌ perfil no válido: {dir_perfil}\n{e}")
    print(f"✅ perfil válido: {perfil.identidad.nombre} ({dir_perfil})")


if __name__ == "__main__":
    main()
