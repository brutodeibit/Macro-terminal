# Estrategia Atlas v1.3.2

Continuación local de la v1.3 integrada. Abre `Estrategia_Atlas_v1_3_integrada.html` y conserva `atlas-core.js` en la misma carpeta. El motor y el adaptador requieren Python 3.10 o posterior y usan su biblioteca estándar. Conserva juntos `atlas_engine.py` y `journal_exchange.py`.

## P1 · Estudiar un histórico diario

```powershell
python atlas_engine.py --prices historico.csv --instrument SPX --market other --output estudio.json
```

Usa un CSV UTF-8 de un instrumento con `date,open,high,low,close,volume`. Fecha de sesión ISO `AAAA-MM-DD`. Volumen opcional. El símbolo o contrato, si están presentes, deben ser únicos y el símbolo debe coincidir con `--instrument`. Para acciones estadounidenses puedes declarar `--market us_equity` y aplicar comprobaciones parciales de fechas de evento.

En **Laboratorio → Motor OHLCV · cruce Journal**, carga el JSON en la primera casilla. El motor registra SHA-256 de los bytes efectivamente leídos, fechas, huecos de más de cuatro días y cobertura de volumen. El heatmap mensual en JSON incluye fechas ancla y excluye el último mes observado y pares con extremos anteriores al día 25. Sigue siendo provisional: faltan calendario completo, ajustes, rollovers y verificación de fuente. Las excursiones de eventos incluyen el punto de partida. Los estudios de eventos y patrones pueden solaparse y sus tamaños de muestra no equivalen a observaciones independientes.

Las vistas originales de heatmap, estacionalidad, histórico comparativo, EventLab y HMM se conservan. Las cifras precargadas pertenecen a referencias sin auditar. Las barridas, rangos y rupturas diarios son reglas aproximadas. El HMM sigue siendo exploratorio. Un CSV diario carece de granularidad para confirmar Wyckoff discrecional, footprint o Volume Profile.

## Estacionalidad con calendario de sesiones

```powershell
python atlas_engine.py --prices historico.csv --instrument SPX --market us_equity --session-calendar sesiones.json --seasonality-test-from 2024-01-01 --output estacionalidad.json
```

El calendario JSON contiene `source` (identificador o enlace de la fuente), `first` y `last` (límites de cobertura inclusivos), y `sessions` (fechas ISO ordenadas de las sesiones efectivas). Usa el calendario correspondiente al instrumento y el mismo corte horario que el CSV. El motor registra los hashes de ambos archivos y comprueba las fechas en cada ventana. La certificación de la fuente, los precios ajustados y los rollovers sigue a cargo del estudio. Repite el comando por índice o por materia prima y conserva sus resultados por separado.

El bloque `calendar_seasonality` del JSON contiene observaciones y resúmenes. Calcula semanas de lunes a domingo, meses naturales, días 1–7, días 1–15, días 16–fin de mes y ventanas móviles de 15 días naturales iniciadas en sesión. La base es el cierre anterior a cada ventana. MAE/MFE usan extremos OHLC, y el retroceso y recuperación usan cierres. Los desplazamientos se cuentan en sesiones desde la base. Las recuperaciones no observadas quedan vacías y su denominador está en `n`. Los deciles se interpolan con el método inclusivo. La frecuencia positiva se expresa como fracción.

El corte cronológico excluye ventanas que lo atraviesan. Los cortes de régimen se calculan con las 21 sesiones anteriores a la ventana, incluido el cierre ancla. Tendencia usa el retorno de 20 sesiones con umbrales ±2 % y volatilidad usa la desviación de 20 retornos logarítmicos anualizada con umbral de 20 %. Ambos umbrales son exploratorios. El ciclo de elecciones de medio término usa los años cuyo resto al dividir por cuatro es dos. Registra la hipótesis y el corte antes de examinar la prueba. Las ventanas móviles se solapan y las estadísticas describen la muestra. El bloque nuevo se consulta en el JSON del motor.

## P3 · Ejecutar el backtest diario

```powershell
python atlas_engine.py --prices historico.csv --instrument SPX --test-from 2024-01-01 --cost-bps 15 --output prueba.json
```

