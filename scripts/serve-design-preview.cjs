'use strict';

// Local comparison only. Serve the dashboard assets and their existing feeds.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname,'..');
const files = new Set([
  'design-preview-v2.html','design-preview-v2.css','design-preview-v2.js',
  'design-lab-v2.html','design-lab-v2.css','design-lab-v2.js','index.html',
  'claude-preview.html','v7-ui.js','macro-feed-v7.json','macro-feed.json','data/cot-feed.json',
  'statistical-monitor.html','stats-feed.json'
]);
const mime = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.json':'application/json'};
const port = Number(process.argv[2] || 8765);
http.createServer((req,res) => {
  if (req.headers.host !== '127.0.0.1:'+port && req.headers.host !== 'localhost:'+port) {
    res.writeHead(403).end(); return;
  }
  if (!['GET','HEAD'].includes(req.method)) { res.writeHead(405).end(); return; }
  const name = new URL(req.url,'http://127.0.0.1').pathname.slice(1) || 'design-preview-v2.html';
  if (!files.has(name)) { res.writeHead(404).end(); return; }
  const file = path.join(root,name);
  fs.stat(file,(error,stat) => {
    if (error || !stat.isFile()) { res.writeHead(404).end(); return; }
    const etag = '"'+stat.size.toString(16)+'-'+Math.trunc(stat.mtimeMs).toString(16)+'"';
    const headers = {'Content-Type':mime[path.extname(file)]+'; charset=utf-8',
      'Cache-Control':'no-cache','Last-Modified':stat.mtime.toUTCString(),ETag:etag,
      'X-Content-Type-Options':'nosniff'};
    if (req.headers['if-none-match']===etag) { res.writeHead(304,headers).end(); return; }
    res.writeHead(200,{...headers,'Content-Length':stat.size});
    if (req.method==='HEAD') res.end();
    else fs.createReadStream(file).on('error',()=>res.destroy()).pipe(res);
  });
}).listen(port,'127.0.0.1',() => console.log('Macro Monitor V2 · http://127.0.0.1:'+port+'/design-preview-v2.html'));
