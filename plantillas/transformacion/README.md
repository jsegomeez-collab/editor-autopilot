# transformacion

**Cuándo:** cuando se dice que algo SE CONVIERTE en otra cosa o pasa de un estado a otro: "convierte tu proyecto en un mapa" (`folder` → `map`), "de idea a producto" (`lightbulb` → `package`), "de caos a sistema" (`shuffle` → `workflow`), "de gasto a inversión" (`wallet` → `trending-up`).

**Qué muestra:** dos círculos: A a la izquierda (blanco, que acaba apagado) y B a la derecha (icono y borde en acento, con glow), unidos por una flecha en arco punteada. Rótulos opcionales de ≤ 4 palabras bajo cada uno (B en acento).

**Animación:**
1. A aparece (escala + icono dibujado a mano) y aterriza en `t_a` (por defecto ~1 s antes de `t_aterrizaje`).
2. En los ~0,75 s previos a `t_aterrizaje`: el arco se traza de A hacia B, A se encoge, gira y se apaga, y un chorro de partículas amarillas sale de A y viaja por el arco.
3. En `t_aterrizaje` las partículas llegan y B aterriza (escala + giro, icono dibujado) con un destello: onda circular y rayos de acento.
4. Hasta el final: B flota y respira, el punteado del arco fluye, deriva suave. El rótulo de B aterriza 0,25 s después.

**Datos:** ver `schema.json` (`icono_a`, `icono_b`, `rotulo_a?`, `rotulo_b?`, `t_a?`, `sonido?`, `t_aterrizaje`).

**Sonido recomendado:** `transformacion` (whoosh + brillo) centrado en `t_aterrizaje`.
