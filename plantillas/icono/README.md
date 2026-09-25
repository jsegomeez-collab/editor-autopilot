# icono

**Cuándo:** la plantilla visual por defecto. Se usa cuando lo que se dice se puede representar con un objeto o un concepto (un cohete para "otro nivel", una papelera para "tirar a la basura", un candado para "seguridad"…). Tiene prioridad sobre `palabra_clave`.

**Qué muestra:** un icono de línea grande (Lucide) con glow y un anillo de acento que se dibuja alrededor. Rótulo opcional de ≤ 4 palabras dichas en la ventana.

**Movimientos (con significado):**
- `subir`: crecer, despegar.
- `caer`: tirar o perder. Con `icono_receptor`, el icono cae dentro de él.
- `latir`: aviso, importancia.
- `girar`: sistema, automatizar.
- `sacudir`: error, prohibido.
- `dibujar`: por defecto.

**Animación:** el icono aterriza en `t_aterrizaje` (al decir la palabra) con un destello de acento en el trazo. Después sigue en movimiento hasta el final.

**Sonido:** el de `datos.sonido` o, si no se indica, el del icono en `plantillas/_iconos/catalogo.yaml`.
