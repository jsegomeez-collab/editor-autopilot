# imagen

**Cuándo:** en una ventana `split` donde se menciona un término que tiene imagen en `perfiles/<marca>/imagenes/catalogo.yaml` (p. ej. "Claude Code") y no encaja una plantilla de datos (cifra, lista, pasos, comparativa, gráfico, alerta, pregunta). Tiene prioridad sobre `palabra_clave`. No se repite la misma imagen en dos ventanas seguidas.

**Qué muestra:**
- `captura`: la captura en una tarjeta con esquinas redondeadas, sombra y un zoom lento en el interior.
- `logo`: el logo sobre un resplandor suave, flotando.
- Pie opcional (≤ 4 palabras, dichas en la ventana).

**Animación:** la imagen aterriza en `t_aterrizaje`, cuando se dice el término. El pie entra 0,35 s después. Durante toda la ventana hay zoom o flotación y deriva.

**Datos:** ver `schema.json`. `archivo` es la ruta dentro de `imagenes/` del perfil, y `render_plantillas.py` la copia al slot en `media/`.
