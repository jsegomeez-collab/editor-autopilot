# comparativa

**Cuándo:** cuando el vídeo enfrenta dos ideas: antes/después, mito/realidad, lo que hace la mayoría frente a lo que propones, herramienta X frente a Y.

**Qué muestra:** dos tarjetas en columnas. Cada una lleva un rótulo corto en mayúsculas (`titulo`) y la idea (`texto`, ≤ 7 palabras). En el centro, un sello "vs". La tarjeta derecha es la que gana: borde, rótulo y resplandor en el color de acento, con el texto en blanco pleno. La izquierda queda atenuada.

**Animación:** la tarjeta izquierda sube y aterriza en `t_izquierda`. Si hay al menos 0,5 s de hueco, el "vs" aparece a mitad de camino (si no, junto con la izquierda). La tarjeta derecha aterriza en `t_derecha` con un pequeño golpe de escala, y en ese momento la izquierda se atenúa. El conjunto y el resplandor derivan suavemente hasta el final (se sostiene ≥ 1 s).

**Datos:** ver `schema.json`.
