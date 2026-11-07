# Claude V7 — consolidación y evidencia

Fecha de trabajo: 7 de noviembre de 2026. Base `a79564a`. Respaldo: rama `backup/pre-v7-claude-2026-11-07`.

La entrega afecta a `claude-preview.html`, su extensión `v7-ui.js`, el feed aislado `macro-feed-v7.json` y los recolectores/pruebas. `index.html` conserva el blob Git `d41eb31711158bbac4bd772b94cc0d61ebf4f780`. No se ha convertido Claude en página principal. No se han contratado servicios.

## Inventario de implementación

| Bloque | Implementado | Evidencia y límite |
|---|---|---|
| Actualización | Workflow de preview con frecuencias por fuente, guardado atómico, conservación ante errores; workflow principal elimina aserciones sobre literales obsoletos y publica solo JSON sin resets | El fallo DAV-21 estaba en la comprobación de `tr3:nval(...)`, después de recolectar correctamente. Python/Node verifican comportamiento. Ejecución remota y publicación se comprueban por separado |
| Bancos centrales | Descubrimiento oficial, archivo persistente, identidad banco/fecha y ventana de tres reuniones sin duplicados. Alemania comparte BCE. Cadencia por banco: 24 h fuera de reuniones y 2 h alrededor del evento | Ocho bancos tienen tres fechas oficiales. BCE de julio/septiembre y RBNZ se recuperaron mediante revisión directa de documentos y bootstrap explícito; no se presenta ese bootstrap como descarga automática exitosa |
| Curvas | Treasury 3M–30Y, curva BCE AAA 3M–30Y y benchmarks de Canadá; históricos, 1D/5S/21S/YTD en pb; gráfico Plotly de 480 px con comparativas | Treasury: 6/11; BCE y Canadá: 5/11 en las consultas. ECB es una curva Svensson estimada oficial de cupón cero; no un bono alemán ni interpolación propia. Canadá LT no equivale a un 30Y exacto. Letras diarias canadienses devuelven 404 |
| FX | Se excluyen observaciones caducadas, 2Y y tipos reales sin fecha. Umbral de cobertura coherente entre tabla y matriz, sin prima fija CHF/JPY | Test de antisimetría. Pesos existentes conservados. La actualización general del feed ya no renueva artificialmente la fecha del FX. No se fuerzan sesgos cuando falta macro vigente |
| Opciones | Cboe con hora AM/PM, dependencia tzdata para Windows, DJX separado de DJI/DIA, PCR de la misma expiración; cálculo de Gamma Flip revalorado y prueba analítica; no se usa el modelo de acciones para VIX | 27 instrumentos en snapshot, cobertura desigual. 64 perfiles de acciones/ETF/índices con metadatos de modelo. Un campo null significa sin cálculo válido. No hay contraste numérico con un proveedor especializado de metodología idéntica |
| Familias | EURO STOXX distingue SX5E/FEZ de SXXP/EXSA. Crédito HYG/LQD y duración TLT/SGOV siguen separados. Sin tarjetas de futuros vacías | SXXP/EXSA identifican el producto; no se inventa una cadena. EWG sigue siendo MSCI Germany, no DAX. No se ha demostrado que EXSA sea el ETF óptimo por liquidez de opciones |
| Dark pools | Velas OHLC reales de un año cuando existen; filtro de fechas, tamaños/lado existentes, trazos discontinuos, opacidad/grosor y etiquetas con colocación que penaliza solapamientos | En el snapshot consultado hay cero prints individuales verificables. La capa preparada no es evidencia de operaciones. ATS/OTC conserva semana y clasificación agregada |
| COT | Conservada interacción y categorías existentes; mayor altura, ventanas cortas con cambios semanales y paneles verticales para escalas | Se conserva frecuencia semanal. No se afirma disponer de publicación intradía |
| Cripto | Un gráfico interactivo F&G/BTC de 550 px con bandas y dos ejes; mini historial; módulo ETF separado entre sentimiento y bonos; un histograma BTC/ETH con diario/semanal e histórico navegable | Farside BTC y ETH: 90 observaciones, última 6/11. Se verifican signos, fechas y columna Total. Ausencia no se convierte en cero. Valores del día abierto se excluyen conservadoramente |
| Estética | Base Claude conservada, temas night/carbon/warm aplicados a tarjetas y gráficos, códigos de país como fallback consistente de banderas, pan/zoom/restauración conservados | Configuraciones de gráficos comprobadas con datos reales. Navegador local deshabilitado: falta QA visual real de escritorio/móvil |
| Radar futuro | Contrato `weeklyFxSchema`, fuentes y snapshots reutilizables | Se conserva el radar existente; no se cierra el nuevo estilo narrativo ni se modifican agentes o cartera |

