'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const escape = value => value.replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[c]);

function collect(dir) {
  const entries = [];
  const ids = new Set(['domains', 'shared']);
  for (const file of fs.readdirSync(dir).filter(name => name.endsWith('.js')).sort()) {
    if (!/^[\w-]+\.js$/.test(file)) throw Error('Unsafe domain filename: ' + file);
    const register = ({ id, topic, title, description }) => {
      if (typeof id !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id) || ids.has(id)) {
        throw Error('Invalid or duplicate route: ' + id);
      }
      if (![topic, title, description].every(s => typeof s === 'string' && s.trim())) {
        throw Error(file + ': missing catalog metadata for ' + id);
      }
      ids.add(id);
      entries.push({ file, id, topic, title, description });
    };
    vm.runInNewContext(fs.readFileSync(path.join(dir, file), 'utf8'), { Sims: { register } }, { filename: file });
  }
  if (!entries.length) throw Error('No simulation specs in ' + dir);
  return entries.sort((a, b) => a.topic.localeCompare(b.topic, 'en') || a.title.localeCompare(b.title, 'en') || a.id.localeCompare(b.id, 'en'));
}

const siteBar = `<nav class="site-bar" aria-label="Site">
  <a href="/">Home</a>
  <a href="/about">About</a>
  <a href="/cv">Resume</a>
  <a href="/projects">Projects</a>
  <a class="external" href="https://www.linkedin.com/in/jack-fraser-3a137ba3/">LinkedIn</a>
  <a href="https://github.com/quintuplin">GitHub</a>
</nav>`;

function head(title, description, prefix) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(title)} · COMPSCI 753</title>
<meta name="description" content="${escape(description)}">
<link rel="stylesheet" href="${prefix}catalog.css">
<style>
.backdrop { background-image: url("/assets/bg.jpg"); }
.local .backdrop { background-image: url("${prefix}../../assets/bg.jpg"); }
.lab-sheet { backdrop-filter: blur(12px); }
@media (prefers-color-scheme: dark) { .backdrop { filter: brightness(.5); } }
</style>
<script>if (location.protocol === "file:") document.documentElement.classList.add("local");</script>`;
}

const siteLinks = `<script>
if (location.protocol === "file:") {
  for (const a of document.querySelectorAll('.site-bar a[href^="/"]')) {
    a.href = "https://quintuplin.github.io" + a.getAttribute("href");
  }
}
</script>`;

function wrapper(spec) {
  const source = '../domains/' + spec.file;
  return `${head(spec.title, spec.description, '../')}
<link rel="stylesheet" href="../shared/player.css">
</head>
<body class="lab-route">
<div class="backdrop" aria-hidden="true"></div>
<header class="lab-sheet lab-heading">
${siteBar}
<a class="catalog-link" href="../index.html">← Simulator directory</a>
<h1>${escape(spec.title)}</h1>
<p>${escape(spec.description)}</p>
</header>
<main id="sim" data-source="${source}"></main>
${siteLinks}
<script src="../shared/renderer.js"></script>
<script src="../shared/player.js"></script>
<script src="${source}"></script>
<script>Sims.boot("${spec.id}");</script>
</body>
</html>
`;
}

function catalog(entries) {
  const topics = new Map();
  for (const spec of entries) {
    if (!topics.has(spec.topic)) topics.set(spec.topic, []);
    topics.get(spec.topic).push(spec);
  }
  const groups = [...topics.entries()];
  const description = 'Explore algorithms step by step with small datasets, a 3D view and a working notebook.';
  return `${head('Algorithm simulator directory', description, '')}
</head>
<body>
<div class="backdrop" aria-hidden="true"></div>
<main class="lab-sheet directory">
${siteBar}
<header>
<p class="course">COMPSCI 753</p>
<h1>Algorithm simulator directory</h1>
<p>${description}</p>
</header>
<nav class="topics" aria-label="Jump to topic">
${groups.map(([topic], i) => `  <a href="#topic-${i + 1}">${escape(topic)}</a>`).join('\n')}
</nav>
${groups.map(([topic, specs], i) => `<section aria-labelledby="topic-${i + 1}">
<h2 id="topic-${i + 1}">${escape(topic)}</h2>
<ul class="lab-list">
${specs.map(s => `  <li><a href="${s.id}/index.html">${escape(s.title)}</a><p>${escape(s.description)}</p></li>`).join('\n')}
</ul>
</section>`).join('\n')}
</main>
${siteLinks}
</body>
</html>
`;
}

function buildPages(root) {
  const dir = path.join(root, 'simulations', '753');
  const entries = collect(path.join(dir, 'domains'));
  for (const spec of entries) {
    const route = path.join(dir, spec.id);
    fs.mkdirSync(route, { recursive: true });
    fs.writeFileSync(path.join(route, 'index.html'), wrapper(spec));
  }
  fs.writeFileSync(path.join(dir, 'index.html'), catalog(entries));
  return entries.length;
}

module.exports = { buildPages };
if (require.main === module) {
  const count = buildPages(path.resolve(__dirname, '../..'));
  console.log(`Generated the directory and ${count} simulator pages.`);
}
