# Continuación solicitada 14-11-2026

Seguimiento existente, sin duplicar: DAV-21 (actualización, calendario, curvas y matriz), DAV-20 (opciones DAX/STOXX y prints), DAV-23 (síntesis semanal).

- Verificar actualización programada end-to-end; distinguir consultar publicación de ejecutar proveedores. Revisar MACRO/ECONOMIC_CALENDAR sin cambios frente a fallos de fuente.
- Rendimientos en tabla global y fichas desde las mismas series; resolver Reino Unido/Nueva Zelanda y vencimientos restantes. Mantener fechas y excluir datos caducados del cálculo operativo.
- Matriz: explicar cinco factores, cobertura y contribuciones sin inventar confianza.
- DAX: índice y opciones ODAX; EWG no replica DAX. STOXX: SX5E/FEZ y SXXP/EXSA, con cuatro selecciones y cobertura real de cadenas; no dar por resuelto por añadir tickers.
- Síntesis semanal breve y ampliable: semana anterior, próximos eventos/consenso, banco central, hipótesis, confirmación e invalidación. Recuperar ejemplos del mentor; no declarar una integración NMM no comprobada.
- Perfil estructural compacto por economía: exportaciones, importaciones y sensibilidad energética; separado de hipótesis semanal y respaldado por fuentes.
- Dark pools menos prioritario: encontrar prints verificables; separar agregados FINRA y no inferir compras/ventas sin evidencia.
- Recomendación de estructura: síntesis semanal arriba, perfil estructural desplegable, eventos y evidencias, banco central y curvas debajo. Evitar duplicar motores y gráficos.

## Aclaración de lectura solicitada
- Separar sesgo fundamental, tendencia 1/3/5/21 sesiones y reacción al catalizador. Un dato favorable puede coincidir con rebote o continuación bajista; no inferir retests ni cambios de tendencia solo de retornos.
- Resumen con contexto suficiente, no solo etiqueta; perfil estructural incluye potencial refugio condicionado, no prima fija para CHF/JPY.
- Investigación DAX: ODAX y ODAP en Eurex; evaluar datos públicos retrasados por strike y vencimiento. GammaCockpit publica una vista ODAX del día previo: validar acceso, metodología y redistribución antes de conectar.
- Prints: FINRA transparencia semanal es agregado. Ejecuciones TRF individuales pertenecen a la cinta consolidada: verificar proveedor con precio, cantidad, timestamp y condiciones, sin asignar BUY/SELL ni cartera por inferencia.

## Bloque Eurex e InfoLib implementado el 14-11
- Cadenas oficiales por strike de ODAX, OESX y OXXP recuperadas desde estadísticas públicas de Eurex: OI, volumen, paredes OI y Max Pain. Selección del primer vencimiento disponible en cada ventana; no representa todos los vencimientos de la ventana.
- No hay IV/griegas en esta fuente: no calcular GEX ni Gamma Flip con ceros. Pendientes clases EOD ODAP/OEXP y cadena efectiva del ETF EXSA.
- InfoLib: filas de precio/tamaño/importe contrastadas aritméticamente; observadas para QQQ, SLV, AAPL y NVDA en la consulta. Proveedor secundario, no cinta de mercado verificada independientemente. Sin identificación de institución o lado. Sin zona horaria publicada: marcas solo por fecha en gráfico diario.
- Actualización Eurex cada 2 horas e InfoLib cada 12 horas dentro del workflow existente; los refrescos de otros proveedores conservan estos datos si su consulta está en caché.
- Pruebas de normalización, Max Pain y conservación entre proveedores aprobadas; validación estructural del feed y pruebas JavaScript del panel/gráficos aprobadas. Publicación se verifica por separado.
