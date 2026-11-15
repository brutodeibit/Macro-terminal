# Plan de cierre incremental

Base: claude-preview.html y feed V7 publicados. Conservar index.html, gráficos funcionales y fuentes existentes. No cerrar tareas por mera implementación local.

1. Navegación europea (DAV-20): cuatro instrumentos juntos en selector y tarjetas: SX5E, FEZ, SXXP y EXSA. Eliminar pestañas superiores redundantes. Conservar ODAX y ODAP separados: distintas horas de vencimiento; no sumar cadenas. Verificar selección y renderizado, publicar y comprobar HTTP.
2. Rendimientos (DAV-21): resolver GBP/NZD con fuentes accesibles y fechadas. BoE y RBNZ responden 403 desde este entorno; no equivale a inexistencia del bono. Investigar descarga desde Actions y alternativas autorizadas. Registrar observación, fuente, unidad e histórico; conservar último valor sin renovar su fecha. Comprobar 2Y y 10Y, después restantes vencimientos reales. Celdas sin dato: guion.
3. Opciones (DAV-20): auditar OI, volumen e IV ATM por contrato. Eurex entrega OI/volumen; aún no IV/griegas verificadas. Investigar método con precios de liquidación y supuestos explícitos antes de calcular Gamma Flip. No reutilizar IV de ETF como IV del índice. Probar vencimientos, raíces múltiples y ausencia de raíz.
4. Prints (DAV-20): ampliar cobertura por activo con fuentes legales, distinguiendo ejecuciones, agregados y cancelaciones. Mostrar lado únicamente cuando esté documentado; rojo compra y verde venta según preferencia del usuario. Sin lado: neutral. Etiquetas breves, detalle en tooltip; no atribuir carteras. Revisar conectores, extensión horizontal y solapamientos visualmente.
5. Economías y sesgo semanal (DAV-23): mismo esquema para todas: contexto anterior, novedades, banco central/expectativas, reacción FX 1/3/5/21 sesiones, hipótesis actual, próximos eventos importantes y escenarios de confirmación/invalidación. Explicar cada parámetro favorable, contrario o ausente; separar lectura macro de confirmación de precio. No inferir consenso ni eventos faltantes.
6. Prioridad de eventos: inflación general/subyacente, PCE para Fed, empleo/salarios, actividad y decisiones/ruedas de prensa. Discursos y precios de importación/exportación en detalle secundario salvo relevancia contextual documentada. Sustituir título Catalizadores por Eventos clave. Recuperar ejemplos del mentor antes de afirmar fidelidad al estilo solicitado.
7. Organización de economías: síntesis semanal ampliable arriba, evidencias y escenarios, tono monetario conservado, tres reuniones únicas y curvas. Evitar duplicar resumen de tipos o dejar explicaciones vacías. Compartir estructura con narrativa sin modificar el proyecto de agentes.
8. Entrega: pruebas específicas, visual escritorio/móvil cuando sea posible, publicación autorizada y verificación pública. Actualizar tareas existentes de Linear sin duplicados ni cierres sin evidencia. COT queda conservado; nuevas ampliaciones requieren concretar utilidad.

Estado 14/11: navegación de cuatro instrumentos corregida localmente; pruebas de renderizado y gráficos ejecutadas. Resto pendiente de implementación/verificación según cada bloque, no cerrado.

## Ampliación 15/11: requisitos y dudas separados
- Rendimientos: GBP/NZD todos; AUD 1Y y vencimientos largos; CAD 20Y/30Y; JPY 3M. Verificar instrumentos, fechas y disponibilidad; no confundir letras soberanas con depósitos o bank bills ni LT con 30Y exactos.
- Tablas: título de rendimientos arriba y matriz relativa abajo; leyenda dentro de cada cuadro sobre los cinco factores, cobertura parcial, fechas y colores. Implementación local realizada.
- Indicadores: corregir ventas minoristas a consumo/actividad, no empleo. Catálogo prioritario específico por economía; estrellas como ayuda, no criterio único. Histórico desplegable de últimas tres observaciones con revisiones y periodo de referencia, sin duplicar gráficos.
- Explicación de sesgo: separar actividad/inflación/empleo, política monetaria, diferenciales externos y confirmación FX/riesgo. Evidencias a favor/en contra y ausentes; evitar narrativa genérica o primas refugio fijas.
- Opciones: GEX e IV ATM ausentes siguen pendientes; distinguir actualización diaria OI de cambios intradía del modelo. Prints: ampliar fuentes sin inferir lado ni instituciones.
- COT: evaluar posición neta/OI, cambio semanal y percentil histórico; evitar añadir muchas métricas equivalentes. Contexto swing, no señal de entrada intradía.
- Commodities: SOLO propuesta futura, sin programación. Ficha por activo con oferta/demanda, inventarios, producción, comercio, clima/geografía, curva de futuros y calendarios oficiales; definir estrategias y validar fuera de muestra en proyecto especializado.
- Diseño: conservar azul noche y preparar variante arena/grafito dorado con contraste y relieve; revisar carbón/turquesa. No alterar información por motivos estéticos.
- Refresco: explicar que cargar publicación descarga el snapshot, no ejecuta proveedores; mostrar fecha de cada fuente.

- Estrategias futuras: valorar commodities junto a swing de divisas en el proyecto especializado; pendiente decidir ubicación en Notion. No se ha modificado Notion.
- Actualización manual: workflow_dispatch permite force_refresh para consultar todos los recolectores, además del refresco de lectura del panel. No garantiza tiempo real ni acceso a fuentes bloqueadas.
