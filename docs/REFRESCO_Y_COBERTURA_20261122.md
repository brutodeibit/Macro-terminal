# Actualización desde el monitor y cobertura pendiente

## Implementado en la copia de trabajo

- El botón «Actualizar fuentes» abre un panel dentro del monitor; no abre GitHub.
- Tres consultas independientes: opciones, Dark Pools/prints y macro/tipos.
- Servicio local `scripts/source_refresh_server.py`, puerto 8766, iniciado con
  `Iniciar actualización de fuentes.cmd`. Conserva la página utilizable durante
  la consulta. Una consulta simultánea y 15 minutos de espera por grupo.
- Se reutiliza `update_preview.py`: no se crea un motor financiero paralelo.
  Se trabaja sobre una copia temporal y se publica localmente de forma atómica.
  Un fallo completo conserva el feed anterior. Los errores de una fuente no
  equivalen a dato nuevo; se muestra su estado individual.
- El botón «Cargar última publicación» conserva su función independiente.
- La consulta manual no crea commits, no publica Pages y no necesita token GitHub.
- No se modifica la cadencia automática existente: lectura visible cada 30
  minutos; ejecución del feed cada dos horas, con cachés por fuente.

## Errores corregidos

1. El feed V7 no programaba los recolectores existentes FINRA/agregados ni
   SquawkFlow. Se incorporan con sus estados y retrasos, sin cambiar sus fórmulas.
2. La selección de semanas FINRA tenía una expresión regular con escapes dobles.
3. InfoLib insertaba filas sin sincronizar recuentos, nocional ni estado del activo.
   Ahora muestra filas visibles y fecha observada, separadas del total del proveedor.
4. Las griegas completadas por un modelo podían contabilizarse como aportadas por
   Cboe. La cobertura del proveedor se captura antes de completar valores.
5. El respaldo SPX confundía fecha observada con vencimiento. Ahora la cobertura
   de vencimientos queda desconocida y se advierte si el modelo tiene más de
   cuatro días o carece de fecha. No se renueva su observación al descargarlo.
6. El resumen de opiniones del BoJ publicado el 9/11 se clasificaba como una
   reunión nueva. Se conserva como documento de apoyo; la decisión más reciente
   recuperada vuelve al 30/10. BoE conserva su publicación combinada de decisión
   y actas.
7. Se desactiva la extracción automática de la tabla pública de cadenas Cboe:
   su página la prohíbe expresamente. El parser se conserva para archivos
   autorizados/pruebas; las estadísticas agregadas Cboe son otro recurso.

## Comprobación real del 22/11

El feed de partida está generado el 22/11 a las 02:17 UTC. La consulta real de
InfoLib se ejecutó a las 10:17 UTC sobre una copia de prueba, sin publicar datos.
El proveedor devolvió 1.863 filas: 46 corresponden a los activos del monitor
(AAPL 26, NVDA 16, QQQ 2, SLV 2). Fechas más recientes: AAPL 19/11, NVDA 20/11,
QQQ 26/8, SLV 18/9. No hay filas nuevas verificadas para SPY, GLD, USO o BNO en
esa respuesta. La descarga reciente no convierte esas operaciones en recientes.

InfoLib no documenta en esas filas zona horaria, venue ni comprador/vendedor.
Se muestran por fecha y como información del proveedor; no como tape consolidado
independientemente verificado. FINRA ATS/OTC son agregados semanales: no ofrecen
ejecuciones individuales para superponer en velas intradía.

## Opciones: qué sigue faltando

| Activo/capa | Cobertura del feed inspeccionado | Pendiente |
| --- | --- | --- |
| SPY, GLD, USO, BNO | Precio de referencia, sin perfiles de cadena | OI, IV y griegas fechadas por contrato/vencimiento |
| SPX | Modelo SquawkFlow del 30/10, no cadena completa | Actualización verificable, cobertura y metodología del proveedor |
| Eurex | OI/volumen y vencimientos; sin IV/griegas verificadas | Precios/IV necesarios antes de calcular GEX y Gamma Flip |
| BTC/ETH Deribit | Perfiles de opciones e IV; Gamma Flip ausente | Modelo específico de contratos, validado; no trasladar el de acciones sin revisión |