Corte y coste son ejemplos. Regístralos junto al protocolo antes de ver el tramo de prueba. Indica el coste total estimado ida y vuelta en puntos básicos, incluido spread y deslizamiento si corresponden. El motor usa una ruptura de máximos/mínimos de las 20 velas anteriores al cierre de señal, abre en la siguiente apertura y cierra al final de la quinta vela desde la entrada. Una posición a la vez. Descarta las ventanas con huecos superiores a cuatro días y exige que cada operación quede dentro de un tramo. El tramo de prueba puede utilizar los precios anteriores al corte para el contexto de la señal.

El informe muestra estadísticas por operación, operaciones con sus fechas y precios, y comparación con una entrada larga periódica de igual plazo y coste. La exposición y número de operaciones pueden diferir. La regla es fija y no se ajusta con los datos. Un corte cronológico ayuda a revisar el desempeño fuera de muestra si eliges el corte y las reglas antes de examinarlo. Quedan pendientes el walk-forward, costes por instrumento y tamaño, stops, y la simulación 1H/5M. Usa `--synthetic` para identificar series de prueba.

## P2 · Leer una copia del Trading Journal

```powershell
python atlas_engine.py --journal copia_journal.json --output intercambio.json
```

Carga `intercambio.json` en la segunda casilla. Se aceptan copias `version: 1` (Journal anterior) y `version: 2` (Journal con parciales y productos). El intercambio `atlas-journal-exchange-v2` conserva una clave `journal:<id>` por operación, IDs de estrategia y setup, producto, entradas o patas, salidas, cantidades, costes y horas disponibles. En CFD/futuros/spot, R usa el riesgo inicial por stop. En opciones, usa el riesgo máximo planificado declarado para la estrategia y conserva call/put, compra/venta, strike y vencimiento por pata. Rechaza IDs repetidos, parciales excesivos, salidas anteriores a la entrada y cálculos inválidos. El neto aplica cada coste una vez. Atlas resume operaciones cerradas por modo, estrategia, setup, divisa y cobertura de costes. Cargar otro archivo sustituye la vista, sin sumar instantáneas. Los IDs relacionan estrategias y setups. El vínculo por señal queda vacío porque las copias actuales del Journal no incluyen ese ID.

El formato `atlas-journal-exchange-v1` sigue disponible al convertir una copia del registro Atlas. Ese origen aparece identificado como Registro Atlas. Las copias de Trading Journal tienen su propio formato y siguen restaurándose en Journal. Los resultados son declarados y su conciliación con extractos de bróker queda pendiente.

### Comparaciones de decisiones

La segunda casilla del laboratorio también muestra la comparación de decisiones del intercambio nuevo. El JSON lleva el archivo fuente y su SHA-256, conteos de pendientes y descartadas y cohortes por setup y versión, oportunidad, alineación, sesión, hora, contexto, régimen con origen declarado, calidad y cumplimiento. Cada cohorte mantiene modo, producto, moneda y cobertura de costes. Solo entran ideas completamente cerradas. El drawdown acumula R por instante de cierre y queda vacío si la cohorte pierde precisión temporal. Las distribuciones de R están disponibles en JSON. Los archivos de intercambio antiguos siguen abriendo.

### Gestión alternativa con velas diarias

```powershell
python atlas_engine.py --prices historico.csv --instrument SPY --session-calendar sesiones.json --management-case caso.json --output gestion.json
```

Ejemplo de configuración con fechas y precios ilustrativos:

```json
{"start":"2024-01-02","end":"2024-01-05","direction":"long","stop":93,"target":115,"cost_bps":{"commissions":1,"spread":2,"slippage":2}}
```

La posición simulada se abre a la apertura de `start`. El stop debe estar en el lado correcto y el objetivo debe superar 1R. Cada vela de la ventana usa la sesión del calendario declarado. El motor compara stop original más objetivo, BE tras +1R, stop dinámico a 1R del cierre anterior y parcial del 50 % en +1R. Los ajustes se activan desde la siguiente vela. Si stop y nivel favorable se cruzan durante una misma vela sin secuencia observable, el escenario devuelve **ambiguo** y deja el resultado vacío. Un hueco más allá del stop usa la apertura. El neto queda vacío cuando se omite `cost_bps`. MAE/MFE describen la ventana completa, incluida su evolución tras la salida simulada. Carga `gestion.json` en la primera casilla del laboratorio. Para pruebas con fixtures añade `--synthetic`.

