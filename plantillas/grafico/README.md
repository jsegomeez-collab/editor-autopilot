# grafico

**Cuándo:** cuando en la ventana se comparan o se ven evolucionar 2–5 cifras dichas en el vídeo (crecimiento, antes/después con números, ranking). Todas las cifras tienen que decirse: nunca se inventan. Ojo: los números que aparezcan en `etiquetas` (p. ej. años) también cuentan como cifras dichas.

**Qué muestra:** un título opcional (≤ 7 palabras) y un gráfico de barras (`tipo: "barras"`) o de línea (`tipo: "linea"`). Cada barra o punto lleva su valor encima con la unidad en formato es-LatAm ("$30.000", "93%") y su etiqueta debajo. La escala es proporcional al máximo (base 0). La barra o punto mayor (la última si empatan) va en acento con resplandor.

**Animación:** primero entran el título y el eje. Después, las barras crecen de una en una (en la línea, cada tramo se dibuja hasta su punto), escalonadas cada 0,15–0,4 s, y la última aterriza exactamente en `t_aterrizaje`. El valor destacado da un pequeño golpe de escala al aterrizar. El conjunto y el resplandor derivan suavemente hasta el final (se sostiene ≥ 1 s).

**Datos:** ver `schema.json`.