Un Gamma Flip ausente puede significar datos insuficientes o que no existe una
raíz dentro del rango calculado. Son estados distintos. No se rellena con cero,
con el cruce acumulado de barras por strike ni con IV de otro instrumento.

Fuentes candidatas: Eurex oficial para OI/volumen; Deribit público para su mercado;
Yahoo como alternativa de disponibilidad irregular, sin garantía de servicio;
Massive solo con acceso y derechos de datos adecuados. Las cotizaciones retrasadas
de futuros CME no constituyen por sí solas una cadena de opciones con griegas.
La viabilidad contractual y la cobertura deben verificarse antes de añadir otra API.

## Macro por economía: siguiente prioridad recomendada

- Fuera de EE. UU. solo hay 2–3 indicadores por economía en el feed inspeccionado;
  algunas fichas mantienen valores con fechas abreviadas y sin fuente por fila.
  El resumen actualizado de la página no demuestra frescura de esos indicadores.
- Completar primero inflación/subyacente, empleo/salarios y actividad por economía,
  con periodo de referencia, fecha ISO de publicación, revisión, unidad y URL.
- Añadir consenso únicamente cuando la fuente lo aporte. Separar consenso,
  expectativas monetarias implícitas y confirmación del precio.
- GBP/NZD siguen sin curva completa; CHF presenta observaciones del 30/10 en
  algunos vencimientos. No sustituirlos por tipos de bancos centrales o depósitos.
- Revisión de expectativas de tipos y motor semanal comparable entre divisas
  siguen siendo parciales. No presentar confianza como probabilidad calibrada.
- COT conserva prioridad secundaria.

## Bloqueo de la web pública

Pages sirve archivos estáticos. Para consultar proveedores desde cualquier
dispositivo se necesita un servicio alojado, con control de acceso/coste y sin
secretos en el navegador. No se ha creado ni reutilizado el proyecto de Trading
Journal para este fin. La elección entre servicio gratuito separado y servicio
local está pendiente de respuesta. El servicio local funciona con el ordenador
encendido; sus resultados no actualizan la publicación compartida en Pages.

Estimación orientativa: copiar el feed cada 30 minutos pesa solo cuando se
descarga; consultar todas las cadenas cada minuto multiplicaría las peticiones
sin mejorar el OI diario. No se ha medido un coste cloud ni se garantiza coste
cero. No se han medido FPS ni consumo GPU porque este cambio no rediseña gráficos.
La consulta local real de Dark Pools (cuatro recolectores) tardó 36,5 segundos
en esta ejecución; no es una garantía de latencia de otras consultas/proveedores.

## Referencias

- [FINRA OTC Transparency](https://www.finra.org/filing-reporting/otc-transparency)
- [Cboe: tabla y restricción de extracción automática](https://www.cboe.com/data/quotes/spx/options)
- [CME: cotizaciones retrasadas](https://www.cmegroup.com/market-data/browse-data/delayed-quotes.html)
- [InfoLib: respuesta pública consultada](https://infolib.org/market-dashboard/get-darkpools-raw)

## Pruebas

- 50 pruebas Python: correctas, incluidas conservación atómica, errores, consulta
  única, espera mínima, rechazo de orígenes ajenos y BoJ/documentos de apoyo.
- Pruebas existentes de renderizado y contratos de gráficos: correctas.
- Chrome: botón, progreso, una sola petición, carga del resultado, servicio
  desconectado y tamaño móvil: correctos con API simulada.
- Chrome: regresión con el feed real, 11 apartados globales, nueve economías,
  15 combinaciones de tema/modo, gráficos y navegación móvil: correcta.
- Consulta real InfoLib: correcta en copia aislada. No se ha ejecutado una
  actualización completa de todas las fuentes ni verificado un servicio cloud.
- Servicio local: consulta real del grupo Dark Pools terminada el 22/11 a las
  10:21 UTC; cuatro recolectores procesados y publicación local atómica. Esto
  comprueba el recorrido real de la API; no certifica que todas las fuentes
  hayan entregado observaciones nuevas. El feed local resultante se conserva
  para inspección, sin incluirlo en los commits ni publicarlo en Pages.