## Modelo y vigencia de opciones

El Gamma Flip busca raíces de la suma de gamma revalorada mediante Black–Scholes a precios entre 70% y 130% del spot. Usa OI, IV constante por strike, tiempo restante de cada contrato y multiplicador 100 para las cadenas estadounidenses compatibles. Supuesto explícito: calls positivas y puts negativas; no es inventario observado de dealers. Requiere al menos 90% del OI con IV utilizable y ambos tipos. Guarda todos los cruces y el más próximo al spot, sensibilidad a OI put ±20% y IV ±10%. Los tipos/dividendos son supuestos visibles, no estimaciones implícitas verificadas. No se mezcla con el cruce acumulado por strikes.

Max Pain minimiza el pago intrínseco agregado sobre el OI disponible; test contra cálculo exhaustivo. Walls OI no son walls gamma. PCR OI y PCR de volumen no describen lo mismo. IV ATM se expresa en puntos porcentuales, incluso cuando es inferior a 3%; el gráfico no la multiplica por 100 por heurística.

Los snapshots diarios comienzan con datos realmente capturados. No hay cinco sesiones históricas de posicionamiento inventadas. El histórico se describe como fechas de snapshot cuando el proveedor no entrega una sesión bursátil inequívoca. Faltan calendarios completos de festivos/medias sesiones y la antigüedad exacta del OI por contrato. VIX requiere un modelo sobre forward; el flip se deja ausente.

