# crecimiento

**Cuándo:** cuando se habla de progreso o de una tendencia: "llegar a $10.000 mensuales", "crecer tu negocio", "duplicar clientes", "las ventas caen un 40%" (`direccion: "baja"`). Si la cifra es el único protagonista y no hay idea de subida/bajada, usar `cifra`.

**Qué muestra:** una gráfica de tendencia sobre una rejilla sutil: curva amarilla con glow, área en degradado de acento, flecha en la punta y, opcional, un icono en un círculo que viaja con la punta. Arriba (a la izquierda si sube, a la derecha si baja, el hueco que deja la curva) la cifra con formato es-LatAm ("$10.000", "93%", "4,5%") y un rótulo de ≤ 4 palabras. Sin `valor`, el rótulo ocupa ese hueco en grande.

**Animación:** aparecen eje y rejilla; la curva se dibuja de izquierda a derecha (~1,2 s, `power2.inOut`) arrastrando área, flecha e icono, y el contador sube al mismo ritmo. En `t_aterrizaje` la punta llega arriba (o abajo) y la cifra alcanza su valor: se tiñe de acento con un golpe de escala, el icono destella y la punta emite ondas. Después: ondas periódicas en la punta, el icono flota, la rejilla se desplaza despacio y el conjunto deriva.

**Datos:** ver `schema.json` (`icono?`, `valor?`, `prefijo?`, `sufijo?`, `rotulo?`, `direccion?`, `sonido?`, `t_aterrizaje`). La cifra solo si se dice en la ventana (el pipeline lo verifica).

**Sonido recomendado:** `subida` (o `bajada` si baja) arrancando con el trazo y culminando en `t_aterrizaje`; con cifra de dinero, `moneda` en el aterrizaje.
