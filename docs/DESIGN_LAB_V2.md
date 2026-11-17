# Macro Monitor · Laboratorio visual V2

## Abrir la demostración

Abre `design-lab-v2.html` con Chrome o Edge. Enlaces internos para revisión rápida: `#liquidez/dark`, `#opciones/cadena` y `#sentimiento/indicadores`. La página carga Plotly 2.35.2 desde el mismo CDN de Claude. Las series demostrativas están en el script del laboratorio. Si el CDN no responde, cada gráfico conserva una tabla de valores y un botón para reintentar.

## Inventario de partida

- Repositorio `brutodeibit/Macro-terminal`, base `5a553466a577f38c46e6f9c84a484514494b5399`. El README identifica `index.html` como portada. El historial muestra cambios compartidos con `claude-preview.html`, que también conserva su extensión `v7-ui.js` y sus contratos gráficos propios.
- `index.html` usa `macro-feed.json`; la vista Claude consume `macro-feed-v7.json` y extensión V7. Los renderizadores generan secciones HTML y montan gráficos Plotly después. Se revisaron el README, la configuración de dependencias y los flujos de actualización y validación. Las tres apariencias localizadas en Claude eran Azul noche, Grafito dorado y Carbón. Los cinco temas especificados están en esta demo.
- Referencias de seguridad locales: `backup/pre-index-promotion-20261108`, `backup/pre-v7-claude-2026-11-07` y la nueva `backup/pre-design-lab-v2-20261117`. El laboratorio vive en `design/lab-v2`.

## Componentes

| Bloque | Referencia reutilizada | Prototipo |
| --- | --- | --- |
| Navegación | Agrupación del Panel Global y funciones analíticas de Claude | Columna lateral, subpestañas con teclado y enlaces directos. En móvil la navegación superior admite desplazamiento horizontal. Montaje diferido y estado de cada panel en memoria durante la sesión. |
| Dark pools | Velas OHLC y controles de Plotly | Desplazamiento, ampliación horizontal por región o rueda, restablecimiento, tooltip y cruce en el eje temporal. Volumen en un panel alineado. Muestras de precio de ejecución y aproximado con símbolos diferentes. Intervalos 15 min, 1 hora y 1 día desde la misma serie sintética. |
| Sentimiento y ETF | Ejes separados en miedo/codicia y barras con signo de Claude | Fechas compartidas, bandas de sentimiento, BTC en USD, escala fija 0–100 y lectura histórica. Flujos con barras positivas y negativas, trama para distinguir ETH, vista diaria y cuatro semanas. |
| COT | Líneas y puntos por informe | Ventanas de 13, 26 o 52 semanas y leyenda por categoría; tooltip en contratos netos. |
| Opciones | Plotly, selección de activo/vencimiento, GEX, OI e IV de Claude | Columnas GEX con línea cero, OI agrupado y no negativo, IV ATM por vencimiento y tarjetas copiables. Los niveles corresponden a la muestra visual. |
| Otros | Organización de régimen, macro, amplitud, tipos y crédito | Tarjetas, comparativas, tablas expandibles y unidades diferenciadas. |

Los tres modos montan los mismos paneles y las mismas series. Esencial usa superficies planas y cambios instantáneos. Avanzado (predeterminado) añade elevación y transiciones suaves. Ultra añade iluminación localizada y perspectiva sólo en tarjetas, con ratón compatible. Los temas controlan superficies, acentos, contraste, bordes y paleta de gráficos. Las preferencias se guardan localmente. Movimiento reducido desactiva animaciones y perspectiva.

## Verificación y alcance

La prueba `tests/design-lab-v2.cjs` usa Chromium con Playwright. Puede ejecutarse con `node tests/design-lab-v2.cjs` y, si hace falta, `BROWSER_EXE` con la ruta a un Chromium instalado. Comprueba controles, escalas y series de la muestra, persistencia, gesto de ratón, estado de error del CDN y anchura móvil emulada. La fuente principal y su versión Claude se pueden comparar con el respaldo mediante `git diff backup/pre-design-lab-v2-20261117 -- index.html claude-preview.html v7-ui.js`.

Última pasada en Chrome sin ventana: mediana hasta el segundo fotograma de 33 ms en Esencial, 33 ms en Avanzado y 34 ms en Ultra (12 cambios de pestaña previamente cargada por modo). La prueba mide respuesta de navegación, no FPS sostenidos ni carga de CPU/GPU. La anchura de 390 px se verificó con emulación, sin dispositivo físico.

## Propuesta de integración, pendiente de revisión

1. Tras aprobar componentes concretos, abrir una rama de integración de prueba desde la versión vigente. Reusar en ella los renderizadores y adaptadores existentes de `index.html` y Claude según el módulo. Mantener las fuentes, fórmulas y transformaciones existentes.
2. Migrar primero tokens visuales y navegación. Conectar luego los cambios de presentación de Dark Pools, opciones y sentimiento a las trazas existentes. Verificar por separado los estados de carga, error, retraso y campos ausentes.
3. Comparar ambas interfaces con el mismo snapshot real: series, fechas, valores, unidades, vencimientos, niveles y etiquetas. Verificar escritorio y móvil con los datos disponibles, incluidas cadenas incompletas y ausencia de prints.
4. Presentar la rama de prueba y las diferencias antes de promover cambios. El mapa económico interactivo queda como posibilidad posterior.
