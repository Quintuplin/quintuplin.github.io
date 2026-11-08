'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { buildPages } = require('./build-pages.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), '753-catalog-test-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const dir = path.join(root, 'simulations', '753');
  fs.mkdirSync(path.join(dir, 'domains'), { recursive: true });
  const read = file => fs.readFileSync(path.join(dir, file), 'utf8');
  const domain = (file, specs) => fs.writeFileSync(path.join(dir, 'domains', file),
    `(() => { for (const spec of ${JSON.stringify(specs)}) globalThis.Sims.register(spec); })();`);
  return { root, dir, read, domain };
}

const entry = (id, topic, title = id) => ({ id, topic, title, description: 'Compare <x> & "y".' });

test('directory groups and escapes registered metadata and links an actual page for every spec', t => {
  const { root, read, domain } = fixture(t);
  domain('b.js', [entry('second', 'Graphs'), entry('third', 'Matrices', 'Alpha & Beta')]);
  domain('a.js', [entry('first', 'Graphs')]);
  assert.equal(buildPages(root), 3);
  const catalog = read('index.html');
  assert.equal(catalog.match(/>Graphs<\/h2>/g).length, 1);
  assert.ok(catalog.indexOf('first/index.html') < catalog.indexOf('second/index.html'));
  assert.ok(catalog.includes('Alpha &amp; Beta'));
  assert.ok(catalog.includes('Compare &lt;x&gt; &amp; &quot;y&quot;.'));
  for (const [id, file] of [['first', 'a.js'], ['second', 'b.js'], ['third', 'b.js']]) {
    assert.ok(catalog.includes('href="' + id + '/index.html"'));
    const page = read(id + '/index.html');
    assert.ok(page.includes('<main id="sim" data-source="../domains/' + file + '">'));
    assert.ok(page.includes('href="../index.html"'));
    assert.ok(page.includes('href="../shared/player.css"'));
    assert.deepEqual([...page.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]), [
      '../shared/renderer.js', '../shared/player.js', '../domains/' + file,
    ]);
    assert.ok(page.indexOf('Sims.boot("' + id + '")') > page.indexOf('src="../domains/'));
  }
  buildPages(root);
  assert.equal(read('index.html'), catalog);
});

test('site navigation and catalog theme satisfy the standalone page checks', t => {
  const { root, read, domain } = fixture(t);
  domain('hash.js', [entry('hash', 'Hashes')]);
  buildPages(root);
  const page = read('index.html');
  for (const token of ['class="site-bar"', 'href="/"', 'href="/about"', 'href="/cv"', 'href="/projects"',
    'class="backdrop"', 'url("/assets/bg.jpg")', 'backdrop-filter', 'prefers-color-scheme: dark']) {
    assert.ok(page.includes(token), token);
  }
  assert.ok(page.indexOf('LinkedIn') < page.indexOf('GitHub'));
});

test('invalid metadata or route collisions fail before any page is written', t => {
  const { root, dir, domain } = fixture(t);
  domain('valid.js', [entry('valid', 'Graphs')]);
  for (const spec of [entry('valid', 'Other'), entry('../escape', 'Other'), entry('shared', 'Other'), entry('blank', '')]) {
    domain('other.js', [spec]);
    assert.throws(() => buildPages(root), /duplicate route|missing catalog metadata/);
    assert.ok(!fs.existsSync(path.join(dir, 'index.html')));
    assert.ok(!fs.existsSync(path.join(dir, 'valid')));
  }
});
