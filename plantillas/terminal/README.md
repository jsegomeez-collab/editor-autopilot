# terminal

**Cuándo:** cuando se habla de USAR una herramienta de IA o de automatizar algo pidiéndoselo: «con Claude Code…», «le pides que…», «automatiza X», «escribes esto y…». Muestra el gesto de teclear una orden y ver cómo se ejecuta.

**Qué muestra:** una ventana de terminal tipo macOS (3 puntos, título opcional como «Claude Code» con un icono pequeño de acento), más oscura que el panel, con borde sutil y glow de acento. Dentro, de 1 a 4 líneas:
- `comando`: prompt `❯` (o `$`) en acento y el texto se teclea carácter a carácter.
- `salida`: aparece de golpe con un fundido corto, atenuada.
- `exito`: con ✓ en acento y un destello al aparecer.

**Animación:** la ventana aterriza en `t_aterrizaje` (sube y escala). Cada línea termina en su `t`: los comandos se teclean con un contador `power2.inOut` que revela caracteres (el hueco del texto se reserva, así la ventana no cambia de alto). Cursor de bloque en la línea activa, parpadeando con tiempos fijos. Barrido de luz y deriva sutil: nunca queda estática.

**Datos:** `titulo?` (≤ 4 palabras), `icono?` (catálogo; p. ej. `terminal`, `bot`), `prompt?` (`❯`|`$`), `lineas` [{`texto` ≤ 7 palabras, `t`, `tipo?`}] (1–4; por defecto la 1.ª es comando y el resto salida), `t_aterrizaje?` (si falta, 0,9 s antes de la primera línea), `sonido?`.

**Sonido recomendado:** tecleo/teclado durante los comandos; un «ding»/éxito suave en la línea `exito`.