## Copias y pruebas

### Histórico de índices y duración de fases

En el mismo Laboratorio OHLCV, carga `historia_indices_20261119.json` en la primera casilla. Selecciona Nasdaq Composite, Nasdaq-100 o S&P 500 y la cobertura disponible o la muestra común desde 2017. La tabla muestra recuento mensual, porcentajes de meses positivos y negativos, media, mediana, percentiles 25–75 y las franjas que concentraron máximos y mínimos de cierre retrospectivos. El último mes completo es octubre de 2026.

`historia_indices.py` reproduce el informe con cierres diarios CSV de FRED y `exchange_calendars==4.13.2`. Descarga cada serie con fecha final hasta el 20 de noviembre de 2026. La copia de FRED termina el 19 de noviembre. Los archivos históricos de precios se descargan por separado de la entrega.

```powershell
python historia_indices.py --nasdaqcom NASDAQCOM.csv --nasdaq100 NASDAQ100.csv --sp500 SP500.csv --last-date 2026-11-20 --complete-through 2026-10 --output informe.json
```

La fuente XNYS se usa como referencia independiente de sesiones. Se omiten los meses con sesiones esperadas ausentes, cierres fuera del calendario o ancla de cierre anterior ausente. Cada mes compara su último cierre con el último cierre del mes anterior. Los máximos y mínimos eligen el primer día si hay empate en el precio. Las franjas tienen distinto número de sesiones y sus frecuencias no son probabilidades operativas de detectar un giro en directo.

Las patas se definen por un cambio de dirección confirmado tras un movimiento adverso de al menos 5 % desde el extremo de cierre. Se identifica la fecha del extremo y la fecha posterior en que pudo confirmarse. La duración mide sesiones y el retroceso divide el movimiento en puntos de la pata por los puntos de la pata anterior, por lo que puede superar 100 %. La pata en curso queda fuera de las medianas de patas completas. Un escenario de corto plazo exige datos de velas y una escala apropiada para esa temporalidad.

Para medir fases Wyckoff revisadas, añade `--phases fases.csv`. Columnas `instrument,timeframe,phase,start,end,bars,evidence`. Usa códigos `SP500`, `NASDAQ100` o `NASDAQCOM` para que se vea la cohorte en el selector. Temporalidades `W`, `D`, `4H`, `1H`. Etiquetas `accumulation` y `distribution`. Incluye timestamps ISO con zona horaria y la evidencia de la revisión. Las fases abiertas llevan final vacío y se cuentan aparte. El informe guarda media y mediana de velas, además de horas naturales transcurridas. La descarga de FRED solo contiene cierres diarios y el informe de entrega carece de fases revisadas.

[Nasdaq Composite en FRED](https://fred.stlouisfed.org/series/NASDAQCOM) · [Nasdaq-100 en FRED](https://fred.stlouisfed.org/series/NASDAQ100) · [S&P 500 en FRED](https://fred.stlouisfed.org/series/SP500)

Esta entrega conserva la v1.3 en una carpeta de trabajo propia. La copia del ZIP de entrada está en `backups/pre_v1_3_20261115/` del proyecto. Si venías usando otra ruta de Atlas, exporta allí los registros JSON antes de abrir este HTML e impórtalos en su Registro. Se admiten las hipótesis pendientes y se preservan los metadatos anteriores al editar. Los campos de investigación que no estaban en el formulario v1.3 siguen en el JSON, sin editor específico en esta entrega.

```powershell
python -B -m unittest discover -s tests -v
node tests/browser.cjs
```

El segundo comando requiere el Playwright ya instalado y Chrome. En otro equipo ajusta `ATLAS_NODE_MODULES`. Se incluye una prueba opcional anterior para Chromium en Linux. Los fixtures y la imagen del ZIP son sintéticos. Las prioridades siguientes son comprobar un histórico real de un instrumento con calendario y costes conocidos, conciliar una exportación del Journal con sus cifras originales, y ampliar las reglas solo después de validar el protocolo.
