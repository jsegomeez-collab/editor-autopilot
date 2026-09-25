"""Gráficos de prueba de JOSE49 (versión "dopamínica"): ventanas split + stickers en las full.
Genera <edit>/graficos.json a partir de <edit>/layout.json. Uso: python este.py <edit>"""
import json, sys
from pathlib import Path

E = Path(sys.argv[1])
SPLIT = {
 "0.00":  ("gancho", {"titular": "Nunca uses Claude Code", "destacado": "Claude Code", "t_aterrizaje": 0}),
 "2.83":  ("icono", {"icono": "rocket", "movimiento": "subir", "rotulo": "otro nivel", "destacado": "nivel", "t_aterrizaje": 0.93}),
 "4.24":  ("red", {"icono_centro": "terminal", "iconos": ["puzzle", "sparkles", "map", "boxes"], "cantidad": 4, "rotulo": "complementos", "t_aterrizaje": 1.42}),
 "8.08":  ("transformacion", {"icono_a": "puzzle", "icono_b": "bot", "rotulo_b": "Claude Code", "t_a": 0.60, "t_aterrizaje": 1.84}),
 "12.48": ("icono", {"icono": "wand-sparkles", "movimiento": "latir", "rotulo": "Ponytail", "t_aterrizaje": 0.60}),
 "14.94": ("crecimiento", {"icono": "coins", "direccion": "baja", "rotulo": "menos tokens", "t_aterrizaje": 0.64}),
 "19.41": ("transformacion", {"icono_a": "battery-low", "icono_b": "battery-charging", "rotulo_a": "sin uso", "t_a": 0.99, "t_aterrizaje": 1.37}),
 "21.36": ("transformacion", {"icono_a": "folder", "icono_b": "map", "rotulo_a": "tu proyecto", "rotulo_b": "un mapa", "t_a": 1.52, "t_aterrizaje": 2.18}),
 "27.32": ("red", {"icono_centro": "package", "iconos": ["brain", "pen-tool", "code", "chart-line", "search", "megaphone"], "cantidad": 24, "rotulo": "habilidades", "t_aterrizaje": 1.28}),
 "31.64": ("imagen", {"archivo": "claude/logo.png", "tipo": "logo", "pie": "Claude", "t_aterrizaje": 0.04}),
 "33.68": ("uno_vs_muchos", {"iconos": ["code", "pen-tool", "chart-line", "megaphone", "mail"], "rotulo": "una sola persona", "t_aterrizaje": 1.74}),
 "38.27": ("transformacion", {"icono_a": "workflow", "icono_b": "hand-coins", "rotulo_a": "sistemas", "rotulo_b": "paguen", "t_a": 0.11, "t_aterrizaje": 1.39}),
 "42.62": ("icono", {"icono": "gift", "movimiento": "latir", "rotulo": "master class", "destacado": "master", "t_aterrizaje": 0.58}),
 "44.84": ("crecimiento", {"icono": "circle-dollar-sign", "valor": 10000, "prefijo": "$", "rotulo": "mensuales", "direccion": "sube", "sonido": "moneda", "t_aterrizaje": 1.88}),
 "47.72": ("cta", {"linea1": "Escribe", "linea2": "la palabra", "palabra": "SISTEMAS", "t_aterrizaje": 0.76}),
}
# Stickers en ventanas full: (inicio absoluto, duración, icono, lado, rótulo); aterrizan 0,25 s tras su inicio.
STICKERS = [
 (1.99, 1.10, "puzzle", "derecha", "complementos"),
 (6.65, 1.20, "trash-2", "izquierda", "basura"),
 (10.61, 0.84, "flame", "derecha", "bestia"),
 (11.51, 0.92, "layers", "izquierda", "complejos"),
 (17.30, 1.00, "plug", "derecha", "conecta"),
 (18.61, 0.80, "server", "izquierda", "proveedores"),
 (24.57, 0.90, "map-pin", "derecha", "dónde"),
 (25.55, 0.55, "search", "izquierda", "revisar"),
 (26.15, 1.10, "files", "derecha", "archivos"),
 (30.81, 0.80, "brain", "izquierda", "IA"),
 (36.97, 1.20, "layers", "derecha", "completos"),
 (40.07, 0.90, "graduation-cap", "izquierda", "aprender"),
 (41.13, 0.70, "hammer", "derecha", "construir"),
]
layout = json.loads((E / "layout.json").read_text())
graficos = []
for i, v in enumerate(layout["ventanas"]):
    k = f"{v['inicio']:.2f}"
    if k in SPLIT:
        p, d = SPLIT[k]
        graficos.append({"id": f"v{i:02d}", "plantilla": p, "inicio": v["inicio"], "duracion": round(v["fin"] - v["inicio"], 3), "datos": d})
for j, (ini, dur, ico, lado, rot) in enumerate(STICKERS):
    graficos.append({"id": f"s{j:02d}", "plantilla": "sticker", "inicio": ini, "duracion": dur,
                     "datos": {"icono": ico, "lado": lado, "rotulo": rot, "t_aterrizaje": 0.25}})
(E / "graficos.json").write_text(json.dumps({"graficos": graficos}, ensure_ascii=False, indent=1))
print(len(graficos), "gráficos (", len(STICKERS), "stickers )")
