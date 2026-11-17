# Macro Monitor · vista de integración V2

Desde la raíz del repositorio, ejecuta `node scripts/serve-design-preview.cjs` y abre ambas vistas en Chrome o Edge.

- V2: http://127.0.0.1:8765/design-preview-v2.html
- Claude: http://127.0.0.1:8765/claude-preview.html
- Portada: http://127.0.0.1:8765/index.html

Las dos vistas Claude cargan la misma copia de `macro-feed-v7.json` y reutilizan sus renderizadores, fuentes y gráficos. El servidor se limita al equipo local. El indicador de la vista V2 identifica la copia local y muestra la fecha del feed. Cada serie conserva sus propias fechas y estados de cobertura.

La página de prueba activa la capa visual mediante `?design=v2`. En esa modalidad, el panel global monta las secciones a medida que se visitan. Las fichas de las nueve economías conservan su marcado y se distribuyen en sesgo semanal, tipos, banco central, lectura macro, curva e indicadores. Las pestañas preservan el contenido y las selecciones mientras la revisión del feed siga siendo la misma. Plotly difiere el dibujo en paneles ocultos. Se mantienen los intervalos y operaciones que entrega el feed.

La comprobación de integración es `node tests/design-preview-v2.cjs` con el servidor iniciado. Se ejecuta con Playwright y Chromium. `BROWSER_EXE` permite seleccionar Chrome o Edge ya instalado.

La integración queda en la rama local `design/integration-v2`. La aprobación de esta vista es independiente de una futura promoción a `index.html`.
