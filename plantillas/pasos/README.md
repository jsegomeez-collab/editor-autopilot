# pasos

**Cuándo:** cuando el vídeo explica un proceso en orden (de 2 a 5 pasos) y cada paso se dice en un momento concreto.

**Qué muestra:** un título opcional con una barra corta de acento y, debajo, los pasos en vertical. Cada paso lleva a la izquierda su número grande (1, 2, 3…) en el color de acento, con brillo, y a la derecha el texto (≤ 7 palabras). Una línea de acento une cada número con el siguiente.

**Animación:** cada paso aterriza exactamente en su `t`: el número crece y se funde, y el texto entra desde la izquierda. En esa misma ventana el conector crece desde el paso anterior y llega a la vez que el nuevo. El paso anterior se atenúa un poco, pero sigue siendo legible, de modo que el paso activo es siempre el último. Si un `t` cae en el último segundo, se adelanta para que el estado final se sostenga ≥ 1 s. El resplandor de fondo y una leve deriva de escala hacen que el panel nunca quede quieto.

**Datos:** ver `schema.json`. Los `t` van en segundos desde el inicio de la ventana y en orden creciente.
