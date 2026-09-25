# pregunta

**Cuándo:** cuando el vídeo lanza una pregunta retórica al espectador ("¿Sigues haciendo esto a mano?") para abrir un bloque o crear tensión.

**Qué muestra:** la pregunta literal (≤ 7 palabras) en tipografía grande y centrada. Los signos ¿ y ? van en el color de acento, un poco más grandes y con brillo. Detrás hay un "?" gigante y muy tenue.

**Animación:** la entrada ocupa como mucho 0,9 s antes de `t_aterrizaje`. Primero el ¿ entra grande y girado y se asienta. Después las palabras suben una a una y, al final, el ? aterriza exactamente en `t_aterrizaje`, que es el momento de sincronía con el sonido. Justo después los dos signos laten una vez. Con `t_aterrizaje` = 0, la pregunta ya se lee en el frame 0. Si el valor cae en el último segundo, se adelanta para que el estado final se sostenga ≥ 1 s. La deriva de escala y el movimiento del resplandor y del "?" de fondo hacen que el panel nunca quede quieto.

**Datos:** ver `schema.json`. Si la pregunta llega sin ¿?, la plantilla los añade.
