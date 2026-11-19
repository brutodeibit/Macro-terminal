# Macro Monitor oficial

El usuario autorizó el 19/11/2026 convertir la navegación V2, con todas las
economías y datos de Claude, en la interfaz oficial. La página canónica es
`index.html`, con `v7-ui.js` y la capa visual `design-preview-v2.js/.css`.

Enlace: https://brutodeibit.github.io/Macro-terminal/

Los módulos son Panel de mercado, Sentimiento, Posicionamiento, Opciones y
Dark Pools. Los retornos de bonos y crédito están dentro de Panel de mercado.
Los antiguos enlaces Claude y V2 redirigen a la portada. Para diagnóstico
local, `index.html?layout=classic` conserva el renderizado continuo.

El feed oficial de la interfaz es `macro-feed-v7.json`, generado por el
workflow existente `update-preview.yml`. La promoción visual mantiene sus
recolectores y cadencias. Respaldo remoto previo a esta promoción:
`backup/pre-official-v2-20261119`.
