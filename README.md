# Macro Monitor

Interfaz oficial: [Macro Monitor](https://brutodeibit.github.io/Macro-terminal/).
La portada `index.html` reúne la versión Claude V7 y la navegación V2.
Los módulos incluyen Panel de mercado (con bonos y crédito), Sentimiento,
Posicionamiento, Opciones y Dark Pools. Todas las economías siguen accesibles
desde la navegación lateral o el selector móvil.

La interfaz carga `macro-feed-v7.json` mediante el conector existente y su
workflow `update-preview.yml`. Cada serie conserva su fecha, fuente y estado.
Los cinco temas y los modos Esencial, Avanzado y Ultra cambian la presentación.
Los antiguos enlaces de revisión redirigen a la portada.

## Qué incluye
- Monitor macro global con tipos, reuniones, curva y datos.
- Historial de 3 reuniones y detalle ampliable de puntos clave.
- Motor de sesgo macro separado por inflación, empleo, crecimiento, banco central y mercado.
- **Econic personalizado integrado en el RESUMEN GLOBAL:** Risk-On/Risk-Off con SP500, Nasdaq, VIX, VVIX, SKEW, crédito HY (opcional FRED), DXY, AUD/JPY, oro, cobre, Brent/WTI, TLT/SPY y BTC/ETH.
- `macro-feed.json` separado del HTML.
- `update_feed.py` para actualizar automáticamente.
- GitHub Actions cada 15 minutos.

## Integridad de expectativas y bancos centrales

- El panel no muestra porcentajes de la próxima reunión si faltan `expectationsUpdated`, `expectationsSource` y `expectationsUrl`. No sustituye ese hueco por probabilidades antiguas ni por estimaciones.
- `update_feed.py` elimina cualquier snapshot de expectativas que no tenga esos tres campos y no lo incorpora al sesgo FX.
- El calendario de decisiones y ruedas de prensa se incorpora desde las páginas oficiales de los bancos centrales. Cada evento conserva un enlace a su fuente; el calendario se actualiza sin requerir una clave de Trading Economics.
- El historial de comunicados usa una lista de hasta tres entradas. Un futuro conector de comunicado sólo debe insertar documentos oficiales con fecha, URL y título; nunca debe borrar un comunicado anterior por un fallo de fuente.

## GitHub
Sube el contenido de esta carpeta a la raíz del repositorio que usas para GitHub Pages. El workflow se ejecuta cada 15 minutos y hace commit de `macro-feed.json`.

Para consensos/forecasts de Trading Economics, añade `TE_API_KEY` como GitHub Secret. Para HY Spread histórico desde FRED, añade `FRED_API_KEY`.

## Importante
El score Risk-On/Risk-Off es descriptivo y transparente; no constituye una señal automática de entrada. Se muestra también qué elementos confirman y cuáles generan tensión.


## Monitor Estadístico por Activo
- `statistical-monitor.html` separado del Monitor Macro para no cargar el HTML principal.
- `update_stats.py` calcula estadísticas descriptivas con hasta 5 años diarios cuando Yahoo Finance entrega la serie.
- Incluye pullbacks en tendencia, impulsos, días explosivos, drawdown y estacionalidad por día del mes.
- Incluye una primera capa de ventanas de liquidez intradía en hora de Nueva York. La muestra intradía pública se etiqueta como parcial y **no se presenta todavía como el backtest de 1–3 años**.
- `stats-feed.json` conserva el último snapshot válido.