Referencias: [especificación DJX](https://www.cboe.com/tradable-products/dow-jones/dow-jones-industrial-average-options/djx-specifications/), [ODAX](https://www.eurex.com/ex-en/markets/idx/dax/DAX-Options-139884), [EWG](https://www.ishares.com/us/products/239650/ishares-msci-germany-etf), [EXSA](https://www.borsaitaliana.it/borsa/etf/scheda/DE0002635307-ETFP.html).

DJIA es el índice; Yahoo usa `^DJI`. DJX son opciones Cboe sobre 1/100 del índice, con multiplicador contractual 100; DIA es un ETF distinto. Tener un precio DAX/SX5E/SXXP no proporciona automáticamente OI, IV ni una cadena completa. Eurex publica productos y estadísticas, pero no se ha validado en este trabajo un conector gratuito y redistribuible de cadenas completas ODAX/OESX/OXXP. No se ha usado la cuenta TradingView ni sorteado restricciones.

LQD aporta crédito investment grade, aunque mezcla exposición a tipos y spreads; complementa HYG. SGOV representa letras 0–3 meses y liquidez, no un “TLT corto” simétrico ni una fuente de GEX tan informativa como un índice de renta variable. Mantenerlos como contexto y habilitar métricas solo si la cadena las soporta. ICE BofA OAS es un indicador, no un ETF con opciones. El OAS HY existente no prueba que el IG esté conectado.

## Datos y cadencia

`generatedAt` fecha la generación del JSON; no demuestra la fecha de observación ni publicación. Los conectores nuevos guardan observedAt, publishedAt (null cuando no se conoce), fetchedAt, source, sourceUrl, status, unit y metodología. El contrato no está todavía normalizado en cada campo de todos los recolectores antiguos. `sourceHealth.processed` significa que se ejecutó el adaptador, no que todos sus proveedores hayan respondido. Advertencias específicas se conservan en `sourceWarnings`.

Preview: cron cada dos horas; fuentes con intervalos propios de 1–24 horas (el cron limita la frecuencia efectiva). COT se consulta como máximo una vez diaria, conserva su fecha semanal; no se simulan observaciones nuevas. ETF cada seis horas, prints/OHLC cada doce, curvas oficiales una vez diaria salvo Treasury. Principal: cada seis horas durante esta consolidación, en lugar de repetir la recolección completa cada quince minutos. Ambos escritores comparten exclusión mutua. Las consultas de reunión se aceleran solo para el banco cercano al evento; la lista de eventos 2026 necesita renovación oficial para 2027 y separar horas de decisión/conferencia. La hora BoJ de la lista heredada es orientativa, no hora fija de publicación verificada.

Fuentes comprobadas: [Treasury](https://home.treasury.gov/resource-center-data-chart-center/interest-rates), [curvas BCE y metodología](https://www.ecb.europa.eu/stats/financial_markets_and_interest_rates/euro_area_yield_curves/html/index.en.html), [Banco de Canadá](https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/), [Farside BTC](https://farside.co.uk/bitcoin-etf-flow-all-data/), [Farside ETH](https://farside.co.uk/ethereum-etf-flow-all-data/). Las URLs individuales de reuniones están en el feed y en `v7-meeting-bootstrap.json`.

## Auditoría de indicadores por economía

Propuestas estratégicas: no se añaden automáticamente todas las filas. Una sorpresa requiere consenso de la misma variable, unidad y período; una previsión del proveedor no equivale a encuesta. La importancia intradía depende de lo descontado y de la respuesta del 2Y/FX. Frecuencias: M mensual, T trimestral, S semanal, E reunión/evento.

| Economía | Mantener | Añadir o verificar cobertura | Reducir prioridad | Eliminar |
|---|---|---|---|---|
| USD | CPI/core, PCE/core (M), NFP/desempleo/AHE (M), claims (S), FOMC (E), ISM (M), PIB (T) | PPI componentes que anticipan PCE; empleo revisado y salario real como contexto, sin duplicar AHE nominal | JOLTS abandonos/vacantes frente a empleo actual; confianza general si no cambia demanda | Copias de CPI/PCE con traducciones distintas; niveles de índice mostrados como inflación; consenso de otro período |
| EUR | HICP general/core (M), PIB (T), desempleo (M), BCE (E), PMI compuesto (M) | Servicios HICP y salarios negociados/tracker, separando frecuencia y calendario real: persistencia y reacción del 2Y | Confianza secundaria y múltiples PMI correlacionados | Tratar Alemania como banco central separado; contar flash y final del mismo período como dos sorpresas independientes |
| GBP | CPI/core/servicios, empleo y salarios (M), PIB mensual y BoE (E) | Salario regular privado, revisiones y calidad muestral del mercado laboral; renta disponible si mejora interpretación de demanda | PMI componentes secundarios y confianza de hogares | Mezclar salario con/sin bonus o tasas trimestrales e interanuales en una sorpresa |
| JPY | CPI nacional/Tokio (M), salarios nominales/reales (M), BoJ (E), PIB/Tankan (T) | Remuneración base y revisiones, acuerdo salarial anual contextual separado de salario efectivamente pagado | Producción/exportaciones mensuales aisladas | Prima refugio fija y usar Nikkei como fortaleza mecánica del yen |
| CHF | CPI (M), SNB (E), PIB (T), desempleo (M) | Expectativas SNB solo con fuente verificable; tipo de cambio efectivo como contexto de inflación importada | Encuestas secundarias y comercio de metales que distorsione exportaciones | Prima refugio constante o fortaleza del SMI como señal directa del CHF |
| CAD | CPI/core trim/median (M), empleo/salarios (M), PIB M/T, BoC (E) | Revisiones de empleo y componentes de inflación que afecten persistencia; curva Valet conectada | Ventas minoristas nominales sin deflactar y encuestas redundantes | Duplicar PIB mensual/trimestral sin distinguir referencia; petróleo = CAD alcista automático |
| AUD | CPI mensual completo, empleo (M), salarios/PIB (T), RBA (E) | Media recortada con su frecuencia correcta y consumo real; exposición a China como contexto, no dato australiano | Encuestas privadas redundantes | Antiguo indicador CPI mensual parcial tratado como equivalente al mensual completo |
| NZD | CPI/empleo/salarios/PIB (T), RBNZ (E) | Inflación no transable y expectativas, con período explícito: útiles para la reacción del 2Y | Encuestas de confianza sin contraste con actividad | Copias trimestrales fechadas como si fueran nuevas publicaciones mensuales |
| Alemania | HICP/CPI (M), PIB (T), Ifo (M), producción/pedidos como contexto | Revisiones y contribución alemana al agregado euro, sin sumarla dos veces | ZEW y desgloses industriales secundarios cuando Ifo/PMI ya explican el cambio | Banco central alemán ficticio y doble contabilización en matriz EUR |

La elección anterior prioriza persistencia de inflación/salarios y capacidad productiva para expectativas monetarias; empleo/actividad contrastan riesgos de crecimiento. Las publicaciones mensuales principales suelen ser catalizadores de sesión y de preparación semanal; PIB, salarios negociados y Tankan aportan más contexto que una señal intradía continua. Se mantiene explícita la diferencia entre dato económico favorable y reacción de la divisa.

La transición australiana a CPI mensual completo está documentada por [ABS](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/nov-2025) y [RBA](https://www.rba.gov.au/publications/smp/2025/nov/box-c-the-transition-to-a-complete-monthly-cpi.html).

## Monitor estadístico: revisión, sin nuevo motor

`statistical-monitor.html` ya muestra observaciones, período, retornos, drawdown, medias, mediana de profundidad, P25/P75 y estacionalidad con n. `update_stats.py` contiene el motor existente; no se crea otro dentro de Claude. El contexto rápido debe limitarse a tamaño de muestra, rango típico/mediana y percentiles, régimen y enlace al estudio profundo.

Hallazgos pendientes para el proyecto especializado: IDs `pbRec` y `pbDepth` duplicados en el HTML; conversiones null→0; cuantiles vacíos convertidos a cero; profundidad del primer día de un retroceso no incorporada al iniciarlo; episodios abiertos al final de muestra y censura a diez sesiones; volatilidad/mediana incluyen la barra evaluada; estacionalidad por día civil UTC sin sesión local explícita; falta comparación por régimen/evento, incertidumbre, mínimos/máximos/duración de forma uniforme y prueba fuera de muestra. No se deben interpretar promedios con n pequeño como predicción ni comparar índices de precio y retorno total sin normalizarlos.

## Pruebas y límites de cierre

- 15 tests Python: transformaciones financieras, Farside, fechas, Max Pain exhaustivo, raíz Gamma Flip analítica, ausencia de IV/cruce, cadencia por evento y puntos básicos.
- Ocho renderizadores ejecutados para principal y Claude; antisimetría FX, enlaces de tres reuniones y vencimiento intradía.
- Contratos de gráficos con el feed real: un F&G y un ETF, ejes independientes, signos, histórico, pan/rueda y exclusión de lasso/box select, unidades IV y etiquetas escalonadas.
- Compilación Python y sintaxis JavaScript. `git diff --check`. Hash de `index.html` idéntico.
- Vídeo revisado mediante extracción de un fotograma (3 s): barras netas, selector temporal e interacción como referencia; no constituye prueba de fluidez de esta implementación.
- No se ha podido inspeccionar la web renderizada en navegador local: el control de navegador está deshabilitado. No se afirma haber pasado QA visual móvil/escritorio.

Pendientes reales: automatización completa de documentos/votaciones/resúmenes y calendario 2027; curvas oficiales restantes y fechas de algunos datos heredados; consensos y probabilidades de mercado verificables; cadenas completas europeas; modelo VIX basado en forward y contraste externo del flip; fuente legal de prints individuales; sesiones reducidas/horarios exactos en todos los instrumentos; datos históricos de posicionamiento que solo podrán acumularse desde capturas nuevas. Los paneles parciales no se rellenan con números ni probabilidades inventados.

Linear: DAV-8, DAV-20 y DAV-21 se actualizan con evidencia; no corresponde cerrarlos mientras subsistan los puntos anteriores. No se crean tareas duplicadas.
