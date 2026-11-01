# Macro Monitor: auditoría integral, 1 noviembre 2026

## Alcance y estado

Trabajo incremental, no entrega integral terminada. Rama `repair/integral-audit-2026-11-01`; respaldo `backup/pre-integral-audit-2026-11-01`. Base actualizada a `15ca89b`. No desplegar esta rama sin revisión y autorización. Las capturas JAM/ProTrader no están adjuntas en esta sesión.

## Arquitectura conservada

- Repositorio: brutodeibit/Macro-terminal; publicación GitHub Pages.
- index.html: aplicación monolítica JavaScript, estilos y renderizadores; gráficos Plotly cargados bajo demanda.
- macro-feed.json: snapshot compartido por los módulos, cargado por HTTP con fallback raw GitHub; respaldo inicial embebido en HTML.
- update_feed.py: BLS, FRED, Treasury, Trading Economics opcional, Yahoo y calendario de decisiones.
- market_features.py: FX, opciones, COT, mercados, sentimiento, bonos, ETF y actividad OTC.
- scripts/cot.py: recolector independiente CFTC. update_stats.py/statistical-monitor.html: módulo estadístico existente, conservado.
- requests y BeautifulSoup; automatización GitHub Actions. No se añade servicio de pago.
- Los antiguos scripts maintenance contienen grandes plantillas que sobrescriben el código en cada ejecución. Se conservan como herramientas históricas, pero se retiran del refresco programado.

## Evidencia y reparaciones iniciales

| Hallazgo reproducible | Cambio en rama | Validación / límite |
|---|---|---|
| parseRate interpreta el separador del rango Fed como signo negativo | Parser explícito para rangos y tipos negativos | 3.75–4.00 → 3.875; -0.25 → -0.25 |
| fxRiskRegime usa umbrales -1/+1 sobre score 0–100: casi todo resulta risk-on | Usa 35/65, iguales al productor | Casos null, 35, 50, 65 |
| Null de Risk-On se convierte a cero | Comprueba ausencia antes de conversión | Ejecución del renderizador; falta QA visual |
| NFP toma nivel de empleo, no cambio mensual | Resta meses consecutivos, unidades miles | Fixture con 159100−159000=100K |
| AHE YoY presenta dólares como porcentaje | Variación frente al mismo mes del año anterior | 39/37.5−1=4% |
| PCE anual presenta índice como inflación | Variación interanual de índice | 103/100−1=3% |
| Consenso anterior se conserva al cambiar período BLS/FRED | Limpia estimación y sorpresa al cambiar período | No incorpora consensos nuevos |
| Formato K decide escala según magnitud | Escala explícita: claims se dividen por 1000; BLS ya está en miles | Falta refresco real acotado |
| YTD de Risk-On usa primer cierre de enero | Usa último cierre observable del año anterior | Sin base anterior, devuelve ausencia |
| Gamma Flip deriva de acumulación por strike | Separa cumulativeStrikeCrossing, deja Gamma Flip ausente | Test de cruce acumulado; falta recalcular snapshots existentes |
| Plot de prints inventa hora a partir del índice de una vela | Exige timestamp con zona, precio real y realPrint | Falta QA del gráfico; no demuestra autenticidad del proveedor |
| Una reunión se duplica si cambia su título | Identidad por fecha, conserva sourceUrl actual | No constituye conector automático |
| Mensajes técnicos saturan mapa | Retira bloque Estado de carga y detalle de pricing del mapa | Falta QA responsive |
| Workflow regenera código desde plantillas antiguas | Retira migraciones del refresco de datos | Pendiente ejecución en GitHub tras autorización |

Las pruebas usan fixtures deliberados y el snapshot existente para ejecutar ocho renderizadores. No constituyen verificación económica de todas las cifras del snapshot. La consulta de Actions obtuvo una ejecución de feed y una de Pages con resultado success; eso tampoco demuestra corrección de datos ni funcionamiento visual.

## Plan ordenado y pendientes

