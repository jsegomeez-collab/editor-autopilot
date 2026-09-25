# red

**Cuándo:** cuando se habla de conectar, integrar o de una red: "lo conecta con 300 proveedores", "integraciones con tus herramientas", "tu red de clientes", "un agente que habla con todos tus sistemas". Es la "órbita" de los vídeos del cliente: un logo/concepto en el centro con satélites alrededor.

**Qué muestra:** un nodo central (icono o `texto_centro` de ≤ 2 palabras) con borde y glow de acento, y 3–8 satélites con iconos de línea sobre una órbita elíptica punteada. Opcional: contador `+N` en una píldora de acento bajo el centro (solo si la cifra se dice) y un rótulo de ≤ 4 palabras bajo la red.

**Animación:**
1. Aparece el centro (escala + el icono se dibuja a mano).
2. Las líneas se trazan de una en una hacia cada satélite, con un pulso de luz amarilla en la punta; el satélite se enciende al llegar (escala, icono dibujado, borde en acento). El contador `+N` sube mientras tanto.
3. En `t_aterrizaje` se enciende el último satélite: pulso general (onda de acento desde el centro, líneas e iconos en amarillo que vuelven a blanco) y el contador llega a su cifra.
4. Hasta el final: órbita lenta de los satélites y ondas de pulsos del centro hacia los satélites; deriva sutil del conjunto. El rótulo aterriza 0,3 s después.

**Datos:** ver `schema.json` (`icono_centro` o `texto_centro`, `iconos`, `cantidad?`, `rotulo?`, `sonido?`, `t_aterrizaje`).

**Sonido recomendado:** `red` (conexión/zumbido digital) en `t_aterrizaje`; con muchos satélites, opcionalmente `pop` suaves en cada encendido.
