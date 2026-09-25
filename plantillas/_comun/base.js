/* Utilidades comunes de las plantillas (sin aleatoriedad ni tiempo real: render determinista).

   Variables de la composición (declaradas en <html data-composition-variables>):
     fondo, primario, acento : colores del perfil
     duracion                : duración de la ventana en segundos (la raíz ya lleva data-duration)
     datos                   : JSON (string) con el contenido; lo valida schema.json de la plantilla

   Reglas de animación (6.4): easing cúbico siempre (en GSAP, "power2" = cúbico), nunca
   lineal; un elemento nuevo cada vez; último estado sostenido ≥ 1 s; el panel nunca
   queda totalmente estático (deriva sutil). */
(function () {
  const vars = (window.__hyperframes && window.__hyperframes.getVariables()) || {};
  const raiz = document.documentElement.style;
  if (vars.fondo) raiz.setProperty("--fondo", vars.fondo);
  if (vars.primario) raiz.setProperty("--primario", vars.primario);
  if (vars.acento) raiz.setProperty("--acento", vars.acento);

  const HF = {
    vars,
    datos: typeof vars.datos === "string" ? JSON.parse(vars.datos || "{}") : vars.datos || {},
    duracion: Number(vars.duracion) || 3,
    EASE_ENTRADA: "power2.out",
    EASE_SUAVE: "power2.inOut",
    REVELADO: 0.4, // segundos que tarda un elemento en "aterrizar"
    SOSTENER: 1.0, // el último aterrizaje debe dejar ≥ 1 s de plano sostenido

    /* Momento de inicio para que el elemento aterrice en t (nunca antes de 0). */
    inicioRevelado(t, revelado = HF.REVELADO) {
      return Math.max(0, t - revelado);
    },

    /* Limita un aterrizaje para que quede tiempo de sostener el último estado. */
    limitar(t) {
      return Math.min(Math.max(0, t), Math.max(0, HF.duracion - HF.SOSTENER));
    },

    /* Aparición estándar: sube 40 px y funde, aterriza exactamente en t.
       Si t = 0, el elemento ya está aterrizado en el frame 0. */
    revelar(tl, el, t, opciones = {}) {
      const r = opciones.revelado ?? HF.REVELADO;
      const fin = HF.limitar(t);
      const desde = { opacity: 0, y: opciones.y ?? 40, scale: opciones.escala ?? 1 };
      const hasta = { opacity: 1, y: 0, scale: 1 };
      if (fin === 0) {
        tl.set(el, hasta, 0);
        return;
      }
      const dur = Math.min(r, fin);
      tl.fromTo(el, desde, { ...hasta, duration: dur, ease: HF.EASE_ENTRADA }, fin - dur);
    },

    /* Deriva sutil de todo el contenido durante la ventana (el panel nunca está quieto). */
    deriva(tl, el, escala = 1.02) { // 1,02 no saca del área útil lo que la llena
      tl.fromTo(el, { scale: 1 }, { scale: escala, duration: HF.duracion, ease: HF.EASE_SUAVE }, 0);
    },

    /* Tamaño de letra aproximado para que un texto quepa en una caja (determinista:
       no mide el DOM, que depende de que la fuente ya esté cargada). */
    tamanoTexto(texto, ancho, alto, maximo = 130, minimo = 44, ratio = 0.58, interlineado = 1.08) {
      const palabras = String(texto).split(/\s+/).filter(Boolean);
      const larga = Math.max(...palabras.map((p) => p.length), 1);
      for (let px = maximo; px >= minimo; px -= 2) {
        if (larga * px * ratio > ancho) continue;
        // Simula el reparto en líneas.
        let lineas = 1, actual = 0;
        for (const p of palabras) {
          const w = (p.length + 1) * px * ratio;
          if (actual + w > ancho && actual > 0) { lineas += 1; actual = w; } else { actual += w; }
        }
        if (lineas * px * interlineado <= alto) return px;
      }
      return minimo;
    },

    /* Color del perfil ya resuelto (GSAP no interpola var(--x)). */
    color(nombre) {
      return getComputedStyle(document.documentElement).getPropertyValue("--" + nombre).trim();
    },

    /* Iconos SVG en línea (render_plantillas.py los inyecta en la variable "svgs"). */
    svgs: typeof vars.svgs === "string" ? JSON.parse(vars.svgs || "{}") : vars.svgs || {},

    /* Crea el <svg> de un icono del catálogo, con el trazo en el color indicado. */
    svg(nombre, clase = "icono") {
      const marcado = HF.svgs[nombre];
      if (!marcado) throw new Error("icono no inyectado: " + nombre);
      const tmp = document.createElement("div");
      tmp.innerHTML = marcado;
      const el = tmp.querySelector("svg");
      el.removeAttribute("width");
      el.removeAttribute("height");
      el.setAttribute("class", clase);
      return el;
    },

    /* Dibuja los trazos de un icono (efecto "a mano") terminando exactamente en t.
       getTotalLength es geometría pura: no depende de fuentes, es determinista. */
    dibujar(tl, svgEl, t, dur = 0.7) {
      const fin = HF.limitar(t);
      const trazos = svgEl.querySelectorAll("path, line, circle, rect, polyline, polygon, ellipse");
      trazos.forEach((p) => {
        const largo = p.getTotalLength ? Math.ceil(p.getTotalLength()) + 1 : 100;
        p.style.strokeDasharray = largo;
        if (fin === 0) { p.style.strokeDashoffset = 0; return; }
        tl.fromTo(p, { strokeDashoffset: largo }, { strokeDashoffset: 0, duration: Math.min(dur, fin), ease: HF.EASE_SUAVE },
          Math.max(0, fin - dur));
      });
    },

    /* Registra la línea de tiempo raíz (una sola, pausada, finita). */
    registrar(tl, id = "main") {
      tl.set({}, {}, HF.duracion); // fija la duración exacta de la línea de tiempo
      window.__timelines = window.__timelines || {};
      window.__timelines[id] = tl;
      tl.seek(0);
    },
  };
  window.HF = HF;
})();