1. **Datos / automatización (P0):** registrar por fuente observedAt, publishedAt, fetchedAt, último éxito, error y caducidad. Separar errores de descarga y de renderizado. Validar respuestas antes de sobrescribir el snapshot. Evitar renovación aparente de timestamps cuando falla una fuente. El fallback actual puede mostrar datos embebidos antiguos. Añadir prueba HTTP y del navegador sobre copia candidata.
2. **Macro / bancos / Forex (P0):** no existe proveedor efectivo de probabilidades; los porcentajes iniciales no tenían procedencia. El calendario actual es una lista finita de noviembre/diciembre de 2026; no es un servicio de calendario ni separa correctamente horarios de conferencias. BoJ tiene hora supuesta. Desarrollar adaptadores oficiales por banco, documentos distintos por tipo, histórico de tres reuniones por fecha, caché condicional y reintentos acotados. No afirmar que esta parte está automatizada hoy.
3. **Sesgo (P0):** documentar pesos existentes antes de cambiarlos; añadir cobertura/caducidad, comparaciones con anterior y horizonte. Separar política monetaria de dirección FX. El régimen reparado no basta para validar primas refugio; eliminar aportaciones fijas de CHF/JPY y medir confirmación por precio de divisa. Consensos deben coincidir en serie, unidad y período, con procedencia; TEForecast no equivale automáticamente a encuesta de analistas.
4. **Opciones / prints (P0):** auditar multiplicador por instrumento, OI fechado, expiración real y liquidación AM/PM, griegas observadas/modeladas y cobertura ponderada por OI. Probar root de gamma frente a spot sólo con modelo completo; no usar cruce acumulado. Revisar todos los fallbacks y snapshots vencidos. Los niveles guardados aún requieren migración. En prints, verificar cada proveedor, campos, correcciones/cancelaciones y redistribución; una concentración de volumen no es ejecución individual. Revisar también la tabla y el renderizador heredado, no sólo el overlay.
5. **Índices / COT / cripto (P1):** auditar cierres y sesión por mercado, YTD también en amplitud, puntos y porcentajes; COT semanal con fecha de posición/publicación y selección de categoría; histórico ocultable. F&G 0–100 y BTC con ejes separados explícitos. Flujos ETF netos diarios/semanales por fecha, sin inferirlos de AUM.
6. **Entrega (P1):** pruebas reales de fuentes, fórmulas y escenarios de fallo; QA desktop/móvil con plots; comparar comportamiento antes/después. No publicar mientras quede un P0 de la entrega acordada sin resolver.

## Fuentes y límites de investigación

Se identificaron en código Yahoo, BLS, FRED/BEA, Treasury, TE opcional, CFTC, FINRA, Cboe, Deribit, Farside, ChartExchange y CapitolWhale. Estar en código no implica acceso garantizado ni permiso de redistribución.

- BLS salarios: https://www.bls.gov/news.release/realer.t01.htm (distingue niveles y variaciones).
- FRED PCE: https://fred.stlouisfed.org/series/PCEPILFE (serie de índice; aplicar transformación interanual).
- CFTC: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm (datos semanales, categorías no intercambiables).
- FINRA: https://www.finra.org/finra-data/browse-catalog/otc-transparency (agregados OTC no sustituyen prints individuales).
- Pendiente investigación de condiciones vigentes y disponibilidad de ZeroGEX, GEXMetrix, FirmTape, InfoLib y capturas JAM. No se ha confirmado una alternativa gratuita de prints completos a 15 minutos.

## Cobertura mínima propuesta

Eurozona: HICP núcleo/servicios, salarios negociados, PMI compuesto y encuesta de préstamos. Reino Unido: CPI servicios, salarios regulares, desempleo, PIB mensual. Japón: CPI Tokio/nacional, salarios y Tankan. CHF: CPI y actividad doméstica; refugio se verifica por FX. Canadá: CPI trim/median, empleo, PIB mensual. Australia: trimmed mean, empleo y salarios. NZ: inflación, empleo y expectativas RBNZ. Añadir sólo con fuente, unidad, período, revisión y calendario; mantener consenso ausente si no está disponible.

## Motor estadístico independiente: propuesta, sin implementación

Conservar el monitor estadístico separado. Datos diarios de cinco años como exploración, preferiblemente diez para regímenes; intradía requiere cobertura suficiente verificable por sesión y cambios DST. Definir giro como máximo/mínimo confirmado con umbral ATR y retraso explícito; impulso y retroceso como segmentos con reglas fijadas antes del test. Esos umbrales son parámetros a comparar, no verdades financieras. Separar desarrollo y validación cronológica walk-forward, costes y múltiples pruebas; informar N, mediana, percentiles, bootstrap por bloques y estabilidad por régimen. No usar extremos confirmados con datos futuros como señal contemporánea. Ficha compacta: instrumento, sesión, distribución de rango/retroceso/duración, incertidumbre, fechas de muestra. Sin automatizar operaciones.

## Contrato compartido futuro

Una sola evaluación versionada: economyId, currency, horizon, catalystAt, fundamentalBias, relativeUsdBias, marketConfirmation, confidence (calidad heurística, no probabilidad), previousEvaluationId, invalidations, methodologyVersion y evidenceIds. Cada evidencia: id, kind (observed/modelled/consensus), value nullable, unit, period, observedAt, publishedAt, fetchedAt, sourceUrl, provider, validUntil, status, revisionOf. Ningún consumidor convierte ausencia a cero. El supervisor y carteras consumen el mismo resultado y documentan discrepancias; no recalculan ni operan. No se modificó ningún proyecto de agentes.
