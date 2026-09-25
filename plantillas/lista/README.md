# lista

**Cuándo:** cuando el vídeo enumera de 2 a 4 cosas (ventajas, herramientas, errores…) y cada una se nombra en un momento concreto.

**Qué muestra:** un título opcional con una barra corta de acento y, debajo, un punto por elemento: una tarjeta gris oscura semitransparente con una viñeta de acento y el texto (≤ 7 palabras).

**Animación:** cada punto sube y se funde para aterrizar exactamente en su `t`. Así se sincroniza con la voz y con el click de sonido. El punto recién aparecido lleva un marco y un brillo de acento. Los anteriores pierden el marco y se atenúan un poco, pero siguen siendo legibles. Si un `t` cae en el último segundo, se adelanta para que el estado final se sostenga ≥ 1 s. El resplandor de fondo y una leve deriva de escala hacen que el panel nunca quede quieto.

**Datos:** ver `schema.json`. Los `t` van en segundos desde el inicio de la ventana y en orden creciente.
