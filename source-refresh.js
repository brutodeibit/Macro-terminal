/* Explicit source refresh, independent from loading the published snapshot. */
(() => {
  'use strict';
  let endpoint, busy = false, timer;
  const button = document.getElementById('sourceRefreshButton');
  if (!button) return;
  const dialog = document.createElement('dialog');
  dialog.setAttribute('aria-labelledby', 'sourceRefreshTitle');
  dialog.style.cssText = 'width:min(94vw,560px);max-height:85vh;overflow:auto;padding:24px;border:1px solid #334155;border-radius:18px;background:#0f172a;color:#e2e8f0;box-shadow:0 24px 90px #0008';
  dialog.innerHTML = `<form method="dialog"><button aria-label="Cerrar" style="float:right;font-size:22px">×</button></form>
    <h2 id="sourceRefreshTitle" style="font-size:20px;font-weight:700;margin-bottom:12px">Consultar las fuentes</h2>
    <p style="font-size:13px;line-height:1.6;margin-bottom:16px">La consulta se ejecuta en segundo plano. Los datos retrasados conservan su fecha; consultar de nuevo no elimina el retraso del proveedor.</p>
    <label for="sourceRefreshGroup">Qué quieres actualizar</label>
    <select id="sourceRefreshGroup" style="display:block;width:100%;margin:10px 0 16px;padding:10px;background:#1e293b;border:1px solid #475569;border-radius:8px">
      <option value="market">Panel global, divisas y sectores</option><option value="options">Opciones y niveles gamma</option><option value="dark">Dark Pools y prints</option><option value="macro">Economías, bancos centrales y tipos</option>
    </select>
    <button type="button" id="sourceRefreshStart" style="background:#2563eb;color:white;border-radius:8px;padding:10px 16px">Consultar ahora</button>
    <p id="sourceRefreshStatus" role="status" aria-live="polite" style="margin-top:16px;font-size:13px;line-height:1.6"></p>
    <ul id="sourceRefreshProgress" style="margin-top:10px;font-size:12px;line-height:1.8"></ul>`;
  document.body.append(dialog);
  const status = dialog.querySelector('#sourceRefreshStatus');
  const start = dialog.querySelector('#sourceRefreshStart');
  const group = dialog.querySelector('select');
  const list = dialog.querySelector('ul');
  const names = {market:'Panel global y sectores', options:'Opciones', dark:'Dark Pools y prints', macro:'Economías y tipos'};
  const states = {processed:'Consulta procesada; revisa la fecha y cobertura', unchanged_or_unavailable:'Sin cambios o sin datos nuevos', retained:'Error: último dato conservado'};
  async function request(url, options = {}) {
    const response = await fetch(url, {...options, cache:'no-store', signal:AbortSignal.timeout(8000)});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Servicio no disponible');
    return body;
  }
  async function connect() {
    const local = ['localhost','127.0.0.1'].includes(location.hostname);
    // A hosted service can provide this same API later; no credentials in the page.
    const urls = window.MACRO_REFRESH_ENDPOINT ? [window.MACRO_REFRESH_ENDPOINT] :
      local ? ['/api/refresh','http://127.0.0.1:8766/api/refresh'] : ['http://127.0.0.1:8766/api/refresh'];
    for (const url of urls) {
      try {
        const data = await request(url);
        if (data.service !== 'macro-source-refresh-v1') continue;
        endpoint = url;
        return data;
      } catch (_) { /* Try the local companion when the static server has no API. */ }
    }
    throw new Error('El servicio de actualización no está conectado. En tu ordenador abre “Iniciar actualización de fuentes.cmd” y mantén esa ventana abierta. La web pública por sí sola no puede ejecutar los recolectores.');
  }
  function render(job) {
    list.replaceChildren();
    for (const item of job.progress || []) {
      const row = document.createElement('li');
      row.textContent = `${item.source}: ${states[item.status] || 'Consultado'}`;
      list.append(row);
    }
    status.textContent = `${names[job.group] || 'Fuentes'} · ${job.state === 'running' ? 'Consultando… puedes seguir usando el monitor.' : 'Consulta terminada.'}`;
  }
  function lock(value) { busy = value; start.disabled = value; group.disabled = value; start.style.opacity = value ? '.55' : '1'; }
  async function poll() {
    try {
      const {job} = await request(endpoint);
      if (!job) throw new Error('No se encontró la consulta. Puedes volver a intentarlo.');
      render(job);
      if (job.state === 'running') { timer = setTimeout(poll,3000); return; }
      lock(false);
      if (job.state === 'failed') throw new Error(job.error || 'La consulta falló; se conserva la copia anterior.');
      // The local service serves its own refreshed snapshot. Never substitute a
      // different feed silently when a hosted endpoint is configured.
      const feedUrl = new URL('../macro-feed-v7.json', new URL(endpoint,location.href)).href;
      const loaded = await loadExternalFeed([feedUrl], true);
      status.textContent = loaded ? 'Consulta terminada y copia cargada. Cada fuente conserva su fecha y sus posibles limitaciones.' : 'Consulta terminada, pero no se pudo cargar la nueva copia. Se conserva la vista actual.';
    } catch (error) { lock(false); status.textContent = error.message; }
  }
  button.addEventListener('click', async () => {
    if (!dialog.open) dialog.showModal();
    if (busy) return;
    status.textContent = 'Comprobando el servicio…';
    try {
      const data = await connect();
      status.textContent = 'Servicio conectado. Una consulta simultánea; mínimo 15 minutos antes de repetir el mismo grupo.';
      if (data.job?.state === 'running') { lock(true); render(data.job); clearTimeout(timer); poll(); }
    } catch (error) { status.textContent = error.message; }
  });
  start.addEventListener('click', async () => {
    if (busy) return;
    lock(true); list.replaceChildren(); status.textContent = 'Iniciando consulta…';
    try {
      await connect();
      const job = await request(endpoint, {method:'POST',headers:{'Content-Type':'application/json','X-Macro-Refresh':'1'},body:JSON.stringify({group:group.value})});
      render(job); poll();
    } catch (error) { lock(false); status.textContent = error.message; }
  });
})();
