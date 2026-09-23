# MacroTerminal V5

## Qué incluye
- Monitor macro global con tipos, reuniones, curva y datos.
- Historial de 3 reuniones y detalle ampliable de puntos clave.
- Motor de sesgo macro separado por inflación, empleo, crecimiento, banco central y mercado.
- **Econic personalizado integrado en el RESUMEN GLOBAL:** Risk-On/Risk-Off con SP500, Nasdaq, VIX, VVIX, SKEW, crédito HY (opcional FRED), DXY, AUD/JPY, oro, cobre, Brent/WTI, TLT/SPY y BTC/ETH.
- `macro-feed.json` separado del HTML.
- `update_feed.py` para actualizar automáticamente.
- GitHub Actions cada 15 minutos.

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
