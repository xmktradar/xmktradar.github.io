// Tiny static server for the repo root. check.js, layout_check.js and stock_pages.js
// load the slim homepages over http://127.0.0.1 so fetch('/data/dash/...') works.
const http = require('http');
const fs = require('fs');
const path = require('path');

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.gif': 'image/gif', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.xml': 'application/xml', '.txt': 'text/plain; charset=utf-8',
};

function start(root) {
  root = path.resolve(root);
  const server = http.createServer((req, res) => {
    let u = decodeURIComponent((req.url || '/').split('?')[0]);
    if (u.endsWith('/')) u += 'index.html';
    const rel = path.normalize(u).replace(/^(\.\.[/\\])+/, '');
    const file = path.join(root, rel);
    if (file !== root && !file.startsWith(root + path.sep)) {
      res.writeHead(403); res.end('forbidden'); return;
    }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); res.end('not found'); return; }
      const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
      res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'no-store' });
      res.end(data);
    });
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      resolve({ server, port, origin: 'http://127.0.0.1:' + port, root });
    });
  });
}

// Homepage URL. index.html -> /, zh/index.html -> /zh/
function pageUrl(origin, root, file) {
  let rel = path.relative(root, path.resolve(file)).split(path.sep).join('/');
  if (rel === 'index.html') rel = '';
  else if (rel.endsWith('/index.html')) rel = rel.slice(0, -'index.html'.length);
  return origin + '/' + rel;
}

module.exports = { start, pageUrl };
