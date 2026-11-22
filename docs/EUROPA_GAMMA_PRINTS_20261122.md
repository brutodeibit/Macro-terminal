# Europa, Gamma Flip y cobertura de operaciones — 22/11/2026

## Estado de entrega

Implementación y datos de prueba reales en `codex/source-refresh-20261122`.
No fusionado ni publicado en Pages. El feed generado se conserva localmente,
fuera de los commits. Respaldo de código: `codex/backup-europe-prints-20261122`;
copia previa del feed: `.test-tmp/europe-before/macro-feed-v7.json`.

## Opciones europeas: aplicado

- Se reutilizan las cadenas oficiales Eurex y los gráficos Plotly existentes.
- OI, volumen y Max Pain conservan su metodología. Las familias ODAX/ODAP y
  OESX/OEXP permanecen separadas, también en la curva de IV por vencimiento.
- Nuevo modelo diario para índices europeos con ejercicio europeo: IV invertida
  de precios oficiales de liquidación, gamma, GEX por strike y búsqueda de raíces
  de Gamma Flip. Las griegas del proveedor siguen teniendo cobertura cero:
  Eurex no las suministra en esta respuesta.
- Descuento y forward se ajustan por paridad call/put del mismo vencimiento;
  no se introduce un tipo del 4%, una IV genérica ni la volatilidad de un ETF.
- Controles: al menos siete pares y amplitud de strikes suficiente, límites
  de coherencia, residuos de paridad, precios identificables y cobertura de al
  menos el 90% del OI reportado. Si fallan, no se publica un nivel inventado.
- Multiplicadores: DAX 5, EURO STOXX 50 10 y STOXX 600 50 EUR por punto,
  verificados en las especificaciones de producto. GEX expresa EUR por un
  movimiento del 1% del subyacente. No se usa el multiplicador 100 de un ETF.
- Convención de tiempo: ACT/365 entre fechas de liquidación y vencimiento,
  sin valoración intradía. Los vencimientos con menos de dos días desde la
  observación y los contratos de estilo no validado quedan fuera del modelo.
- Cada perfil conserva fecha observada, precio de cierre utilizado, cobertura,
  error del ajuste, supuestos, raíces y sensibilidad. La selección sigue siendo
  una expiración por tramo temporal, no la suma de todas las opciones del mercado.

### Validación con las respuestas del 20/11

| Mercado | Perfiles seleccionados | Modelo disponible | Limitación |
| --- | ---: | ---: | --- |
| DAX: ODAX + ODAP | 6 | 6 | Escenario diario, OI fijo |
| EURO STOXX 50: OESX + OEXP | 6 | 6 | Escenario diario, OI fijo |
| STOXX Europe 600: OXXP | 3 | 2 | Liquidaciones insuficientes en el tercer perfil |
| EXSA | 2 | 0 | Modelo de ejercicio/valoración no validado |

La descarga se realizó el 22/11; las observaciones de opciones son del 20/11.
No se presentan como datos del 22/11 ni como una actualización intradía.
Como control reproducible, la muestra OESX del 30/11 contiene 71 pares aptos
para ajustar carry, con residuo RMS de 0,0376 puntos y cobertura de OI del 100%.
Esto verifica consistencia interna; no es una validación independiente de una
posición de dealers ni una prueba de capacidad predictiva del nivel.

El signo calls positivo / puts negativo es una hipótesis del escenario. Cambiar
la distribución de posiciones o la IV cambia los resultados. La ausencia de raíz
en ±30% del precio es distinta de la ausencia de datos y no se representa con cero.

## Economías: aplicado

Conector Eurostat gratuito y sin clave, con seis consultas pequeñas por ejecución
y caché de 24 horas. Se integra en el actualizador V7 y en la consulta manual macro.

- Eurozona EA21 (incluye la composición desde 2026) y Alemania DE.
- HICP general y subyacente: tabla vigente ECOICOP 2 `prc_hicp_minr`.
  No se usa la antigua clasificación congelada como si fuera una serie actual.
- PIB trimestral real, ajustado estacionalmente y por calendario.
- Desempleo armonizado Eurostat, total y ajustado: no se confunde con el registro
  nacional de desempleo alemán.
- Cada fila muestra unidad, fuente oficial, periodo de referencia y las tres
  últimas observaciones, incluidas las marcas del proveedor.
- Se distinguen actualización del conjunto, descarga y publicación de la
  observación. Eurostat no proporciona aquí la hora de publicación de cada valor:
  ese campo queda vacío. No se renueva una publicación antigua al descargarla.
- Consenso y sorpresa quedan ausentes. Estas series no se usan para fabricar
  sorpresas en el motor de sesgo. Un fallo conserva el dato y su periodo con
  estado de último dato retenido.
- La tabla señala las filas heredadas que todavía no tienen fuente por fila.

## Prints y dark pools: aplicado

- Un registro solo fechado se ancla visualmente a su vela diaria; no se le
  atribuye medianoche UTC como hora de ejecución.
