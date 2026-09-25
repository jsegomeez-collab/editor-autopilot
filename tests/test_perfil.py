"""Tests del esquema de perfil (pipeline/perfil.py)."""
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "pipeline"))
from perfil import Perfil  # noqa: E402

EJEMPLO = yaml.safe_load((RAIZ / "perfiles/_ejemplo/perfil.yaml").read_text(encoding="utf-8"))


def test_ejemplo_valido():
    assert Perfil.model_validate(EJEMPLO).ritmo == "rapido"


@pytest.mark.parametrize("cambio", [
    {"colores": {**EJEMPLO["colores"], "acentos": ["#111111", "#222222", "#333333"]}},
    {"colores": {**EJEMPLO["colores"], "fondo": "negro"}},
    {"ritmo": "lento"},
    {"clave_inventada": 1},
    {"plantillas_permitidas": ["cifra", "lista"]},
    {"subtitulos": {"estilos_permitidos": ["contorno"], "estilo_por_defecto": "caja"}},
])
def test_errores_detectados(cambio):
    with pytest.raises(ValidationError):
        Perfil.model_validate({**EJEMPLO, **cambio})