- Al cambiar a 1h/4h, las filas sin hora/zona verificable siguen en la tabla
  pero no se superponen como operaciones intradía.
- Cobertura visible por activo y rango: filas reportadas, fecha más reciente,
  precisión suficiente para el gráfico y distinción de datos del proveedor.
- Se elimina la afirmación de que todas las filas tienen hora y fuente
  independientemente verificadas. InfoLib conserva su condición de proveedor.
- Los campos nulos de volumen off-exchange muestran ausencia, no un 0% artificial.
- Se añaden referencias a fuentes europeas candidatas, sin presentarlas como
  conectores ya operativos ni como prints dark pool confirmados.

### Fuentes gratuitas comprobadas

1. **Deutsche Börse/Xetra**: índice de archivos y descarga gzip/JSON accesibles.
   Una muestra de un minuto del 20/11 a las 16:30 UTC devolvió 390 registros,
   con ISIN, precio, moneda, cantidad, hora UTC y venue. Sus venues son XETA,
   XETB y XETS. Son publicaciones de operaciones de bolsa: no se reclasifican
   como dark pool. La muestra no contenía EXSA; no se traslada al gráfico de otro
   activo. No se ha integrado una recogida automática ni se publica el archivo bruto.
2. **Cboe Europe APA**: catálogo público accesible, descarga de muestra denegada
   con HTTP 403. El servicio actual tiene un formato distinto del catálogo legado;
   no se ha conseguido una descarga válida ni se afirma que esté operativo.
3. **Nasdaq APA y Euronext**: documentación oficial de archivos retrasados;
   candidatos a un adaptador futuro. Sin descarga validada en esta fase.
4. **FINRA**: se mantiene separado como agregado semanal ATS/OTC. La consulta
   anónima de particiones probada no entregó datos. Esto no demuestra que el
   servicio oficial con credenciales gratuitas no sea viable.

Antes de conectar operaciones europeas: resolver correcciones/cancelaciones,
identidad de transacción, mapeo ISIN/ticker/moneda y condiciones de uso y distribución.
Una publicación APA o una operación fuera de bolsa no demuestra ejecución en
dark pool, agresor BUY/SELL ni identidad institucional.

## Recomendación de próximos pasos

1. Revisar las hipótesis y comparar el nuevo modelo diario con otra cadena o
   herramienta independiente antes de tratar niveles como referencia operativa.
2. Completar las series oficiales por economía: inflación, empleo/salarios y
   actividad. Luego consenso documentado y expectativas implícitas de tipos;
   estos son los huecos principales del motor semanal.
3. Completar curvas GBP/NZD y verificar los vencimientos suizos que siguen antiguos.
4. Probar un adaptador APA que respete correcciones y derechos, manteniendo
   operaciones en bolsa, off-exchange y dark pools como categorías distintas.
5. Mantener COT en segundo plano. Evitar añadir más porcentajes de confianza o
   proxies equivalentes que aparenten información adicional sin mejorar cobertura.

## Pruebas y consumo

- 63 pruebas Python correctas; comprobaciones de sintaxis, renderizado, contratos
  de gráficos y precisión de operaciones correctas.
- Modelo: precio europeo conocido, recuperación de carry/IV, multiplicadores,
  revaloración numérica, fallos de paridad, OI sin precio, versiones duplicadas,
  estilo no admitido y ausencia de raíz. Sin llamadas de red en las pruebas unitarias.
- Consulta real de seis productos Eurex y ocho series macro en copia aislada;
  comprobación de cobertura y estados por perfil.
- Chrome con el feed real: OESX, columnas GEX, unidades EUR, curva sin mezclar
  familias, Eurostat sin consenso y conservación de filas con fecha en modo intradía.
- Regresión Chrome: 11 apartados globales, nueve economías, 15 combinaciones
  tema/modo y móvil; validación de estructura y contratos de gráficos.
- El feed pasó de 12.053.148 a 12.104.923 bytes en esta comparación local (+0,43%).
  No se han medido FPS/GPU ni coste cloud. No se acelera la consulta a cada minuto.

## Referencias oficiales

- [Eurex OESX: estilo, valoración y multiplicador](https://www.eurexgroup.com/ex-en/markets/idx/stx/euro-stoxx-50-derivatives/products/EURO-STOXX-50-Index-Options-46548)
- [Eurex DAX](https://www.eurex.com/ex-en/markets/idx/dax/DAX-Options-70044)
- [Eurex OXXP](https://www.eurex.com/ex-en/markets/idx/stx/stoxx-europe-600/products/STOXX-Europe-600-Index-Options-947818)
- [Eurostat: API oficial y actualizaciones](https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-introduction)
- [Eurostat: cambios HICP 2026](https://ec.europa.eu/eurostat/cache/metadata/en/prc_hicp_esms.htm)
- [Deutsche Börse: datos retrasados](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/Delayed-data)
- [Cboe: transparencia retrasada](https://www.cboe.com/markets/eu/equities/transparency-data/)
