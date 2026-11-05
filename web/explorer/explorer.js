/*! Research explorer, v1. Original code with no third-party dependencies.
 *  Integration notes: README.md in this folder. */
(function (root, factory) {
  'use strict';
  var scriptSrc = typeof document !== 'undefined' && document.currentScript ? document.currentScript.src : '';
  var api = factory(root, scriptSrc);
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }
  root.ExplorerCore = api;
  if (typeof document !== 'undefined' && !root.EXPLORER_NO_BOOT) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { api.boot(); }, { once: true });
    else api.boot();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root, scriptSrc) {
  'use strict';

  const VERSION = '1.0.0';
  const WORLD_W = 1200;
  const WORLD_H = 800;
  const MODES = ['graph', 'treemap', 'city'];
  const LEGACY_ROUTES = {
    sectors: { view: 'graph', mode: 'treemap' },
    treemap: { view: 'graph', mode: 'treemap' },
    city: { view: 'graph', mode: 'city' }
  };
  const PAL = 10; // 8 colours, "other", spare
  const PALETTE = {
    light: ['#A8C0EC', '#B2D3BA', '#E6CF9F', '#E5B5BC', '#C5B7E4', '#A6D4CE', '#D2D4A2', '#D8BDA2', '#D2D0CA', '#D2D0CA'],
    dark: ['#47628F', '#4C7658', '#857043', '#87575F', '#665A8B', '#477A74', '#767847', '#7A6149', '#4A4946', '#4A4946']
  };
  // Node display states, drawn in this order so emphasis sits on top.
  const S_NORMAL = 0, S_DIM = 1, S_NEIGHBOR = 2, S_SELECTED = 3, S_HIDDEN = 4, S_MATCH = 5;
  const DRAW_ORDER = [S_HIDDEN, S_DIM, S_NORMAL, S_MATCH, S_NEIGHBOR, S_SELECTED];
  const EV = ['observed', 'inferred', 'unstated'];
  const EV_LABEL = { observed: 'Observed', inferred: 'Inferred', unstated: 'Evidence not stated' };
  const CITY_MAX_H = 140;
  const CITY_FLAT_H = 1.2;
  const EDGE_DRAW_BUDGET = 60000;
  const HOT_EDGE_LIMIT = 4000;

  const now = () => (root.performance && root.performance.now ? root.performance.now() : Date.now());
  const NF = new Intl.NumberFormat('en-US');
  const fmt = (n) => NF.format(n);
  const plural = (n, one, many) => fmt(n) + ' ' + (n === 1 ? one : (many || one + 's'));
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

  // ---------------------------------------------------------------- text and URLs

  function text(v, max) {
    let s;
    if (typeof v === 'string') s = v;
    else if (typeof v === 'number' && isFinite(v)) s = String(v);
    else if (typeof v === 'boolean') s = String(v);
    else return '';
    s = s.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '').trim();
    if (max && s.length > max) s = s.slice(0, max - 1) + '\u2026';
    return s;
  }

  function fold(s) {
    return s ? s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase() : '';
  }

  function preparedLabel(value) {
    const raw = text(value, 60);
    if (!raw) return 'Preparation date not listed';
    const date = new Date(raw);
    return Number.isFinite(date.getTime())
      ? 'Prepared ' + new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(date)
      : 'Preparation date not listed';
  }

  function overlapWarnings(datasets, selectedIds) {
    const selected = new Set(selectedIds);
    const warnings = new Set();
    for (const dataset of datasets) {
      if (!selected.has(dataset.id) || !Array.isArray(dataset.overlapsWith)) continue;
      const overlaps = datasets.filter((other) => other.id !== dataset.id && selected.has(other.id) && dataset.overlapsWith.includes(other.id));
      if (!overlaps.length) continue;
      warnings.add(text(dataset.overlapWarning, 2000) || text(dataset.label, 200) + ' shares records with ' + overlaps.map((other) => text(other.label, 200)).join(', ') + '. Combined counts include repeated records.');
    }
    return [...warnings];
  }

  const ABSOLUTE = /^[a-z][a-z0-9+.-]*:/i;

  /** True only when the page itself was opened from disk (a local, private copy). */
  function pageIsFile() {
    return !!(root.location && root.location.protocol === 'file:');
  }

  /** Returns a normalised URL, or null. http and https are always allowed.
   *  file: is allowed only when the page itself is a file: page, so a public
   *  http(s) page never links to local paths. Every other scheme (javascript:,
   *  data:, blob: and so on) is rejected. Relative URLs are allowed only when
   *  allowRelative is set (dataset and detail files); they resolve against base. */
  function safeUrl(value, base, allowRelative) {
    if (typeof value !== 'string') return null;
    const s = value.trim();
    if (!s || s.length > 4096 || /[\u0000-\u001F\u007F]/.test(s)) return null;
    const absolute = ABSOLUTE.test(s);
    if (!absolute && !allowRelative) return null;
    let u;
    try {
      u = absolute ? new URL(s) : new URL(s, base || (root.location && root.location.href) || 'https://example.invalid/');
    } catch (e) { return null; }
    if (u.protocol === 'https:' || u.protocol === 'http:') return u.href;
    if (u.protocol === 'file:' && pageIsFile()) return u.href;
    return null;
  }

  function hostOf(url) {
    try {
      const u = new URL(url);
      if (u.protocol === 'file:') {
        let name = u.pathname.split('/').filter(Boolean).pop() || '';
        try { name = decodeURIComponent(name); } catch (e) { /* keep encoded name */ }
        return name ? 'local file ' + name : 'local file';
      }
      return u.hostname.replace(/^www\./, '') || 'source';
    } catch (e) { return 'source'; }
  }

  // ---------------------------------------------------------------- data model

  /** entries: [{ meta: {id,label}, data: datasetJson, baseUrl }] in display order.
   *  Edges resolve only inside their own dataset, so no edge can join two datasets. */
  function buildModel(entries) {
    const t0 = now();
    const nodes = [];
    const edges = [];
    const byUid = new Map();
    const datasets = [];
    const kindCount = new Map();
    const typeCount = new Map();
    const evidenceCounts = { observed: 0, inferred: 0, unstated: 0 };

    for (let d = 0; d < entries.length; d++) {
      const entry = entries[d];
      const meta = entry.meta || {};
      const data = entry.data;
      const dsId = text(meta.id) || text(data && data.id) || 'dataset-' + d;
      const info = {
        id: dsId, index: d, label: text(meta.label, 200) || text(data && data.label, 200) || dsId,
        nodeStart: nodes.length, nodeEnd: nodes.length, edgeCount: 0,
        invalidNodes: 0, duplicateNodes: 0, invalidEdges: 0, unresolvedEdges: 0,
        selfLoops: 0, duplicateEdges: 0, rejectedUrls: 0,
        missingNodes: !(data && Array.isArray(data.nodes)),
        missingEdges: !(data && Array.isArray(data.edges)),
        idMismatch: data && data.id != null && text(data.id) !== dsId ? text(data.id, 200) : null
      };
      const local = new Map();
      const rawNodes = data && Array.isArray(data.nodes) ? data.nodes : [];
      for (let r = 0; r < rawNodes.length; r++) {
        const raw = rawNodes[r];
        if (!raw || typeof raw !== 'object') { info.invalidNodes++; continue; }
        const id = text(raw.id, 500);
        if (!id) { info.invalidNodes++; continue; }
        if (local.has(id)) { info.duplicateNodes++; continue; }
        const i = nodes.length;
        const kind = text(raw.kind, 120);
        const sourceUrl = safeUrl(raw.sourceUrl);
        const detailUrl = safeUrl(raw.detailUrl, entry.baseUrl, true);
        if ((raw.sourceUrl && !sourceUrl) || (raw.detailUrl && !detailUrl)) info.rejectedUrls++;
        const metrics = raw.metrics && typeof raw.metrics === 'object' && !Array.isArray(raw.metrics) ? raw.metrics : null;
        const node = {
          i, uid: dsId + '::' + id, ds: dsId, d, id,
          label: text(raw.label, 300) || id,
          kind, group: text(raw.group, 200), subgroup: text(raw.subgroup, 200),
          description: text(raw.description, 8000), sourceUrl,
          sourceRejected: !!(raw.sourceUrl && !sourceUrl),
          date: text(raw.date, 60), status: text(raw.status, 120), author: text(raw.author, 300),
          metrics, detailUrl
        };
        local.set(id, i);
        nodes.push(node);
        byUid.set(node.uid, node);
        kindCount.set(kind, (kindCount.get(kind) || 0) + 1);
      }
      info.nodeEnd = nodes.length;

      const rawEdges = data && Array.isArray(data.edges) ? data.edges : [];
      const seen = new Set();
      for (let r = 0; r < rawEdges.length; r++) {
        const raw = rawEdges[r];
        if (!raw || typeof raw !== 'object') { info.invalidEdges++; continue; }
        const sId = text(raw.source, 500), tId = text(raw.target, 500);
        if (!sId || !tId) { info.invalidEdges++; continue; }
        const s = local.get(sId), t = local.get(tId);
        if (s === undefined || t === undefined) { info.unresolvedEdges++; continue; }
        if (s === t) { info.selfLoops++; continue; }
        const type = text(raw.type, 120) || 'Type not recorded';
        const evidence = raw.evidence === 'observed' || raw.evidence === 'inferred' ? raw.evidence : 'unstated';
        const directed = raw.directed === true;
        const key = (directed || s < t ? s + '>' + t : t + '>' + s) + '|' + type + '|' + evidence;
        if (seen.has(key)) { info.duplicateEdges++; continue; }
        seen.add(key);
        const sourceUrl = safeUrl(raw.sourceUrl);
        if (raw.sourceUrl && !sourceUrl) info.rejectedUrls++;
        edges.push({ i: edges.length, s, t, type, basis: text(raw.basis, 4000), sourceUrl, evidence, directed, d });
        typeCount.set(type, (typeCount.get(type) || 0) + 1);
        evidenceCounts[evidence]++;
        info.edgeCount++;
      }
      datasets.push(info);
    }

    const n = nodes.length, m = edges.length;
    const degree = new Int32Array(n);
    for (let e = 0; e < m; e++) { degree[edges[e].s]++; degree[edges[e].t]++; }
    const adjStart = new Int32Array(n + 1);
    for (let i = 0; i < n; i++) adjStart[i + 1] = adjStart[i] + degree[i];
    const cursor = adjStart.slice(0, n);
    const adj = new Int32Array(2 * m);
    for (let e = 0; e < m; e++) { adj[cursor[edges[e].s]++] = e; adj[cursor[edges[e].t]++] = e; }
    let maxDegree = 0;
    for (let i = 0; i < n; i++) if (degree[i] > maxDegree) maxDegree = degree[i];
    let crossDataset = 0;
    for (let e = 0; e < m; e++) if (nodes[edges[e].s].d !== nodes[edges[e].t].d) crossDataset++;
    const byEvidence = EV.map((ev) => {
      const list = [];
      for (let e = 0; e < m; e++) if (edges[e].evidence === ev) list.push(e);
      return Int32Array.from(list);
    });
    const sortCounts = (map) => [...map].map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
    const kinds = sortCounts(kindCount);
    const kindIndex = new Map(kinds.map((k, idx) => [k.name, idx]));
    return {
      datasets, nodes, edges, byUid, degree, adjStart, adj, maxDegree, crossDataset, byEvidence,
      kinds, kindIndex, edgeTypes: sortCounts(typeCount), evidenceCounts, buildMs: now() - t0
    };
  }

  // ---------------------------------------------------------------- layout

  /** Squarified treemap (Bruls, Huizing and van Wijk). values must be sorted
   *  in descending order. Returns [x, y, w, h] per value in input order. */
  function squarify(values, x, y, w, h) {
    const n = values.length;
    const out = new Float64Array(n * 4);
    if (!n || !(w > 0) || !(h > 0)) {
      for (let i = 0; i < n; i++) { out[i * 4] = x; out[i * 4 + 1] = y; }
      return out;
    }
    let total = 0;
    for (let i = 0; i < n; i++) total += values[i];
    if (!(total > 0)) return out;
    const scale = (w * h) / total;
    let i = 0;
    while (i < n) {
      const side = Math.min(w, h);
      const s2 = side * side;
      let sum = values[i] * scale, maxA = sum, minA = sum;
      let worst = Math.max((s2 * maxA) / (sum * sum), (sum * sum) / (s2 * minA));
      let j = i + 1;
      while (j < n) {
        const a = values[j] * scale;
        const ns = sum + a, nmax = a > maxA ? a : maxA, nmin = a < minA ? a : minA;
        const nw = Math.max((s2 * nmax) / (ns * ns), (ns * ns) / (s2 * nmin));
        if (nw > worst) break;
        sum = ns; maxA = nmax; minA = nmin; worst = nw; j++;
      }
      const last = j >= n;
      if (w >= h) {
        const rw = last ? w : sum / h;
        let cy = y;
        for (let k = i; k < j; k++) {
          const rh = k === j - 1 ? y + h - cy : (values[k] * scale) / rw;
          out[k * 4] = x; out[k * 4 + 1] = cy; out[k * 4 + 2] = rw; out[k * 4 + 3] = rh;
          cy += rh;
        }
        x += rw; w -= rw;
      } else {
        const rh = last ? h : sum / w;
        let cx = x;
        for (let k = i; k < j; k++) {
          const rw = k === j - 1 ? x + w - cx : (values[k] * scale) / rh;
          out[k * 4] = cx; out[k * 4 + 1] = y; out[k * 4 + 2] = rw; out[k * 4 + 3] = rh;
          cx += rw;
        }
        y += rh; h -= rh;
      }
      i = j;
    }
    return out;
  }

  function byCount(a, b) {
    return b.count - a.count || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0) || a.first - b.first;
  }

  /** One shared hierarchy: dataset > group > subgroup > record. Every record has
   *  equal area. The graph, treemap and city all read these rectangles. */
  function computeLayout(model, opts) {
    const t0 = now();
    const W = (opts && opts.width) || WORLD_W;
    const H = (opts && opts.height) || WORLD_H;
    const nodes = model.nodes, n = nodes.length;
    const rects = new Float32Array(n * 4);
    const nodeFrame = new Int32Array(n).fill(-1);
    const order = new Int32Array(n);
    const frames = [];
    let op = 0;

    function addFrame(level, label, d, x, y, w, h, count, parent, labelled) {
      const m = Math.min(w, h);
      const pad = labelled ? (level === 0 ? Math.min(4, m * 0.02) : level === 1 ? Math.min(2, m * 0.02) : Math.min(1, m * 0.02)) : 0;
      let head = 0;
      if (labelled) head = level === 0 ? Math.min(20, m * 0.1) : level === 1 ? Math.min(13, m * 0.1) : Math.min(8, m * 0.1);
      if (h - head - 2 * pad < h * 0.55) head = 0;
      const f = {
        i: frames.length, level, label, d, x, y, w, h, head, count, parent,
        ix: x + pad, iy: y + pad + head, iw: Math.max(0, w - 2 * pad), ih: Math.max(0, h - 2 * pad - head)
      };
      frames.push(f);
      return f;
    }
    function placeLeaves(list, f) {
      const r = squarify(new Float64Array(list.length).fill(1), f.ix, f.iy, f.iw, f.ih);
      for (let k = 0; k < list.length; k++) {
        const i = list[k], o = i * 4, q = k * 4;
        rects[o] = r[q]; rects[o + 1] = r[q + 1]; rects[o + 2] = r[q + 2]; rects[o + 3] = r[q + 3];
        nodeFrame[i] = f.i;
        order[op++] = i;
      }
    }
    function layoutChildren(items, parent, level, d, fallbackLabel, inner) {
      const r = squarify(Float64Array.from(items.map((it) => it.count)), parent.ix, parent.iy, parent.iw, parent.ih);
      items.forEach((it, k) => {
        const f = addFrame(level, it.label || fallbackLabel, d, r[k * 4], r[k * 4 + 1], r[k * 4 + 2], r[k * 4 + 3], it.count, parent.i, true);
        inner(it, f);
      });
    }
    function layoutSubgroups(g, parent, d) {
      const subs = [...g.subs.values()].sort(byCount);
      if (subs.length === 1 && !subs[0].label) { placeLeaves(subs[0].nodes, parent); return; }
      layoutChildren(subs, parent, 2, d, 'No subgroup recorded', (s, f) => placeLeaves(s.nodes, f));
    }

    const items = [];
    for (const ds of model.datasets) {
      if (ds.nodeEnd <= ds.nodeStart) continue;
      const groups = new Map();
      for (let i = ds.nodeStart; i < ds.nodeEnd; i++) {
        const nd = nodes[i];
        let g = groups.get(nd.group);
        if (!g) groups.set(nd.group, (g = { label: nd.group, subs: new Map(), count: 0, first: i }));
        g.count++;
        let s = g.subs.get(nd.subgroup);
        if (!s) g.subs.set(nd.subgroup, (s = { label: nd.subgroup, nodes: [], count: 0, first: i }));
        s.nodes.push(i); s.count++;
      }
      items.push({ ds, label: ds.label, count: ds.nodeEnd - ds.nodeStart, first: ds.index, groups: [...groups.values()].sort(byCount) });
    }
    items.sort(byCount);
    const multi = items.length > 1;
    const dsRects = multi ? squarify(Float64Array.from(items.map((it) => it.count)), 0, 0, W, H) : [0, 0, W, H];
    items.forEach((it, k) => {
      const f = addFrame(0, it.ds.label, it.ds.index, dsRects[k * 4], dsRects[k * 4 + 1], dsRects[k * 4 + 2], dsRects[k * 4 + 3], it.count, -1, multi);
      if (it.groups.length === 1 && !it.groups[0].label) layoutSubgroups(it.groups[0], f, it.ds.index);
      else layoutChildren(it.groups, f, 1, it.ds.index, 'No group recorded', (g, gf) => layoutSubgroups(g, gf, it.ds.index));
    });

    const grid = buildGrid(rects, n, W, H);
    let hsh = 0x811c9dc5;
    const mix = (v) => { hsh ^= v & 0xffff; hsh = Math.imul(hsh, 0x01000193) >>> 0; hsh ^= v >>> 16; hsh = Math.imul(hsh, 0x01000193) >>> 0; };
    for (let i = 0; i < n; i++) {
      const u = nodes[i].uid;
      for (let c = 0; c < u.length; c++) mix(u.charCodeAt(c));
      for (let q = 0; q < 4; q++) mix(Math.round(rects[i * 4 + q] * 1000) >>> 0);
    }
    return { W, H, rects, frames, nodeFrame, order, grid, hash: hsh.toString(16).padStart(8, '0'), ms: now() - t0 };
  }

  /** Uniform grid over record rectangles for constant-time hit tests. */
  function buildGrid(rects, n, W, H) {
    const cols = 160, cell = W / cols, rows = Math.ceil(H / cell);
    const counts = new Int32Array(cols * rows + 1);
    const span = (i, fn) => {
      const o = i * 4;
      const c0 = clamp(Math.floor(rects[o] / cell), 0, cols - 1);
      const c1 = clamp(Math.floor((rects[o] + rects[o + 2]) / cell), 0, cols - 1);
      const r0 = clamp(Math.floor(rects[o + 1] / cell), 0, rows - 1);
      const r1 = clamp(Math.floor((rects[o + 1] + rects[o + 3]) / cell), 0, rows - 1);
      for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) fn(r * cols + c);
    };
    for (let i = 0; i < n; i++) span(i, (g) => { counts[g + 1]++; });
    for (let g = 0; g < cols * rows; g++) counts[g + 1] += counts[g];
    const fill = counts.slice(0, cols * rows);
    const items = new Int32Array(counts[cols * rows]);
    for (let i = 0; i < n; i++) span(i, (g) => { items[fill[g]++] = i; });
    return { cols, rows, cell, start: counts, items };
  }

  function hitTest(layout, wx, wy) {
    if (!layout || wx < 0 || wy < 0 || wx > layout.W || wy > layout.H) return -1;
    const g = layout.grid, R = layout.rects;
    const c = Math.min(g.cols - 1, Math.floor(wx / g.cell)), r = Math.min(g.rows - 1, Math.floor(wy / g.cell));
    const cellIndex = r * g.cols + c;
    for (let p = g.start[cellIndex]; p < g.start[cellIndex + 1]; p++) {
      const i = g.items[p], o = i * 4;
      if (wx >= R[o] && wx <= R[o] + R[o + 2] && wy >= R[o + 1] && wy <= R[o + 1] + R[o + 3]) return i;
    }
    return -1;
  }

  /** Nearest record from `from` in direction (dx, dy), restricted by allow(j). */
  function nearestInDirection(rects, n, from, dx, dy, allow) {
    const o = from * 4;
    const cx = rects[o] + rects[o + 2] / 2, cy = rects[o + 1] + rects[o + 3] / 2;
    let best = -1, bestScore = Infinity;
    for (let j = 0; j < n; j++) {
      if (j === from || (allow && !allow(j))) continue;
      const q = j * 4;
      const vx = rects[q] + rects[q + 2] / 2 - cx, vy = rects[q + 1] + rects[q + 3] / 2 - cy;
      const along = vx * dx + vy * dy;
      if (along <= 1e-6) continue;
      const perp = Math.abs(vx * dy - vy * dx);
      if (perp > along * 2.5) continue;
      const score = along + perp * 2.5;
      if (score < bestScore) { bestScore = score; best = j; }
    }
    return best;
  }

  // ---------------------------------------------------------------- search

  const FIELDS = ['label', 'id', 'author', 'topic', 'dataset', 'desc', 'refs'];
  const FIELD_SCORE = { label: 35, id: 28, author: 24, topic: 18, dataset: 12, desc: 9, refs: 6 };
  const FIELD_NAME = { label: 'name', id: 'record ID', author: 'author', topic: 'topic', dataset: 'dataset', desc: 'description', refs: 'references' };
  const FIELD_ALIAS = {
    name: 'label', title: 'label', label: 'label', id: 'id', author: 'author', by: 'author',
    topic: 'topic', kind: 'topic', group: 'topic', status: 'topic', ref: 'refs', refs: 'refs',
    source: 'refs', reference: 'refs', references: 'refs', dataset: 'dataset', text: 'desc', description: 'desc'
  };

  function createSearchIndex(model) {
    const t0 = now();
    const n = model.nodes.length;
    const f = {};
    for (const k of FIELDS) f[k] = new Array(n);
    const refs = new Array(n).fill('');
    for (const e of model.edges) {
      const bit = ' ' + e.type + ' ' + e.basis + ' ' + (e.sourceUrl || '');
      if (refs[e.s].length < 3000) refs[e.s] += bit;
      if (refs[e.t].length < 3000) refs[e.t] += bit;
    }
    for (let i = 0; i < n; i++) {
      const nd = model.nodes[i];
      const ds = model.datasets[nd.d];
      f.label[i] = fold(nd.label);
      f.id[i] = fold(nd.id);
      f.author[i] = fold(nd.author);
      f.topic[i] = fold(nd.kind + ' \u2022 ' + nd.group + ' \u2022 ' + nd.subgroup + ' \u2022 ' + nd.status);
      f.dataset[i] = fold(ds.label + ' ' + ds.id);
      f.desc[i] = fold(nd.description);
      f.refs[i] = fold((nd.sourceUrl || '') + refs[i]);
    }
    return { n, f, ms: now() - t0 };
  }

  function parseQuery(q) {
    const tokens = [];
    const re = /([a-z]+):"([^"]*)"|([a-z]+):(\S+)|"([^"]*)"|(\S+)/gi;
    let m;
    while ((m = re.exec(q || ''))) {
      let field = null, value;
      if (m[1] !== undefined || m[3] !== undefined) {
        const alias = FIELD_ALIAS[(m[1] || m[3]).toLowerCase()];
        value = m[2] !== undefined ? m[2] : m[4];
        if (alias) field = alias;
        else value = m[0];
      } else value = m[5] !== undefined ? m[5] : m[6];
      value = fold(value.trim());
      if (value) tokens.push({ field, value });
    }
    return tokens;
  }

  function wordStart(s, idx) {
    if (idx <= 0) return true;
    const c = s.charCodeAt(idx - 1);
    return !((c >= 48 && c <= 57) || (c >= 97 && c <= 122));
  }

  function runSearch(index, q) {
    const t0 = now();
    const tokens = parseQuery(q);
    if (!tokens.length) return null;
    const n = index.n, f = index.f;
    const scores = new Float32Array(n);
    const fieldOf = new Uint8Array(n);
    const mask = new Uint8Array(n);
    const hits = [];
    for (let i = 0; i < n; i++) {
      let total = 0, firstField = -1;
      let ok = true;
      for (let t = 0; t < tokens.length; t++) {
        const tok = tokens[t], v = tok.value;
        let best = 0, bestField = -1;
        for (let fi = 0; fi < FIELDS.length; fi++) {
          const name = FIELDS[fi];
          if (tok.field && tok.field !== name) continue;
          const s = f[name][i];
          if (!s) continue;
          const idx = s.indexOf(v);
          if (idx < 0) continue;
          let sc = FIELD_SCORE[name];
          if (name === 'label') {
            if (s === v) sc = 100;
            else if (idx === 0) sc = 70;
            else if (wordStart(s, idx)) sc = 50;
          } else if (wordStart(s, idx)) sc += 3;
          if (sc > best) { best = sc; bestField = fi; }
        }
        if (!best) { ok = false; break; }
        total += best;
        if (firstField < 0) firstField = bestField;
      }
      if (!ok) continue;
      scores[i] = total; fieldOf[i] = firstField; mask[i] = 1;
      hits.push(i);
    }
    hits.sort((a, b) => scores[b] - scores[a] || a - b);
    return { tokens, indices: Int32Array.from(hits), mask, fieldOf, scores, count: hits.length, ms: now() - t0 };
  }

  function matchedFieldName(result, i) {
    return FIELD_NAME[FIELDS[result.fieldOf[i]]] || 'name';
  }

  // ---------------------------------------------------------------- lazy evidence

  /** Picks one record's evidence from a fetched detail file. Sharded files are
   *  {schemaVersion:1, datasetId, records:{[localId]: evidence}}; only the entry
   *  for localId is returned, never its neighbours. Any other JSON value is
   *  treated as an unsharded file holding one record's evidence. */
  function evidenceFor(data, localId) {
    if (data && typeof data === 'object' && !Array.isArray(data) && data.records && typeof data.records === 'object' && !Array.isArray(data.records)) {
      const found = Object.prototype.hasOwnProperty.call(data.records, localId);
      return { sharded: true, found, value: found ? data.records[localId] : undefined, datasetId: text(data.datasetId, 200) };
    }
    return { sharded: false, found: data != null, value: data, datasetId: '' };
  }

  function evidenceEntry(cache, url, load) {
    let entry = cache.get(url);
    if (!entry) {
      entry = { status: 'loading' };
      cache.set(url, entry);
      entry.promise = Promise.resolve().then(() => load(url))
        .then((data) => { entry.status = 'ready'; entry.data = data; })
        .catch((err) => {
          entry.status = 'error'; entry.error = describeError(err);
          if (cache.get(url) === entry) cache.delete(url);
        });
    }
    return entry;
  }

  function watchEvidence(entry, body, show) {
    show(entry);
    if (entry.status === 'loading') entry.promise.then(() => { if (body.isConnected) show(entry); });
  }

  function metricText(value) {
    const saved = text(value.value, 200), unit = text(value.unit, 60);
    if (!saved) return 'Not recorded' + (unit ? ' \u00B7 ' + unit : '');
    return saved + (unit ? ' ' + unit : '');
  }

  // ---------------------------------------------------------------- colour helpers

  function hexToRgb(hex) {
    const h = String(hex).trim().replace('#', '');
    const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
    const v = parseInt(full.slice(0, 6), 16);
    if (!isFinite(v)) return [0.5, 0.5, 0.5];
    return [((v >> 16) & 255) / 255, ((v >> 8) & 255) / 255, (v & 255) / 255];
  }
  const mixRgb = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];

  // ================================================================ application

  function boot() {
    if (boot.started) return;
    boot.started = true;
    try { createApp(); } catch (err) {
      const box = document.getElementById('home-status');
      if (box) { box.hidden = false; box.className = 'status is-error'; box.textContent = 'The explorer could not start: ' + (err && err.message ? err.message : String(err)); }
      if (root.console) console.error(err);
    }
  }

  function el(tag, props) {
    const node = document.createElement(tag);
    if (props) {
      for (const key of Object.keys(props)) {
        const v = props[key];
        if (v == null || v === false) continue;
        if (key === 'class') node.className = v;
        else if (key === 'text') node.textContent = v;
        else if (key === 'data') for (const d of Object.keys(v)) node.dataset[d] = v[d];
        else if (key.slice(0, 2) === 'on' && typeof v === 'function') node.addEventListener(key.slice(2), v);
        else node.setAttribute(key, v === true ? '' : String(v));
      }
    }
    for (let a = 2; a < arguments.length; a++) appendKid(node, arguments[a]);
    return node;
  }
  function appendKid(node, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { for (const k of kid) appendKid(node, k); return; }
    node.append(kid.nodeType ? kid : String(kid));
  }
  function extLink(url, label, cls) {
    if (!url) return null;
    return el('a', { href: url, target: '_blank', rel: 'noopener noreferrer', class: cls || 'ext' }, label, el('span', { class: 'arrow-out', 'aria-hidden': 'true' }));
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src; s.async = true;
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('Could not load ' + src));
      document.head.appendChild(s);
    });
  }

  function describeError(err) {
    if (!err) return 'Unknown error.';
    if (err.name === 'SyntaxError') return 'The file is not valid JSON.';
    if (err.name === 'TypeError') return 'The file could not be reached. If you opened the page from disk, serve the folder over http instead.';
    return err.message || String(err);
  }

  function readConfig() {
    let cfg = root.EXPLORER_CONFIG;
    if (!cfg) {
      const tag = document.getElementById('explorer-config');
      if (tag) { try { cfg = JSON.parse(tag.textContent); } catch (e) { cfg = null; } }
    }
    return cfg && typeof cfg === 'object' && typeof cfg.manifestUrl === 'string' ? cfg : null;
  }

  function createApp() {
    const doc = document;
    const $ = (id) => doc.getElementById(id);
    const motion = root.matchMedia ? root.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
    const narrow = root.matchMedia ? root.matchMedia('(max-width: 760px)') : { matches: false };
    if (narrow.matches) $('legend').open = false;
    const timings = {
      bootMs: null, manifestMs: null, datasets: {}, buildMs: null, layoutMs: null, searchIndexMs: null,
      render2d: { last: null, avg: null, max: null, frames: 0 },
      city: { loadMs: null, initMs: null, sceneMs: null, last: null, avg: null, max: null, frames: 0 },
      searchMs: null, keyNavMs: null, libraryRenderMs: null, inspectorMs: null
    };
    const bootStart = now();

    // -------------------------------------------------------------- config
    const cfg = readConfig();
    const title = cfg ? text(cfg.title, 200) || 'Research explorer' : 'Research explorer';
    const assetBase = cfg && typeof cfg.assetBase === 'string' ? cfg.assetBase : (scriptSrc ? scriptSrc.replace(/[^/]*$/, '') : '');
    doc.title = title;
    for (const id of ['brand-title', 'home-title']) { const n = $(id); if (n) n.textContent = title; }
    if (cfg && cfg.fontUrl && root.FontFace && doc.fonts) {
      const furl = safeUrl(cfg.fontUrl, location.href, true);
      if (furl) {
        // The bundled Google Fonts latin file covers weights 400 to 600.
        const face = new FontFace('Source Serif 4', 'url("' + furl.replace(/["\\]/g, '') + '")', { weight: '400 600', style: 'normal', display: 'swap' });
        face.load().then((f) => { doc.fonts.add(f); readTheme(); requestRender(); }).catch(() => {});
      }
    }
    if (cfg && cfg.legacyUrl) {
      const legacy = safeUrl(cfg.legacyUrl, location.href, true);
      const a = $('legacy-link');
      if (legacy && a) { a.href = legacy; a.hidden = false; }
    }

    // -------------------------------------------------------------- state
    const state = {
      view: 'home', mode: 'treemap', datasets: [], selected: [], query: '',
      colorBy: 'kind', height: 'connections',
      hiddenKinds: new Set(), hiddenTypes: new Set(), hiddenEvidence: new Set()
    };
    let manifest = { datasets: [], defaultSelection: [], skipped: 0 };
    const metaById = new Map();
    const cache = new Map();
    let model = null, modelKey = '', layout = null, search = null, result = null;
    let loadToken = 0;
    let modelProblems = [];
    let nodeState = new Uint8Array(0), nodeColor = new Uint8Array(0);
    let edgeOn = new Uint8Array(0), edgeHot = new Uint8Array(0), hotEdges = [];
    let selIdx = [];
    let theme = {};
    let histDepth = 0;
    let focusFrame = -1;
    let hoverIdx = -1;

    // -------------------------------------------------------------- routing
    function parseHash() {
      const raw = (location.hash || '').replace(/^#\/?/, '');
      const q = raw.indexOf('?');
      const path = (q >= 0 ? raw.slice(0, q) : raw).replace(/\/+$/, '');
      const params = q >= 0 ? raw.slice(q + 1) : '';
      // Older reader links such as #sectors open the treemap; unknown hashes open Home.
      const legacy = LEGACY_ROUTES[path.toLowerCase()];
      const r = {
        view: legacy ? legacy.view : path === 'graph' ? 'graph' : path === 'library' ? 'library' : 'home',
        datasets: null, selected: [], query: '', mode: legacy ? legacy.mode : null, legacy: !!legacy
      };
      for (const part of params.split('&')) {
        if (!part) continue;
        const eq = part.indexOf('=');
        const key = eq >= 0 ? part.slice(0, eq) : part;
        const value = eq >= 0 ? part.slice(eq + 1) : '';
        const list = () => value.split(',').map((s) => { try { return decodeURIComponent(s); } catch (e) { return ''; } }).filter(Boolean);
        if (key === 'd') r.datasets = list();
        else if (key === 's') r.selected = list();
        else if (key === 'm') r.mode = MODES.includes(value) ? value : null;
        else if (key === 'q') { try { r.query = decodeURIComponent(value.replace(/\+/g, ' ')); } catch (e) { r.query = ''; } }
      }
      return r;
    }
    function hashFor() {
      const parts = [];
      if (state.datasets.length) parts.push('d=' + state.datasets.map(encodeURIComponent).join(','));
      if (state.view === 'graph' || state.mode !== 'treemap') parts.push('m=' + state.mode);
      if (state.selected.length) parts.push('s=' + state.selected.map(encodeURIComponent).join(','));
      if (state.query) parts.push('q=' + encodeURIComponent(state.query));
      return '#/' + (state.view === 'home' ? '' : state.view) + (parts.length ? '?' + parts.join('&') : '');
    }
    function commit(push) {
      const url = hashFor();
      if (url === location.hash) return;
      try {
        if (push) history.pushState({ explorer: 1, depth: ++histDepth }, '', url);
        else history.replaceState({ explorer: 1, depth: histDepth }, '', url);
      } catch (e) { /* sandboxed frames can refuse history writes */ }
    }
    const canGoBack = () => histDepth > 0;

    // -------------------------------------------------------------- theme
    function readTheme() {
      const cs = getComputedStyle(doc.documentElement);
      const v = (name, fallback) => (cs.getPropertyValue(name).trim() || fallback);
      const dark = doc.documentElement.dataset.theme === 'dark';
      theme = {
        dark,
        bg: v('--bg', '#F5F5F5'), surface: v('--surface', '#FFFFFF'), surface2: v('--surface-2', '#FAFAFA'),
        line: v('--line', '#E0E0E0'), lineStrong: v('--line-strong', '#8C8C8C'),
        ink: v('--ink', '#141414'), muted: v('--muted', '#525252'),
        select: v('--select', '#99BBFF'), selectStrong: v('--select-strong', '#99BBFF'), accent: v('--accent', '#0036A3'),
        edge: [v('--edge-observed', '#2F4F99'), v('--edge-inferred', '#C2621A'), v('--edge-unstated', '#8B8984')],
        palette: PALETTE[dark ? 'dark' : 'light'],
        dimAlpha: dark ? 0.3 : 0.26,
        sans: v('--sans', 'Helvetica Neue, Arial, sans-serif'),
        serif: v('--serif', 'Georgia, serif')
      };
    }
    function setTheme(t, persist) {
      doc.documentElement.dataset.theme = t;
      if (persist) { try { localStorage.setItem('explorer-theme', t); } catch (e) { /* private mode */ } }
      const btn = $('theme-toggle');
      if (btn) btn.setAttribute('aria-label', t === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
      readTheme();
      if (model) { refreshStyles(); renderLegend(); }
      if (city) city.setTheme(cityTheme());
      requestRender();
    }

    // -------------------------------------------------------------- manifest and datasets
    async function loadManifest() {
      const t0 = now();
      const url = new URL(cfg.manifestUrl, location.href).href;
      const res = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('The dataset list returned HTTP ' + res.status + '.');
      const data = await res.json();
      if (!data || data.schemaVersion !== 1) throw new Error('This explorer reads dataset list version 1; the file reports version ' + text(data && data.schemaVersion) + '.');
      const list = [];
      let skipped = 0;
      for (const d of Array.isArray(data.datasets) ? data.datasets : []) {
        const id = d && text(d.id, 200);
        const dsUrl = d && safeUrl(d.url, url, true);
        if (!id || !dsUrl || metaById.has(id)) { skipped++; continue; }
        const num = (v) => (typeof v === 'number' && isFinite(v) && v >= 0 ? Math.round(v) : null);
        const meta = {
          id, label: text(d.label, 200) || id, description: text(d.description, 2000),
          nodeCount: num(d.nodeCount), edgeCount: num(d.edgeCount), url: dsUrl,
          updatedAt: text(d.updatedAt, 60), public: d.public === true ? true : d.public === false ? false : null,
          sourceUrl: safeUrl(d.sourceUrl),
          overlapsWith: Array.isArray(d.overlapsWith) ? d.overlapsWith.map((value) => text(value, 200)).filter(Boolean) : [],
          overlapWarning: text(d.overlapWarning, 2000)
        };
        list.push(meta);
        metaById.set(id, meta);
      }
      const defaults = (Array.isArray(data.defaultSelection) ? data.defaultSelection : []).map((s) => text(s)).filter((s) => metaById.has(s));
      manifest = { datasets: list, defaultSelection: defaults, skipped };
      timings.manifestMs = now() - t0;
    }

    function orderedSelection(ids) {
      const set = new Set(ids);
      return manifest.datasets.filter((m) => set.has(m.id)).map((m) => m.id);
    }

    function loadDataset(meta) {
      let c = cache.get(meta.id);
      if (c) return c.promise;
      c = { status: 'loading', data: null, error: null };
      cache.set(meta.id, c);
      const t0 = now();
      c.promise = fetch(meta.url, { credentials: 'same-origin' })
        .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status + '.'); return r.text(); })
        .then((body) => {
          const t1 = now();
          c.data = JSON.parse(body);
          timings.datasets[meta.id] = { fetchMs: t1 - t0, parseMs: now() - t1, bytes: body.length };
          c.status = 'ready';
          return c;
        })
        .catch((err) => { c.status = 'error'; c.error = describeError(err); return c; })
        .then((v) => { if (state.view === 'home') renderHome(); return v; });
      return c.promise;
    }

    async function ensureModel() {
      const ids = orderedSelection(state.datasets);
      const key = ids.join('\u0001');
      if (model && key === modelKey) return true;
      const token = ++loadToken;
      if (!ids.length) {
        installModel(buildModel([]), key, []);
        return true;
      }
      const pending = ids.filter((id) => !cache.has(id) || cache.get(id).status === 'loading');
      if (pending.length) {
        showStageMessage('Loading ' + ids.map((id) => metaById.get(id).label).join(', ') + '\u2026', 'loading', null, 'model');
        $('library-counts').textContent = 'Loading records\u2026';
      }
      const loaded = await Promise.all(ids.map((id) => loadDataset(metaById.get(id))));
      if (token !== loadToken) return false;
      const entries = [], problems = [];
      ids.forEach((id, k) => {
        const c = loaded[k], meta = metaById.get(id);
        if (c.status === 'ready') entries.push({ meta, data: c.data, baseUrl: meta.url });
        else problems.push(meta.label + ' could not load: ' + c.error);
      });
      const t0 = now();
      const m = buildModel(entries);
      timings.buildMs = now() - t0;
      installModel(m, key, problems);
      return true;
    }

    function installModel(m, key, problems) {
      model = m; modelKey = key; modelProblems = problems;
      layout = computeLayout(model);
      timings.layoutMs = layout.ms;
      search = createSearchIndex(model);
      timings.searchIndexMs = search.ms;
      const n = model.nodes.length;
      nodeState = new Uint8Array(n); nodeColor = new Uint8Array(n);
      edgeOn = new Uint8Array(model.edges.length); edgeHot = new Uint8Array(model.edges.length);
      for (const k of [...state.hiddenKinds]) if (!model.kindIndex.has(k)) state.hiddenKinds.delete(k);
      const types = new Set(model.edgeTypes.map((t) => t.name));
      for (const t of [...state.hiddenTypes]) if (!types.has(t)) state.hiddenTypes.delete(t);
      focusFrame = -1; hoverIdx = -1;
      const kept = state.selected.filter((u) => model.byUid.has(u));
      if (kept.length !== state.selected.length) { state.selected = kept; commit(false); }
      runQuery();
      assignColors();
      refreshStyles();
      cityKey = '';
      fit2d(false);
      hideStageMessage('model');
    }

    // -------------------------------------------------------------- styles
    function assignColors() {
      if (!model) return;
      const nodes = model.nodes;
      for (let i = 0; i < nodes.length; i++) {
        if (state.colorBy === 'dataset') nodeColor[i] = nodes[i].d % 8;
        else { const k = model.kindIndex.get(nodes[i].kind); nodeColor[i] = k < 8 ? k : 8; }
      }
    }

    function refreshStyles() {
      if (!model) return;
      const n = model.nodes.length, E = model.edges;
      selIdx = state.selected.map((u) => model.byUid.get(u)).filter(Boolean).map((nd) => nd.i);
      for (let e = 0; e < E.length; e++) {
        edgeOn[e] = state.hiddenTypes.has(E[e].type) || state.hiddenEvidence.has(E[e].evidence) ? 0 : 1;
        edgeHot[e] = 0;
      }
      const neighbor = new Uint8Array(n);
      hotEdges = [];
      for (const s of selIdx) {
        for (let p = model.adjStart[s]; p < model.adjStart[s + 1]; p++) {
          const e = model.adj[p];
          if (!edgeOn[e] || edgeHot[e]) continue;
          edgeHot[e] = 1;
          if (hotEdges.length < HOT_EDGE_LIMIT) hotEdges.push(e);
          neighbor[E[e].s === s ? E[e].t : E[e].s] = 1;
        }
      }
      const selSet = new Set(selIdx);
      const hasSel = selIdx.length > 0, mask = result ? result.mask : null;
      const hidden = state.hiddenKinds.size ? state.hiddenKinds : null;
      for (let i = 0; i < n; i++) {
        let st;
        if (selSet.has(i)) st = S_SELECTED;
        else if (hidden && hidden.has(model.nodes[i].kind)) st = S_HIDDEN;
        else if (hasSel) st = neighbor[i] ? S_NEIGHBOR : S_DIM;
        else if (mask) st = mask[i] ? S_MATCH : S_DIM;
        else st = S_NORMAL;
        nodeState[i] = st;
      }
      if (city && cityKey) { city.setColors(cityColors()); city.setLinks(cityLinks()); }
    }

    // -------------------------------------------------------------- 2D canvas
    const cv = $('canvas-2d');
    const ctx = cv.getContext('2d', { alpha: false });
    const v2 = { w: 0, h: 0, dpr: 1, k: 1, tx: 0, ty: 0, fitK: 1, raf: 0, anim: 0, truncated: false, drawnEdges: 0, visible: 0 };
    const buckets = Array.from({ length: 6 * PAL }, () => []);
    const renderSamples = [];

    function requestRender() {
      if (state.view !== 'graph') return;
      if (state.mode === 'city') { if (city) city.requestRender(); return; }
      if (!v2.raf) v2.raf = requestAnimationFrame(draw2d);
    }
    function resize2d() {
      const r = cv.getBoundingClientRect();
      const dpr = Math.min(root.devicePixelRatio || 1, 2);
      const w = Math.round(r.width), h = Math.round(r.height);
      if (!w || !h) return;
      if (w === v2.w && h === v2.h && dpr === v2.dpr) return;
      const had = v2.w > 0;
      const cx = had ? (v2.w / 2 - v2.tx) / v2.k : null, cy = had ? (v2.h / 2 - v2.ty) / v2.k : null;
      v2.w = w; v2.h = h; v2.dpr = dpr;
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      if (!layout) return;
      const prevFit = v2.fitK;
      v2.fitK = fitScale(0, 0, layout.W, layout.H);
      if (!had || v2.needsFit) { fit2d(false); return; }
      v2.k = clamp(v2.k * (v2.fitK / prevFit), v2.fitK * 0.5, v2.fitK * 800);
      v2.tx = w / 2 - cx * v2.k; v2.ty = h / 2 - cy * v2.k;
      requestRender();
    }
    function margin() { return narrow.matches ? 10 : 24; }
    function fitScale(x, y, w, h) {
      const m = margin();
      return Math.min((v2.w - 2 * m) / Math.max(w, 1e-6), (v2.h - 2 * m) / Math.max(h, 1e-6));
    }
    function fitRect2d(x, y, w, h, animate) {
      if (!v2.w) { v2.needsFit = true; return; }
      v2.needsFit = false;
      const k = clamp(fitScale(x, y, w, h), v2.fitK * 0.5, v2.fitK * 800);
      setCamera2d(k, v2.w / 2 - (x + w / 2) * k, v2.h / 2 - (y + h / 2) * k, animate);
    }
    function fit2d(animate) {
      if (!layout) return;
      if (v2.w) v2.fitK = fitScale(0, 0, layout.W, layout.H);
      focusFrame = -1;
      fitRect2d(0, 0, layout.W, layout.H, animate);
      renderTrail();
    }
    function setCamera2d(k, tx, ty, animate) {
      cancelAnimationFrame(v2.anim); v2.anim = 0;
      if (!animate || motion.matches) { v2.k = k; v2.tx = tx; v2.ty = ty; requestRender(); return; }
      const from = { cx: (v2.w / 2 - v2.tx) / v2.k, cy: (v2.h / 2 - v2.ty) / v2.k, lk: Math.log(v2.k) };
      const to = { cx: (v2.w / 2 - tx) / k, cy: (v2.h / 2 - ty) / k, lk: Math.log(k) };
      const t0 = now(), dur = 220;
      const step = () => {
        const p = Math.min(1, (now() - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        const kk = Math.exp(from.lk + (to.lk - from.lk) * e);
        v2.k = kk;
        v2.tx = v2.w / 2 - (from.cx + (to.cx - from.cx) * e) * kk;
        v2.ty = v2.h / 2 - (from.cy + (to.cy - from.cy) * e) * kk;
        draw2d();
        v2.anim = p < 1 ? requestAnimationFrame(step) : 0;
      };
      v2.anim = requestAnimationFrame(step);
    }
    function zoomAt2d(sx, sy, f) {
      const k = clamp(v2.k * f, v2.fitK * 0.5, v2.fitK * 800);
      const wx = (sx - v2.tx) / v2.k, wy = (sy - v2.ty) / v2.k;
      v2.k = k; v2.tx = sx - wx * k; v2.ty = sy - wy * k;
      requestRender();
    }

    function draw2d() {
      v2.raf = 0;
      if (state.view !== 'graph' || state.mode === 'city') return;
      if (!v2.w) resize2d();
      if (!v2.w) return;
      const t0 = now();
      const { w, h, dpr, k, tx, ty } = v2;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.globalAlpha = 1; ctx.setLineDash([]);
      ctx.fillStyle = theme.bg; ctx.fillRect(0, 0, w, h);
      if (!model || !layout || !model.nodes.length) return;
      const R = layout.rects, n = model.nodes.length;
      const x0 = -tx / k, y0 = -ty / k, x1 = (w - tx) / k, y1 = (h - ty) / k;
      const tree = state.mode === 'treemap';

      // Frames: datasets, groups and subgroups.
      const labels = [];
      ctx.lineWidth = 1;
      for (const f of layout.frames) {
        if (f.x > x1 || f.y > y1 || f.x + f.w < x0 || f.y + f.h < y0) continue;
        const sw = f.w * k, sh = f.h * k;
        if (sw < 3 || sh < 3) continue;
        const sx = Math.round(f.x * k + tx) + 0.5, sy = Math.round(f.y * k + ty) + 0.5;
        if (tree) { ctx.fillStyle = f.level === 2 ? theme.surface2 : theme.surface; ctx.fillRect(sx, sy, Math.round(sw) - 1, Math.round(sh) - 1); }
        ctx.strokeStyle = f.level === 0 ? theme.lineStrong : theme.line;
        ctx.globalAlpha = f.level === 0 && !tree ? 0.6 : 1;
        ctx.strokeRect(sx, sy, Math.round(sw) - 1, Math.round(sh) - 1);
        ctx.globalAlpha = 1;
        const hh = f.head * k;
        if (hh >= 10 && sw > 40) labels.push(f);
      }

      // Records, bucketed by state and colour so each bucket is one path.
      for (let b = 0; b < buckets.length; b++) buckets[b].length = 0;
      let visible = 0;
      for (let i = 0; i < n; i++) {
        const o = i << 2, x = R[o], y = R[o + 1];
        if (x > x1 || y > y1 || x + R[o + 2] < x0 || y + R[o + 3] < y0) continue;
        buckets[nodeState[i] * PAL + nodeColor[i]].push(i);
        visible++;
      }
      v2.visible = visible;
      if (!tree) drawEdges(R, k, tx, ty, x0, y0, x1, y1, true);
      for (const st of DRAW_ORDER) {
        ctx.globalAlpha = st === S_DIM ? theme.dimAlpha : st === S_HIDDEN ? 0.08 : 1;
        for (let c = 0; c < PAL; c++) {
          const list = buckets[st * PAL + c];
          if (!list.length) continue;
          ctx.fillStyle = st === S_SELECTED ? (tree ? theme.select : theme.accent) : theme.palette[c];
          ctx.beginPath();
          for (let q = 0; q < list.length; q++) {
            const o = list[q] << 2;
            const sx = R[o] * k + tx, sy = R[o + 1] * k + ty, sw = R[o + 2] * k, sh = R[o + 3] * k;
            if (tree) {
              const g = sw > 3 && sh > 3 ? 0.5 : 0;
              ctx.rect(sx + g, sy + g, sw - 2 * g, sh - 2 * g);
            } else {
              const cx = sx + sw / 2, cy = sy + sh / 2;
              const r = clamp(Math.min(sw, sh) * 0.3, 1.1, 10) * (st === S_SELECTED ? 1.35 : 1);
              if (r < 2) ctx.rect(cx - r, cy - r, r * 2, r * 2);
              else { ctx.moveTo(cx + r, cy); ctx.arc(cx, cy, r, 0, Math.PI * 2); }
            }
          }
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      drawEdges(R, k, tx, ty, x0, y0, x1, y1, false);

      // Outlines for neighbours, selection and hover.
      const outline = (i, color, width) => {
        const o = i << 2;
        const sx = R[o] * k + tx, sy = R[o + 1] * k + ty, sw = R[o + 2] * k, sh = R[o + 3] * k;
        ctx.strokeStyle = color; ctx.lineWidth = width;
        if (tree) ctx.strokeRect(sx + width / 2, sy + width / 2, Math.max(1, sw - width), Math.max(1, sh - width));
        else {
          const r = clamp(Math.min(sw, sh) * 0.3, 1.1, 10) * 1.35 + 2;
          ctx.beginPath(); ctx.arc(sx + sw / 2, sy + sh / 2, r, 0, Math.PI * 2); ctx.stroke();
        }
      };
      if (tree) {
        ctx.globalAlpha = 0.6;
        for (let c = 0; c < PAL; c++) for (const i of buckets[S_NEIGHBOR * PAL + c]) outline(i, theme.ink, 1);
        ctx.globalAlpha = 1;
      }
      for (const i of selIdx) outline(i, theme.accent, 2);
      if (hoverIdx >= 0 && hoverIdx < n) outline(hoverIdx, theme.ink, 1.5);

      // Labels.
      ctx.textBaseline = 'middle';
      for (const f of labels) {
        const sx = f.x * k + tx, sy = f.y * k + ty, sw = f.w * k, hh = f.head * k;
        const fs = clamp(hh * 0.62, 9, f.level === 0 ? 16 : 14);
        ctx.font = (f.level === 0 ? '400 ' + fs + 'px ' + theme.serif : (f.level === 1 ? '600 ' : '400 ') + fs + 'px ' + theme.sans);
        const label = f.label, count = fmt(f.count);
        const avail = sw - 12;
        let shown = label;
        let lw = ctx.measureText(shown).width;
        if (lw > avail) {
          const chars = Math.max(1, Math.floor(shown.length * (avail / lw)) - 1);
          shown = shown.slice(0, chars) + '\u2026';
          lw = ctx.measureText(shown).width;
        }
        const ly = sy + Math.max(hh * 0.55, fs * 0.65) + 1;
        ctx.fillStyle = theme.ink;
        ctx.fillText(shown, sx + 6, ly);
        if (lw + 40 < avail) {
          ctx.fillStyle = theme.muted;
          ctx.font = '400 ' + Math.max(9, fs - 2) + 'px ' + theme.sans;
          ctx.fillText(count, sx + 12 + lw, ly);
        }
      }
      drawRecordLabels(R, k, tx, ty, tree);
      if (selIdx.length) drawChip(selIdx[selIdx.length - 1], R, k, tx, ty, tree);

      const ms = now() - t0;
      renderSamples.push(ms); if (renderSamples.length > 60) renderSamples.shift();
      const r2 = timings.render2d;
      r2.last = ms; r2.frames++; r2.max = Math.max(r2.max || 0, ms);
      r2.avg = renderSamples.reduce((a, b) => a + b, 0) / renderSamples.length;
      r2.visibleRecords = visible; r2.drawnEdges = v2.drawnEdges;
    }

    function drawEdges(R, k, tx, ty, x0, y0, x1, y1, background) {
      const E = model.edges;
      if (background) { v2.drawnEdges = 0; v2.truncated = false; }
      const hasSel = selIdx.length > 0;
      ctx.lineWidth = background ? 1 : 1.6;
      for (let c = 0; c < 3; c++) {
        if (state.hiddenEvidence.has(EV[c])) continue;
        const list = background ? model.byEvidence[c] : null;
        ctx.strokeStyle = theme.edge[c];
        ctx.setLineDash(c === 1 ? [5, 4] : c === 2 ? [1.5, 3] : []);
        ctx.globalAlpha = background ? (hasSel ? 0.07 : c === 0 ? 0.3 : 0.36) : 0.92;
        ctx.beginPath();
        let any = false;
        const add = (e) => {
          const a = E[e].s << 2, b = E[e].t << 2;
          const ax = R[a] + R[a + 2] / 2, ay = R[a + 1] + R[a + 3] / 2, bx = R[b] + R[b + 2] / 2, by = R[b + 1] + R[b + 3] / 2;
          if ((ax < x0 && bx < x0) || (ax > x1 && bx > x1) || (ay < y0 && by < y0) || (ay > y1 && by > y1)) return;
          ctx.moveTo(ax * k + tx, ay * k + ty); ctx.lineTo(bx * k + tx, by * k + ty);
          any = true; v2.drawnEdges++;
        };
        if (background) {
          for (let q = 0; q < list.length; q++) {
            const e = list[q];
            if (!edgeOn[e] || edgeHot[e]) continue;
            if (v2.drawnEdges >= EDGE_DRAW_BUDGET) { v2.truncated = true; break; }
            add(e);
          }
        } else {
          for (const e of hotEdges) if (E[e].evidence === EV[c]) add(e);
        }
        if (any) ctx.stroke();
      }
      ctx.setLineDash([]);
      if (!background) {
        // Arrowheads on directed connections of the selection.
        ctx.globalAlpha = 0.92;
        for (const e of hotEdges) {
          const ed = E[e];
          if (!ed.directed) continue;
          const a = ed.s << 2, b = ed.t << 2;
          const ax = (R[a] + R[a + 2] / 2) * k + tx, ay = (R[a + 1] + R[a + 3] / 2) * k + ty;
          const bx = (R[b] + R[b + 2] / 2) * k + tx, by = (R[b + 1] + R[b + 3] / 2) * k + ty;
          const len = Math.hypot(bx - ax, by - ay);
          if (len < 14) continue;
          const ux = (bx - ax) / len, uy = (by - ay) / len;
          const back = Math.min(len * 0.25, clamp(Math.min(R[b + 2], R[b + 3]) * k * 0.32, 3, 12) + 3);
          const px = bx - ux * back, py = by - uy * back;
          ctx.fillStyle = theme.edge[EV.indexOf(ed.evidence)];
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(px - ux * 8 - uy * 4, py - uy * 8 + ux * 4);
          ctx.lineTo(px - ux * 8 + uy * 4, py - uy * 8 - ux * 4);
          ctx.closePath(); ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    }

    function truncateTo(label, px, charW) {
      const max = Math.floor(px / charW);
      if (max < 3) return '';
      return label.length > max ? label.slice(0, max - 1) + '\u2026' : label;
    }

    function drawRecordLabels(R, k, tx, ty, tree) {
      let budget = 450;
      ctx.textBaseline = 'top';
      ctx.font = '400 11px ' + theme.sans;
      const charW = 6.1;
      const drawFor = (st, alpha) => {
        ctx.globalAlpha = alpha;
        for (let c = 0; c < PAL && budget > 0; c++) {
          const list = buckets[st * PAL + c];
          for (let q = 0; q < list.length && budget > 0; q++) {
            const i = list[q], o = i << 2;
            const sw = R[o + 2] * k, sh = R[o + 3] * k;
            if (tree) {
              if (sw < 56 || sh < 18) continue;
              const s = truncateTo(model.nodes[i].label, sw - 8, charW);
              if (!s) continue;
              ctx.fillStyle = theme.ink;
              ctx.fillText(s, R[o] * k + tx + 4, R[o + 1] * k + ty + 4);
            } else {
              if (sw < (st === S_NEIGHBOR || st === S_SELECTED ? 20 : 70)) continue;
              const r = clamp(Math.min(sw, sh) * 0.3, 1.1, 10);
              const s = truncateTo(model.nodes[i].label, Math.max(sw * 0.5 - r, 90), charW);
              if (!s) continue;
              const lx = R[o] * k + tx + sw / 2 + r + 4, ly = R[o + 1] * k + ty + sh / 2 - 6;
              ctx.lineWidth = 3; ctx.strokeStyle = theme.bg; ctx.strokeText(s, lx, ly);
              ctx.fillStyle = theme.ink; ctx.fillText(s, lx, ly);
            }
            budget--;
          }
        }
      };
      drawFor(S_SELECTED, 1);
      drawFor(S_NEIGHBOR, 1);
      drawFor(S_MATCH, 1);
      drawFor(S_NORMAL, 1);
      drawFor(S_DIM, 0.4);
      ctx.globalAlpha = 1;
    }

    function drawChip(i, R, k, tx, ty, tree) {
      const o = i << 2;
      const sw = R[o + 2] * k;
      if (tree && sw >= 56 && R[o + 3] * k >= 18) return; // already labelled in place
      const label = truncateTo(model.nodes[i].label, 260, 6.6);
      ctx.font = '600 12px ' + theme.sans;
      const tw = ctx.measureText(label).width;
      const cx = R[o] * k + tx + sw / 2, top = R[o + 1] * k + ty;
      let x = clamp(cx - tw / 2 - 8, 6, v2.w - tw - 22), y = top - 30;
      if (y < 6) y = top + R[o + 3] * k + 8;
      ctx.globalAlpha = 1;
      ctx.fillStyle = theme.surface; ctx.strokeStyle = theme.accent; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.rect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(tw + 16), 22); ctx.fill(); ctx.stroke();
      ctx.fillStyle = theme.ink; ctx.textBaseline = 'middle';
      ctx.fillText(label, x + 8, y + 12);
    }

    // -------------------------------------------------------------- city (lazy)
    let city = null, cityLoading = null, cityKey = '', cityUnavailable = '';
    function cityTheme() {
      return { dark: theme.dark, bg: hexToRgb(theme.bg), surface: hexToRgb(theme.surface), line: hexToRgb(theme.line), edge: theme.edge.map(hexToRgb) };
    }
    function ensureCity() {
      if (city) return Promise.resolve(city);
      if (cityUnavailable) return Promise.resolve(null);
      if (!cityLoading) {
        const t0 = now();
        cityLoading = loadScript(assetBase + 'city.js').then(() => {
          timings.city.loadMs = now() - t0;
          if (!root.ExplorerCity) throw new Error('The city renderer did not register.');
          const t1 = now();
          const c = root.ExplorerCity.create($('canvas-3d'), {
            labels: $('city-labels'),
            reducedMotion: () => motion.matches,
            onPick: (i, ev) => { if (i < 0) { if (!ev.shiftKey) select([], { push: true }); return; } pickRecord(i, ev); },
            onHover: (i, x, y) => { showHover(i, x, y); },
            onFrame: (stats) => { const c3 = timings.city; c3.last = stats.ms; c3.frames++; c3.max = Math.max(c3.max || 0, stats.ms); c3.avg = stats.avg; },
            onLost: () => showStageMessage('The 3D view lost its graphics context. It returns when the browser restores it.', 'error', null, 'city'),
            onRestored: () => { hideStageMessage('city'); cityKey = ''; activateCity(); }
          });
          timings.city.initMs = now() - t1;
          if (!c) { cityUnavailable = 'This browser cannot show the 3D city because WebGL 2 is unavailable. The treemap uses the same layout.'; return null; }
          city = c;
          city.setTheme(cityTheme());
          return city;
        }).catch((err) => { cityUnavailable = describeError(err); cityLoading = null; return null; });
      }
      return cityLoading;
    }
    function cityHeights() {
      const n = model.nodes.length, out = new Float32Array(n * 2);
      const max = model.maxDegree;
      for (let i = 0; i < n; i++) {
        const f = layout.frames[layout.nodeFrame[i]];
        out[i * 2] = (f ? f.level + 1 : 1) * 0.6;
        out[i * 2 + 1] = state.height === 'flat' || !max ? CITY_FLAT_H : CITY_FLAT_H + (model.degree[i] / max) * CITY_MAX_H;
      }
      return out;
    }
    function cityColors() {
      const n = model.nodes.length, out = new Float32Array(n * 4);
      const pal = theme.palette.map(hexToRgb), bg = hexToRgb(theme.bg), sel = hexToRgb(theme.accent), ink = hexToRgb(theme.ink);
      for (let i = 0; i < n; i++) {
        const st = nodeState[i];
        let c = pal[nodeColor[i]];
        if (st === S_SELECTED) c = sel;
        else if (st === S_DIM) c = mixRgb(c, bg, 0.7);
        else if (st === S_HIDDEN) c = mixRgb(c, bg, 0.9);
        else if (st === S_NEIGHBOR) c = mixRgb(c, ink, 0.12);
        out[i * 4] = c[0]; out[i * 4 + 1] = c[1]; out[i * 4 + 2] = c[2]; out[i * 4 + 3] = 1;
      }
      return out;
    }
    function cityLinks() {
      const pairs = new Int32Array(hotEdges.length * 2), styles = new Uint8Array(hotEdges.length);
      hotEdges.forEach((e, q) => { const ed = model.edges[e]; pairs[q * 2] = ed.s; pairs[q * 2 + 1] = ed.t; styles[q] = EV.indexOf(ed.evidence); });
      return { pairs, styles };
    }
    function citySceneData() {
      const fr = layout.frames;
      const frames = new Float32Array(fr.length * 4), levels = new Uint8Array(fr.length);
      fr.forEach((f, q) => { frames[q * 4] = f.x; frames[q * 4 + 1] = f.y; frames[q * 4 + 2] = f.w; frames[q * 4 + 3] = f.h; levels[q] = f.level; });
      const top = fr.filter((f) => f.level <= 1 && f.head > 0).sort((a, b) => b.w * b.h - a.w * a.h).slice(0, 24)
        .map((f) => ({ x: f.x + 2, z: f.y + f.head * 0.5 + 1, y: (f.level + 1) * 0.6, text: f.label }));
      return { W: layout.W, H: layout.H, rects: layout.rects, ids: model.nodes.map((nd) => nd.uid), yh: cityHeights(), colors: cityColors(), frames, frameLevels: levels, labels: top };
    }
    function activateCity() {
      if (state.mode !== 'city' || state.view !== 'graph') return;
      if (!city) showStageMessage('Loading the 3D city\u2026', 'loading', null, 'city');
      ensureCity().then((c) => {
        if (state.mode !== 'city' || state.view !== 'graph') return;
        if (!c) {
          showStageMessage(cityUnavailable, 'error', { label: 'Show treemap', run: () => setMode('treemap', true) }, 'city');
          return;
        }
        hideStageMessage('city');
        if (!model.nodes.length) return;
        cv.hidden = true; $('canvas-3d').hidden = false; $('city-labels').hidden = false;
        c.resize();
        if (cityKey !== modelKey + '|' + state.height) {
          const t0 = now();
          const fresh = !cityKey.startsWith(modelKey + '|') || !cityKey;
          c.setScene(citySceneData());
          timings.city.sceneMs = now() - t0;
          cityKey = modelKey + '|' + state.height;
          if (fresh) c.fit();
        } else c.setColors(cityColors());
        c.setLinks(cityLinks());
        c.requestRender();
        renderLegend();
      });
    }
    function activate2D() {
      $('canvas-3d').hidden = true; $('city-labels').hidden = true; cv.hidden = false;
      hideStageMessage('city');
      resize2d();
      requestRender();
    }

    // -------------------------------------------------------------- stage messages and hover
    let messageOwner = '';
    function showStageMessage(msg, kind, action, owner) {
      const box = $('stage-message');
      box.replaceChildren(el('p', { text: msg }), action ? el('button', { type: 'button', class: 'button', text: action.label, onclick: action.run }) : null);
      box.className = 'stage-message is-' + kind;
      box.hidden = false;
      messageOwner = owner || kind;
    }
    function hideStageMessage(owner) {
      if (owner && owner !== messageOwner) return;
      $('stage-message').hidden = true;
      messageOwner = '';
    }

    function showHover(i, x, y) {
      const tip = $('hover');
      if (i === hoverIdx && !tip.hidden) { positionTip(tip, x, y); return; }
      hoverIdx = i;
      if (i < 0 || !model || !model.nodes[i]) { tip.hidden = true; requestRender(); return; }
      const nd = model.nodes[i];
      const where = [nd.group, nd.subgroup].filter(Boolean).join(' \u203A ');
      tip.replaceChildren(
        el('strong', { text: nd.label }),
        el('span', { text: [nd.kind || 'Kind not recorded', where].filter(Boolean).join(' \u00B7 ') }),
        el('span', { text: plural(model.degree[i], 'connection') })
      );
      tip.hidden = false;
      positionTip(tip, x, y);
      requestRender();
    }
    function positionTip(tip, x, y) {
      const stage = $('stage').getBoundingClientRect();
      const tw = tip.offsetWidth || 220, th = tip.offsetHeight || 60;
      let lx = x - stage.left + 14, ly = y - stage.top + 14;
      if (lx + tw > stage.width - 8) lx = x - stage.left - tw - 14;
      if (ly + th > stage.height - 8) ly = y - stage.top - th - 14;
      tip.style.transform = 'translate(' + Math.max(4, lx) + 'px,' + Math.max(4, ly) + 'px)';
    }

    // -------------------------------------------------------------- selection
    function select(uids, opts) {
      opts = opts || {};
      const valid = model ? uids.filter((u) => model.byUid.has(u)) : [];
      const same = valid.length === state.selected.length && valid.every((u, q) => u === state.selected[q]);
      state.selected = valid;
      if (!same) commit(opts.push !== false);
      refreshStyles();
      requestRender();
      renderInspector();
      if (state.view === 'library') { renderLibraryRows(); renderLibraryDetail(); }
      const primary = valid.length ? model.byUid.get(valid[valid.length - 1]) : null;
      announce(primary ? 'Selected ' + primary.label + '. ' + plural(model.degree[primary.i], 'connection') + '.' : 'Selection cleared.');
      if (primary && opts.reveal) revealRecord(primary.i, opts.zoom);
    }
    function pickRecord(i, ev) {
      const uid = model.nodes[i].uid;
      if (ev && (ev.shiftKey || ev.metaKey || ev.ctrlKey)) {
        const has = state.selected.includes(uid);
        select(has ? state.selected.filter((u) => u !== uid) : state.selected.concat(uid), { push: true });
      } else select([uid], { push: true });
    }
    function revealRecord(i, zoom) {
      if (state.mode === 'city') { if (city && cityKey) city.focus(i, !!zoom); return; }
      const o = i * 4, R = layout.rects;
      const sw = R[o + 2] * v2.k;
      if (zoom && sw < 14) {
        const f = layout.frames[layout.nodeFrame[i]];
        if (f) { focusFrame = f.i; fitRect2d(f.x, f.y, f.w, f.h, true); renderTrail(); return; }
      }
      const cx = (R[o] + R[o + 2] / 2) * v2.k + v2.tx, cy = (R[o + 1] + R[o + 3] / 2) * v2.k + v2.ty;
      const m = 48;
      if (cx < m || cy < m || cx > v2.w - m || cy > v2.h - m) {
        setCamera2d(v2.k, v2.w / 2 - (R[o] + R[o + 2] / 2) * v2.k, v2.h / 2 - (R[o + 1] + R[o + 3] / 2) * v2.k, false);
      }
    }
    function announce(msg) { const live = $('live'); if (live) live.textContent = msg; }

    // -------------------------------------------------------------- pointer input (2D)
    const pointers = new Map();
    let drag = null, pinch = null;
    cv.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 && e.pointerType === 'mouse') return;
      cv.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pointers.size === 1) drag = { sx: e.clientX, sy: e.clientY, lx: e.clientX, ly: e.clientY, moved: false };
      else if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = { dist: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
        if (drag) drag.moved = true;
      }
    });
    cv.addEventListener('pointermove', (e) => {
      const p = pointers.get(e.pointerId);
      if (!p) {
        if (e.pointerType === 'mouse' && model) {
          const rect = cv.getBoundingClientRect();
          showHover(pick2d(e.clientX - rect.left, e.clientY - rect.top), e.clientX, e.clientY);
        }
        return;
      }
      p.x = e.clientX; p.y = e.clientY;
      if (pointers.size >= 2 && pinch) {
        const [a, b] = [...pointers.values()];
        const dist = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        const rect = cv.getBoundingClientRect();
        v2.tx += mx - pinch.mx; v2.ty += my - pinch.my;
        if (pinch.dist > 0) zoomAt2d(mx - rect.left, my - rect.top, dist / pinch.dist);
        pinch = { dist, mx, my };
        requestRender();
        return;
      }
      if (!drag) return;
      if (!drag.moved && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) { drag.moved = true; cv.classList.add('is-dragging'); showHover(-1); }
      if (drag.moved) { v2.tx += e.clientX - drag.lx; v2.ty += e.clientY - drag.ly; requestRender(); }
      drag.lx = e.clientX; drag.ly = e.clientY;
    });
    const endPointer = (e, cancelled) => {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinch = null;
      if (pointers.size === 0) {
        if (drag && !drag.moved && !cancelled) {
          const rect = cv.getBoundingClientRect();
          click2d(e.clientX - rect.left, e.clientY - rect.top, e);
        }
        drag = null;
        cv.classList.remove('is-dragging');
      }
    };
    cv.addEventListener('pointerup', (e) => endPointer(e, false));
    cv.addEventListener('pointercancel', (e) => endPointer(e, true));
    cv.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !pointers.size) showHover(-1); });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const rect = cv.getBoundingClientRect();
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      zoomAt2d(e.clientX - rect.left, e.clientY - rect.top, Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0018)));
    }, { passive: false });
    cv.addEventListener('dblclick', (e) => {
      const rect = cv.getBoundingClientRect();
      zoomAt2d(e.clientX - rect.left, e.clientY - rect.top, 2);
    });

    function pick2d(sx, sy) {
      if (!layout) return -1;
      const wx = (sx - v2.tx) / v2.k, wy = (sy - v2.ty) / v2.k;
      const i = hitTest(layout, wx, wy);
      if (i < 0 || state.mode === 'treemap') return i;
      const o = i * 4, R = layout.rects;
      const cx = (R[o] + R[o + 2] / 2) * v2.k + v2.tx, cy = (R[o + 1] + R[o + 3] / 2) * v2.k + v2.ty;
      const r = clamp(Math.min(R[o + 2], R[o + 3]) * v2.k * 0.3, 1.1, 10);
      return Math.hypot(sx - cx, sy - cy) <= Math.max(r + 4, 9) ? i : -1;
    }
    function click2d(sx, sy, ev) {
      const i = pick2d(sx, sy);
      if (i >= 0) { pickRecord(i, ev); return; }
      const wx = (sx - v2.tx) / v2.k, wy = (sy - v2.ty) / v2.k;
      for (let q = layout ? layout.frames.length - 1 : -1; q >= 0; q--) {
        const f = layout.frames[q];
        if (f.head > 0 && wx >= f.x && wx <= f.x + f.w && wy >= f.y && wy <= f.y + f.head + 2) { zoomToFrame(f.i); return; }
      }
      if (state.selected.length && !(ev && ev.shiftKey)) select([], { push: true });
    }
    function zoomToFrame(fi) {
      if (fi < 0 || !layout) { fit2d(true); if (city && state.mode === 'city') city.fit(); return; }
      const f = layout.frames[fi];
      focusFrame = fi;
      if (state.mode === 'city') { if (city) city.fitRect(f.x, f.y, f.w, f.h); }
      else fitRect2d(f.x, f.y, f.w, f.h, true);
      renderTrail();
    }

    // -------------------------------------------------------------- keyboard on the stage
    function onStageKey(e) {
      if (!model || e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.key;
      const dirs = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (dirs[key]) {
        e.preventDefault();
        const [dx, dy] = dirs[key];
        if (e.shiftKey) {
          if (state.mode === 'city') { if (city) city.rotate(dx * 0.12, -dy * 0.08); }
          else { v2.tx -= dx * 90; v2.ty -= dy * 90; requestRender(); }
          return;
        }
        moveSelection(dx, dy);
      } else if (key === '+' || key === '=') { e.preventDefault(); zoomBy(1.5); }
      else if (key === '-' || key === '_') { e.preventDefault(); zoomBy(1 / 1.5); }
      else if (key === '0' || key === 'f' || key === 'F') { e.preventDefault(); zoomToFrame(-1); }
      else if (key === 'Enter' && state.selected.length) { e.preventDefault(); go('library', true); }
    }
    function zoomBy(f) {
      if (state.mode === 'city') { if (city) city.zoomBy(f); return; }
      zoomAt2d(v2.w / 2, v2.h / 2, f);
    }
    function moveSelection(dx, dy) {
      const t0 = now();
      const n = model.nodes.length;
      if (!n) return;
      const mask = result ? result.mask : null;
      const hidden = state.hiddenKinds;
      const allow = (j) => (!mask || mask[j]) && !hidden.has(model.nodes[j].kind);
      let from = selIdx.length ? selIdx[selIdx.length - 1] : -1;
      let next = -1;
      if (from < 0) {
        // Start from the record nearest the view centre.
        let cx, cy;
        if (state.mode === 'city' && city) { const t = city.target(); cx = t[0]; cy = t[1]; }
        else { cx = (v2.w / 2 - v2.tx) / v2.k; cy = (v2.h / 2 - v2.ty) / v2.k; }
        let best = Infinity;
        const R = layout.rects;
        for (let j = 0; j < n; j++) {
          if (!allow(j)) continue;
          const o = j * 4, d = Math.hypot(R[o] + R[o + 2] / 2 - cx, R[o + 1] + R[o + 3] / 2 - cy);
          if (d < best) { best = d; next = j; }
        }
      } else {
        let wdx = dx, wdy = dy;
        if (state.mode === 'city' && city) [wdx, wdy] = city.screenDirToWorld(dx, dy);
        next = nearestInDirection(layout.rects, n, from, wdx, wdy, allow);
      }
      timings.keyNavMs = now() - t0;
      if (next >= 0) select([model.nodes[next].uid], { push: false, reveal: true });
    }
    cv.addEventListener('keydown', onStageKey);
    $('canvas-3d').addEventListener('keydown', onStageKey);

    // -------------------------------------------------------------- trail
    function renderTrail() {
      const ol = $('trail');
      if (!ol) return;
      ol.replaceChildren();
      const chain = [];
      for (let f = focusFrame; f >= 0 && layout; f = layout.frames[f].parent) chain.unshift(layout.frames[f]);
      const all = el('li', null, el('button', { type: 'button', class: 'crumb', 'aria-current': chain.length ? null : 'true', onclick: () => zoomToFrame(-1) }, 'All records'));
      ol.append(all);
      chain.forEach((f, q) => {
        if (!f.head && f.level === 0) return; // single dataset frame has no label strip
        ol.append(el('li', null, el('button', { type: 'button', class: 'crumb', 'aria-current': q === chain.length - 1 ? 'true' : null, onclick: () => zoomToFrame(f.i) }, f.label)));
      });
    }

    // -------------------------------------------------------------- search UI
    function runQuery() {
      if (!search) { result = null; return; }
      const t0 = now();
      result = state.query.trim() ? runSearch(search, state.query) : null;
      timings.searchMs = now() - t0;
    }
    let srActive = -1, srItems = [];
    function setQuery(q, source) {
      state.query = q;
      for (const id of ['graph-search', 'library-search']) { const inp = $(id); if (inp && inp !== source && inp.value !== q) inp.value = q; }
      runQuery();
      refreshStyles();
      commit(false);
      requestRender();
      renderCounts();
      if (state.view === 'graph' && model && model.nodes.length) {
        if (result && !result.count) showStageMessage('No records match “' + q + '”.', 'empty', { label: 'Clear search', run: () => setQuery('', null) }, 'query');
        else hideStageMessage('query');
      }
      if (state.view === 'library') { computeLibrary(); renderLibraryRows(); }
      if (source && source.id === 'graph-search') renderSearchResults();
    }
    function renderSearchResults() {
      const box = $('search-results'), input = $('graph-search');
      srActive = -1;
      if (!state.query.trim() || !model || doc.activeElement !== input) { box.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); return; }
      box.replaceChildren();
      srItems = result ? Array.from(result.indices.subarray(0, 8)) : [];
      if (!srItems.length) box.append(el('p', { class: 'sr-empty', text: 'No records match \u201C' + state.query + '\u201D.' }));
      srItems.forEach((i, q) => {
        const nd = model.nodes[i];
        const field = matchedFieldName(result, i);
        box.append(el('div', { class: 'sr-item', role: 'option', id: 'sr-' + q, 'aria-selected': 'false', data: { pos: String(q) } },
          el('span', { class: 'sr-title', text: nd.label }),
          el('span', { class: 'sr-meta', text: [model.datasets.length > 1 ? model.datasets[nd.d].label : null, nd.group || null, field !== 'name' ? 'Matched ' + field : null].filter(Boolean).join(' \u00B7 ') })));
      });
      if (result && result.count > srItems.length) box.append(el('button', { type: 'button', class: 'sr-more', onclick: () => { box.hidden = true; go('library', true); } }, 'Show all ' + fmt(result.count) + ' in the library'));
      box.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }
    function setSrActive(q) {
      const box = $('search-results'), input = $('graph-search');
      srActive = q;
      for (const item of box.querySelectorAll('.sr-item')) item.setAttribute('aria-selected', item.dataset.pos === String(q) ? 'true' : 'false');
      if (q >= 0) input.setAttribute('aria-activedescendant', 'sr-' + q); else input.removeAttribute('aria-activedescendant');
    }
    function chooseResult(q) {
      const i = srItems[q];
      if (i === undefined) return;
      $('search-results').hidden = true;
      $('graph-search').setAttribute('aria-expanded', 'false');
      select([model.nodes[i].uid], { push: true, reveal: true, zoom: true });
      (state.mode === 'city' ? $('canvas-3d') : cv).focus({ preventScroll: true });
    }
    {
      const input = $('graph-search');
      input.addEventListener('input', () => setQuery(input.value, input));
      input.addEventListener('focus', () => renderSearchResults());
      input.addEventListener('blur', () => setTimeout(() => { if (doc.activeElement !== input) { $('search-results').hidden = true; input.setAttribute('aria-expanded', 'false'); } }, 120));
      input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); if (srItems.length) setSrActive(Math.min(srItems.length - 1, srActive + 1)); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); if (srItems.length) setSrActive(Math.max(0, srActive - 1)); }
        else if (e.key === 'Enter') { e.preventDefault(); if (srItems.length) chooseResult(srActive >= 0 ? srActive : 0); }
        else if (e.key === 'Escape') {
          e.preventDefault(); e.stopPropagation();
          if (!$('search-results').hidden) { $('search-results').hidden = true; input.setAttribute('aria-expanded', 'false'); }
          else if (input.value) { input.value = ''; setQuery('', input); }
          else cv.focus({ preventScroll: true });
        }
      });
      $('search-results').addEventListener('mousedown', (e) => e.preventDefault());
      $('search-results').addEventListener('click', (e) => { const item = e.target.closest('.sr-item'); if (item) chooseResult(Number(item.dataset.pos)); });
      $('graph-search').closest('form').addEventListener('submit', (e) => e.preventDefault());
    }

    // -------------------------------------------------------------- counts, chips, legend, filters
    function renderCounts() {
      const box = $('graph-counts');
      if (!box) return;
      if (!model) { box.textContent = ''; return; }
      const parts = [plural(model.nodes.length, 'record'), plural(model.edges.length, 'connection')];
      if (result) parts.push(result.count ? fmt(result.count) + ' match' : 'No matches');
      const filters = state.hiddenKinds.size + state.hiddenTypes.size + state.hiddenEvidence.size;
      if (filters) parts.push(plural(filters, 'filter') + ' on');
      box.textContent = parts.join(' \u00B7 ');
      const warn = $('graph-warning');
      const skipped = model.datasets.reduce((a, d) => a + d.unresolvedEdges + d.invalidEdges, 0);
      const msgs = modelProblems.slice();
      msgs.push(...overlapWarnings(manifest.datasets, model.datasets.map((dataset) => dataset.id)));
      if (skipped) msgs.push(plural(skipped, 'connection') + (skipped === 1 ? ' is' : ' are') + ' not drawn because a source or target record is missing from its dataset.');
      for (const d of model.datasets) {
        if (d.missingNodes) msgs.push(d.label + ' has no records list.');
        if (d.rejectedUrls) msgs.push(d.label + ': ' + plural(d.rejectedUrls, 'link') + (d.rejectedUrls === 1 ? ' was' : ' were') + ' removed because ' + (pageIsFile() ? 'the address was not http, https or file.' : 'the address was not http or https. Local file links open only in a local copy.'));
      }
      warn.hidden = !msgs.length;
      warn.textContent = msgs.join(' ');
      const badge = $('filters-badge');
      badge.textContent = filters ? ' (' + filters + ')' : '';
    }
    function renderTitle() {
      const ids = orderedSelection(state.datasets);
      $('graph-title').textContent = ids.length === 1 ? metaById.get(ids[0]).label : ids.length ? fmt(ids.length) + ' datasets' : 'No dataset selected';
    }
    function renderChips() {
      const box = $('dataset-chips');
      box.replaceChildren();
      if (manifest.datasets.length < 2) { box.hidden = true; return; }
      box.hidden = false;
      for (const m of manifest.datasets) {
        const on = state.datasets.includes(m.id);
        const only = on && state.datasets.length === 1;
        box.append(el('button', {
          type: 'button', class: 'chip', 'aria-pressed': on ? 'true' : 'false', 'aria-disabled': only ? 'true' : null,
          title: only ? 'At least one dataset stays selected' : null,
          onclick: () => { if (only) return; toggleDataset(m.id, !on); }
        }, m.label));
      }
    }
    function toggleDataset(id, on) {
      const set = new Set(state.datasets);
      if (on) set.add(id); else set.delete(id);
      state.datasets = orderedSelection([...set]);
      commit(state.view !== 'home');
      if (state.view === 'home') { renderHome(); for (const d of state.datasets) loadDataset(metaById.get(d)); }
      else renderView();
    }

    function renderLegend() {
      const box = $('legend-body');
      if (!box || !model) return;
      box.replaceChildren();
      const city3 = state.mode === 'city';
      const swatches = el('ul', { class: 'legend-swatches' });
      if (state.colorBy === 'dataset') {
        model.datasets.forEach((d, q) => swatches.append(el('li', null, el('i', { class: 'sw', style: 'background:' + theme.palette[q % 8] }), d.label)));
      } else {
        model.kinds.slice(0, 8).forEach((kd, q) => swatches.append(el('li', null, el('i', { class: 'sw', style: 'background:' + theme.palette[q] }), (kd.name || 'Kind not recorded') + ' ', el('span', { class: 'muted', text: fmt(kd.count) }))));
        if (model.kinds.length > 8) {
          const rest = model.kinds.slice(8).reduce((a, kd) => a + kd.count, 0);
          swatches.append(el('li', null, el('i', { class: 'sw', style: 'background:' + theme.palette[8] }), 'Other kinds ', el('span', { class: 'muted', text: fmt(rest) })));
        }
      }
      box.append(
        el('p', { class: 'legend-h', text: state.colorBy === 'dataset' ? 'Colour: dataset' : 'Colour: record kind' }),
        swatches,
        el('p', { text: city3 ? 'Footprint: one equal share per record, the same as the treemap.' : 'Area: one equal share per record. Larger blocks hold more records.' }),
        el('p', { class: 'legend-lines' },
          el('span', null, el('i', { class: 'ln ln-observed' }), 'Observed'),
          el('span', null, el('i', { class: 'ln ln-inferred' }), 'Inferred comparison'),
          model.evidenceCounts.unstated ? el('span', null, el('i', { class: 'ln ln-unstated' }), 'Evidence not stated') : null)
      );
      if (city3) {
        box.append(el('p', { text: state.height === 'flat' ? 'Height: none. All records are flat.' : model.maxDegree ? 'Height: connections per record in the loaded data, 0 to ' + fmt(model.maxDegree) + ', linear. Height does not measure value.' : 'Height: no record has connections in the loaded data.' }));
      }
      if (!city3 && state.mode === 'graph' && v2.truncated) box.append(el('p', { class: 'warn', text: 'Showing the first ' + fmt(EDGE_DRAW_BUDGET) + ' connections in view. Zoom in or select a record to see the rest.' }));
    }

    function renderFilters() {
      const kinds = $('filter-kinds'), types = $('filter-types'), evid = $('filter-evidence');
      if (!model) return;
      const box = (list, set, items, labelFor) => {
        list.replaceChildren();
        if (!items.length) { list.append(el('p', { class: 'muted', text: 'None in the loaded data.' })); return; }
        for (const it of items) {
          const id = list.id + '-' + list.childElementCount;
          list.append(el('label', { class: 'check', for: id },
            el('input', { type: 'checkbox', id, checked: !set.has(it.name), data: { value: it.name } }),
            el('span', { text: labelFor(it.name) }), el('span', { class: 'muted', text: fmt(it.count) })));
        }
      };
      box(kinds, state.hiddenKinds, model.kinds, (s) => s || 'Kind not recorded');
      box(types, state.hiddenTypes, model.edgeTypes, (s) => s);
      box(evid, state.hiddenEvidence, EV.map((e) => ({ name: e, count: model.evidenceCounts[e] })).filter((x) => x.count || x.name !== 'unstated'), (s) => EV_LABEL[s]);
      for (const r of doc.querySelectorAll('input[name="colorBy"]')) r.checked = r.value === state.colorBy;
      for (const r of doc.querySelectorAll('input[name="height"]')) r.checked = r.value === state.height;
    }
    function bindFilterList(id, set) {
      $(id).addEventListener('change', (e) => {
        const inp = e.target;
        if (!inp.dataset || inp.dataset.value === undefined) return;
        if (inp.checked) set.delete(inp.dataset.value); else set.add(inp.dataset.value);
        refreshStyles(); requestRender(); renderCounts();
      });
    }
    bindFilterList('filter-kinds', state.hiddenKinds);
    bindFilterList('filter-types', state.hiddenTypes);
    bindFilterList('filter-evidence', state.hiddenEvidence);
    $('filters').addEventListener('change', (e) => {
      const t = e.target;
      if (t.name === 'colorBy') { state.colorBy = t.value; assignColors(); refreshStyles(); renderLegend(); requestRender(); }
      if (t.name === 'height') { state.height = t.value; if (city && cityKey) { city.setHeights(cityHeights()); cityKey = modelKey + '|' + state.height; city.setLinks(cityLinks()); } renderLegend(); }
    });
    $('filters-reset').addEventListener('click', () => {
      state.hiddenKinds.clear(); state.hiddenTypes.clear(); state.hiddenEvidence.clear();
      state.colorBy = 'kind';
      if (state.height !== 'connections') { state.height = 'connections'; if (city && cityKey) { city.setHeights(cityHeights()); cityKey = modelKey + '|' + state.height; } }
      assignColors(); refreshStyles(); renderFilters(); renderLegend(); renderCounts(); requestRender();
    });
    function openFilters(open) {
      const pop = $('filters'), btn = $('filters-open');
      if (open) { renderFilters(); pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); const first = pop.querySelector('input,button'); if (first) first.focus({ preventScroll: true }); }
      else if (!pop.hidden) { pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.focus({ preventScroll: true }); }
    }
    $('filters-open').addEventListener('click', () => openFilters($('filters').hidden));
    $('filters-close').addEventListener('click', () => openFilters(false));
    doc.addEventListener('pointerdown', (e) => {
      const pop = $('filters');
      if (!pop.hidden && !pop.contains(e.target) && !$('filters-open').contains(e.target)) { pop.hidden = true; $('filters-open').setAttribute('aria-expanded', 'false'); }
    });

    // -------------------------------------------------------------- record details
    const detailCache = new Map();
    function renderInspector() {
      const aside = $('inspector');
      if (!aside) return;
      const has = model && state.selected.length > 0;
      aside.hidden = !has;
      $('graph-shell').classList.toggle('has-inspector', !!has);
      if (has) renderRecord($('inspector-body'), 'graph');
      if (state.view === 'graph') { resize2d(); if (city && state.mode === 'city') city.resize(); }
    }
    function renderLibraryDetail() {
      const box = $('library-detail');
      if (!box || !model) return;
      renderRecord(box, 'library');
      box.classList.toggle('has-record', state.selected.length > 0);
    }

    function factRow(dl, term, value) {
      dl.append(el('dt', { text: term }), el('dd', null, value == null || value === '' ? el('span', { class: 'missing', text: 'Not recorded' }) : value));
    }

    function renderRecord(container, context) {
      const t0 = now();
      container.replaceChildren();
      const sel = state.selected.map((u) => model.byUid.get(u)).filter(Boolean);
      if (!sel.length) {
        container.append(el('div', { class: 'record-empty' }, el('p', { text: context === 'library' ? 'Select a record to see its details, connections and sources.' : 'Select a record to see its connections and sources.' })));
        return;
      }
      const node = sel[sel.length - 1];
      const ds = model.datasets[node.d];
      const bar = el('div', { class: 'record-bar' });
      if (canGoBack()) bar.append(el('button', { type: 'button', class: 'button button-quiet', onclick: () => history.back() }, el('span', { class: 'arrow-back', 'aria-hidden': 'true' }), 'Back'));
      bar.append(el('span', { class: 'spacer' }));
      bar.append(el('button', { type: 'button', class: 'icon-button', 'aria-label': 'Close record details', onclick: () => select([], { push: true }) }, '\u00D7'));
      container.append(bar);

      if (sel.length > 1) {
        const chips = el('div', { class: 'record-multi', role: 'group', 'aria-label': 'Selected records' }, el('span', { class: 'muted', text: fmt(sel.length) + ' selected' }));
        for (const s of sel) {
          chips.append(el('button', {
            type: 'button', class: 'chip', 'aria-pressed': s === node ? 'true' : 'false',
            onclick: () => select(state.selected.filter((u) => u !== s.uid).concat(s.uid), { push: false })
          }, s.label));
        }
        container.append(chips);
      }

      container.append(el('h2', { class: 'record-title', text: node.label }));
      const where = [node.group || 'No group recorded', node.subgroup].filter(Boolean).join(' \u203A ');
      container.append(el('p', { class: 'record-meta' }, [node.kind || 'Kind not recorded', where, ds.label].join(' \u00B7 ')));
      container.append(node.description ? el('p', { class: 'record-desc', text: node.description }) : el('p', { class: 'record-desc missing', text: 'No description recorded.' }));

      const actions = el('div', { class: 'record-actions' });
      if (node.sourceUrl) actions.append(extLink(node.sourceUrl, 'Source: ' + hostOf(node.sourceUrl), 'button button-primary'));
      if (context === 'graph') actions.append(el('button', { type: 'button', class: 'button', onclick: () => go('library', true) }, 'Open in library'));
      else actions.append(el('button', { type: 'button', class: 'button', onclick: () => { go('graph', true); } }, 'Show in graph'));
      container.append(actions);

      const facts = el('dl', { class: 'facts' });
      factRow(facts, 'Author', node.author);
      factRow(facts, 'Date', node.date);
      factRow(facts, 'Status', node.status);
      factRow(facts, 'Record ID', el('code', { text: node.id }));
      if (!node.sourceUrl) factRow(facts, 'Source', node.sourceRejected ? el('span', { class: 'missing', text: pageIsFile() ? 'Link removed because it did not use http, https or file.' : 'Link removed because it did not use http or https.' }) : null);
      container.append(facts);

      if (node.metrics && Object.keys(node.metrics).length) {
        const sec = el('section', { class: 'record-section' }, el('h3', { text: 'Recorded values' }), el('p', { class: 'muted small', text: 'As recorded by the source. Units vary, so compare values only when they share a unit.' }));
        const dl = el('dl', { class: 'facts' });
        for (const key of Object.keys(node.metrics).slice(0, 60)) dl.append(el('dt', { text: text(key, 120) }), el('dd', null, metricValue(node.metrics[key])));
        sec.append(dl);
        container.append(sec);
      }

      container.append(renderConnections(node));
      if (node.detailUrl) container.append(renderEvidence(node));
      timings.inspectorMs = now() - t0;
    }

    function metricValue(v) {
      if (v == null) return el('span', { class: 'missing', text: 'Not recorded' });
      if (typeof v !== 'object') return text(v, 400);
      if (Array.isArray(v)) return text(v.map((x) => (typeof x === 'object' ? JSON.stringify(x) : String(x))).join(', '), 400);
      if ('value' in v) {
        const parts = metricText(v);
        const extra = [text(v.date || v.asOf, 40), text(v.basis || v.note, 300)].filter(Boolean).join(' \u00B7 ');
        const url = safeUrl(v.sourceUrl || v.url);
        return [parts || 'Not recorded', extra ? el('span', { class: 'muted', text: ' ' + extra }) : null, url ? [' ', extLink(url, hostOf(url))] : null];
      }
      return text(JSON.stringify(v), 400);
    }

    function renderConnections(node) {
      const sec = el('section', { class: 'record-section' });
      const p = node.i, E = model.edges;
      const total = model.adjStart[p + 1] - model.adjStart[p];
      if (!total) {
        sec.append(el('h3', { text: 'Connections' }), el('p', { class: 'muted', text: 'No connections are recorded for this record in its dataset.' }));
        return sec;
      }
      const counts = { observed: 0, inferred: 0, unstated: 0 };
      const groups = new Map();
      for (let q = model.adjStart[p]; q < model.adjStart[p + 1]; q++) {
        const e = model.adj[q], ed = E[e];
        counts[ed.evidence]++;
        const dir = !ed.directed ? 'with' : ed.s === p ? 'to' : 'from';
        const key = ed.type + '\u0001' + dir;
        let g = groups.get(key);
        if (!g) groups.set(key, (g = { type: ed.type, dir, list: [] }));
        g.list.push(e);
      }
      const present = EV.filter((ev) => counts[ev]);
      const summary = present.length === 1
        ? plural(total, 'connection') + (present[0] === 'unstated' ? ', evidence not stated.' : ', all ' + EV_LABEL[present[0]].toLowerCase() + '.')
        : plural(total, 'connection') + ': ' + present.map((ev) => fmt(counts[ev]) + ' ' + EV_LABEL[ev].toLowerCase()).join(', ') + '.';
      sec.append(el('h3', { text: 'Connections' }), el('p', { class: 'muted small', text: summary }));
      const dirLabel = { to: 'Points to', from: 'Pointed to by', with: 'Linked with' };
      const sorted = [...groups.values()].sort((a, b) => b.list.length - a.list.length || (a.type < b.type ? -1 : 1));
      for (const g of sorted) {
        g.list.sort((a, b) => (E[a].evidence === 'observed' ? 0 : 1) - (E[b].evidence === 'observed' ? 0 : 1) || (model.nodes[other(E[a], p)].label < model.nodes[other(E[b], p)].label ? -1 : 1));
        const ul = el('ul', { class: 'conn-list' });
        const det = el('details', { class: 'conn-group', open: sorted.length <= 4 ? true : null },
          el('summary', null, el('span', { text: g.type }), el('span', { class: 'muted', text: ' ' + dirLabel[g.dir] + ' \u00B7 ' + fmt(g.list.length) })), ul);
        let shown = 0;
        const more = el('button', { type: 'button', class: 'button button-quiet small' });
        const addMore = () => {
          const next = Math.min(g.list.length, shown + 30);
          for (; shown < next; shown++) ul.append(connRow(g.list[shown], p));
          if (shown < g.list.length) { more.textContent = 'Show ' + fmt(Math.min(30, g.list.length - shown)) + ' more of ' + fmt(g.list.length - shown); ul.after(more); }
          else more.remove();
        };
        more.addEventListener('click', addMore);
        addMore();
        sec.append(det);
      }
      return sec;
    }
    function other(ed, p) { return ed.s === p ? ed.t : ed.s; }
    function connRow(e, p) {
      const ed = model.edges[e], nb = model.nodes[other(ed, p)];
      return el('li', { class: 'conn' },
        el('div', { class: 'conn-head' },
          el('button', { type: 'button', class: 'link-button', data: { uid: nb.uid } }, nb.label),
          el('span', { class: 'badge badge-' + ed.evidence, text: EV_LABEL[ed.evidence] })),
        ed.basis ? el('p', { class: 'conn-basis', text: ed.basis }) : el('p', { class: 'conn-basis missing', text: 'No basis recorded.' }),
        ed.sourceUrl ? el('p', { class: 'conn-source' }, extLink(ed.sourceUrl, hostOf(ed.sourceUrl))) : el('p', { class: 'conn-source missing', text: 'No source link recorded.' }));
    }
    for (const id of ['inspector-body', 'library-detail']) {
      $(id).addEventListener('click', (e) => {
        const b = e.target.closest('button[data-uid]');
        if (!b) return;
        const uid = b.dataset.uid;
        select([uid], { push: true, reveal: state.view === 'graph' });
        if (state.view === 'library') revealInLibrary(uid);
      });
    }

    function renderEvidence(node) {
      const sec = el('section', { class: 'record-section', 'aria-live': 'polite' }, el('h3', { text: 'Source evidence' }));
      const body = el('div', { class: 'evidence' });
      sec.append(body);
      const url = node.detailUrl;
      const show = (entry) => {
        body.replaceChildren();
        if (entry.status === 'loading') { body.append(el('p', { class: 'muted', text: 'Loading source evidence\u2026' })); return; }
        if (entry.status === 'error') { body.append(el('p', { class: 'missing', text: 'The full source evidence could not load. ' + entry.error })); return; }
        const ev = evidenceFor(entry.data, node.id);
        if (!ev.found || ev.value == null || ev.value === '') {
          const mismatch = ev.datasetId && ev.datasetId !== node.ds && ev.datasetId !== model.datasets[node.d].idMismatch;
          body.append(el('p', { class: 'missing', text: mismatch
            ? 'The evidence file belongs to the dataset \u201c' + ev.datasetId + '\u201d, so it has no entry for this record.'
            : 'The evidence file has no entry for this record (ID ' + node.id + ')' + (node.sourceUrl ? '. The source link above is the recorded evidence.' : ', and no source link is recorded.') }));
          return;
        }
        body.append(renderDetailValue(ev.value, 0));
      };
      const entry = evidenceEntry(detailCache, url, (address) => fetch(address, { credentials: 'same-origin' })
        .then((response) => { if (!response.ok) throw new Error('HTTP ' + response.status + '.'); return response.json(); }));
      watchEvidence(entry, body, show);
      return sec;
    }

    const isCitation = (v) => v && typeof v === 'object' && !Array.isArray(v) && (v.url || v.sourceUrl || v.href) && (v.title || v.label || v.name || v.quote || v.excerpt);
    function renderCitation(v) {
      const url = safeUrl(v.url || v.sourceUrl || v.href);
      const name = text(v.title || v.label || v.name, 400) || (url ? hostOf(url) : 'Source');
      const meta = [text(v.publisher || v.site || v.author, 200), text(v.date || v.published || v.accessed, 60)].filter(Boolean).join(' \u00B7 ');
      const quote = text(v.quote || v.excerpt || v.text, 4000);
      return el('div', { class: 'citation' },
        url ? extLink(url, name) : el('span', { text: name }),
        meta ? el('p', { class: 'muted small', text: meta }) : null,
        quote ? el('blockquote', { text: quote }) : null);
    }
    function renderDetailValue(v, depth) {
      if (v == null || v === '') return el('span', { class: 'missing', text: 'Not recorded' });
      if (typeof v === 'string') {
        const url = /^(https?|file):\/\//i.test(v.trim()) ? safeUrl(v) : null;
        return url ? extLink(url, hostOf(url)) : el('span', { class: 'prewrap', text: text(v, 8000) });
      }
      if (typeof v !== 'object') return el('span', { text: text(v, 200) });
      if (depth > 4) return el('code', { text: text(JSON.stringify(v), 600) });
      if (Array.isArray(v)) {
        const ul = el('ul', { class: 'detail-list' });
        v.slice(0, 200).forEach((item) => ul.append(el('li', null, isCitation(item) ? renderCitation(item) : renderDetailValue(item, depth + 1))));
        if (v.length > 200) ul.append(el('li', { class: 'muted', text: fmt(v.length - 200) + ' more entries are in the source file.' }));
        return ul;
      }
      if (isCitation(v)) return renderCitation(v);
      const dl = el('dl', { class: 'facts detail' });
      for (const key of Object.keys(v).slice(0, 80)) dl.append(el('dt', { text: text(key, 120) }), el('dd', null, renderDetailValue(v[key], depth + 1)));
      return dl;
    }

    // -------------------------------------------------------------- library
    const lib = { items: new Int32Array(0), active: -1, rows: [], rowH: 60, raf: 0 };
    const collator = new Intl.Collator('en', { sensitivity: 'base', numeric: true });
    function populateLibraryFilters() {
      const dsSel = $('library-dataset'), kindSel = $('library-kind');
      const keepDs = dsSel.value, keepKind = kindSel.value;
      dsSel.replaceChildren(el('option', { value: '', text: 'All datasets' }));
      model.datasets.forEach((d, q) => dsSel.append(el('option', { value: String(q), text: d.label + ' (' + fmt(d.nodeEnd - d.nodeStart) + ')' })));
      dsSel.value = [...dsSel.options].some((o) => o.value === keepDs) ? keepDs : '';
      dsSel.closest('label').hidden = model.datasets.length < 2;
      kindSel.replaceChildren(el('option', { value: '', text: 'All kinds' }));
      model.kinds.slice(0, 200).forEach((kd) => kindSel.append(el('option', { value: kd.name ? 'k:' + kd.name : 'none', text: (kd.name || 'Kind not recorded') + ' (' + fmt(kd.count) + ')' })));
      kindSel.value = [...kindSel.options].some((o) => o.value === keepKind) ? keepKind : '';
    }
    function computeLibrary() {
      if (!model) { lib.items = new Int32Array(0); return; }
      const dsVal = $('library-dataset').value, kindVal = $('library-kind').value, sort = $('library-sort').value;
      const kindOn = kindVal !== '';
      const kindWanted = kindVal === 'none' ? '' : kindVal.slice(2);
      const base = result ? result.indices : layout.order;
      const out = [];
      for (let q = 0; q < base.length; q++) {
        const i = base[q], nd = model.nodes[i];
        if (dsVal !== '' && nd.d !== Number(dsVal)) continue;
        if (kindOn && nd.kind !== kindWanted) continue;
        out.push(i);
      }
      if (sort === 'name') out.sort((a, b) => collator.compare(model.nodes[a].label, model.nodes[b].label));
      else if (sort === 'connections') out.sort((a, b) => model.degree[b] - model.degree[a] || a - b);
      else if (sort === 'date') out.sort((a, b) => { const da = model.nodes[a].date, db = model.nodes[b].date; if (!da !== !db) return da ? -1 : 1; return da < db ? 1 : da > db ? -1 : a - b; });
      else if (sort === 'map' && result) { const pos = new Int32Array(model.nodes.length); layout.order.forEach((i, q) => { pos[i] = q; }); out.sort((a, b) => pos[a] - pos[b]); }
      lib.items = Int32Array.from(out);
      lib.active = -1;
      const counts = $('library-counts');
      const total = model.nodes.length;
      if (!total) counts.textContent = 'No records in the selected datasets.';
      else if (result) counts.textContent = out.length ? fmt(out.length) + ' of ' + plural(total, 'record') + ' match \u201C' + state.query + '\u201D' : 'No records match \u201C' + state.query + '\u201D';
      else counts.textContent = out.length === total ? plural(total, 'record') : fmt(out.length) + ' of ' + plural(total, 'record');
      $('library-empty').hidden = out.length > 0;
      $('library-empty-text').textContent = !total ? 'The selected datasets have no records.' : result ? 'No records match \u201C' + state.query + '\u201D.' : 'No records match these filters.';
      $('library-clear').hidden = !(result || dsVal !== '' || kindOn);
    }
    function metaLine(nd) {
      return [model.datasets.length > 1 ? model.datasets[nd.d].label : null, [nd.group, nd.subgroup].filter(Boolean).join(' \u203A ') || null, nd.kind || null, nd.date || null].filter(Boolean).join(' \u00B7 ');
    }
    function renderLibraryRows() {
      if (!model) return;
      const t0 = now();
      const list = $('library-list'), spacer = $('library-spacer');
      const N = lib.items.length, H = lib.rowH;
      spacer.style.height = N * H + 'px';
      const top = list.scrollTop, vh = list.clientHeight || 640;
      const start = Math.max(0, Math.floor(top / H) - 4), end = Math.min(N, Math.ceil((top + vh) / H) + 4);
      const need = Math.max(0, end - start);
      while (lib.rows.length < need) {
        const row = el('div', { class: 'lib-row', role: 'option' }, el('span', { class: 'lib-title' }), el('span', { class: 'lib-meta' }), el('span', { class: 'lib-count' }));
        spacer.append(row);
        lib.rows.push(row);
      }
      const selected = new Set(state.selected);
      for (let r = 0; r < lib.rows.length; r++) {
        const row = lib.rows[r];
        if (r >= need) { row.hidden = true; row.removeAttribute('id'); continue; }
        const pos = start + r, i = lib.items[pos], nd = model.nodes[i];
        row.hidden = false;
        row.id = 'lib-opt-' + pos;
        row.dataset.pos = String(pos);
        row.style.transform = 'translateY(' + pos * H + 'px)';
        row.setAttribute('aria-posinset', String(pos + 1));
        row.setAttribute('aria-setsize', String(N));
        row.setAttribute('aria-selected', selected.has(nd.uid) ? 'true' : 'false');
        row.classList.toggle('is-active', pos === lib.active);
        row.children[0].textContent = nd.label;
        row.children[1].textContent = metaLine(nd);
        const deg = model.degree[i];
        row.children[2].textContent = deg ? fmt(deg) : '';
        row.children[2].title = plural(deg, 'connection');
      }
      if (lib.active >= start && lib.active < end) list.setAttribute('aria-activedescendant', 'lib-opt-' + lib.active);
      else list.removeAttribute('aria-activedescendant');
      timings.libraryRenderMs = now() - t0;
      timings.libraryRows = need;
    }
    function setLibActive(pos, selectIt) {
      const N = lib.items.length;
      if (!N) return;
      pos = clamp(pos, 0, N - 1);
      lib.active = pos;
      const list = $('library-list'), H = lib.rowH;
      if (pos * H < list.scrollTop) list.scrollTop = pos * H;
      else if ((pos + 1) * H > list.scrollTop + list.clientHeight) list.scrollTop = (pos + 1) * H - list.clientHeight;
      if (selectIt) select([model.nodes[lib.items[pos]].uid], { push: false });
      renderLibraryRows();
    }
    function revealInLibrary(uid) {
      const nd = model.byUid.get(uid);
      if (!nd) return;
      const pos = lib.items.indexOf(nd.i);
      if (pos >= 0) setLibActive(pos, false);
    }
    {
      const list = $('library-list');
      list.addEventListener('scroll', () => { if (!lib.raf) lib.raf = requestAnimationFrame(() => { lib.raf = 0; renderLibraryRows(); }); }, { passive: true });
      list.addEventListener('click', (e) => {
        const row = e.target.closest('.lib-row');
        if (!row) return;
        const pos = Number(row.dataset.pos);
        lib.active = pos;
        select([model.nodes[lib.items[pos]].uid], { push: true });
      });
      list.addEventListener('keydown', (e) => {
        const page = Math.max(1, Math.floor(list.clientHeight / lib.rowH) - 1);
        const map = { ArrowDown: 1, ArrowUp: -1, PageDown: page, PageUp: -page };
        if (map[e.key] !== undefined) { e.preventDefault(); setLibActive((lib.active < 0 ? -1 : lib.active) + map[e.key], true); }
        else if (e.key === 'Home') { e.preventDefault(); setLibActive(0, true); }
        else if (e.key === 'End') { e.preventDefault(); setLibActive(lib.items.length - 1, true); }
        else if (e.key === 'Enter' && lib.active >= 0) { e.preventDefault(); select([model.nodes[lib.items[lib.active]].uid], { push: true }); }
      });
      list.addEventListener('focus', () => { if (lib.active < 0 && lib.items.length) { lib.active = Math.floor(list.scrollTop / lib.rowH); renderLibraryRows(); } });
      const relist = () => { computeLibrary(); list.scrollTop = 0; renderLibraryRows(); };
      $('library-dataset').addEventListener('change', relist);
      $('library-kind').addEventListener('change', relist);
      $('library-sort').addEventListener('change', relist);
      const input = $('library-search');
      input.addEventListener('input', () => { setQuery(input.value, input); list.scrollTop = 0; renderLibraryRows(); });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') { e.preventDefault(); list.focus(); setLibActive(0, true); }
        else if (e.key === 'Escape' && input.value) { e.preventDefault(); e.stopPropagation(); input.value = ''; setQuery('', input); renderLibraryRows(); }
      });
      $('library-clear').addEventListener('click', () => {
        $('library-dataset').value = ''; $('library-kind').value = '';
        input.value = ''; setQuery('', input); relist();
      });
      input.closest('form').addEventListener('submit', (e) => e.preventDefault());
    }

    // -------------------------------------------------------------- home
    function renderHome() {
      const list = $('dataset-list');
      list.replaceChildren();
      if (!manifest.datasets.length) {
        list.append(el('p', { class: 'empty', text: 'No datasets are published in the dataset list yet.' }));
      }
      manifest.datasets.forEach((m, q) => {
        const on = state.datasets.includes(m.id);
        const id = 'ds-check-' + q;
        const c = cache.get(m.id);
        const meta = [
          m.nodeCount != null ? plural(m.nodeCount, 'record') : 'Record count not listed',
          m.edgeCount != null ? plural(m.edgeCount, 'connection') : 'Connection count not listed',
          preparedLabel(m.updatedAt)
        ].join(' \u00B7 ');
        const status = c ? (c.status === 'loading' ? el('span', { class: 'tag', text: 'Loading' }) : c.status === 'error' ? el('span', { class: 'tag tag-error', text: 'Unavailable' }) : el('span', { class: 'tag tag-ok', text: 'Loaded' })) : null;
        list.append(el('div', { class: 'dataset' + (on ? ' is-selected' : ''), data: { ds: m.id } },
          el('input', { type: 'checkbox', id, checked: on, data: { ds: m.id } }),
          el('div', { class: 'dataset-body' },
            el('div', { class: 'dataset-top' }, el('label', { for: id, class: 'dataset-name', text: m.label }), status),
            m.description ? el('p', { class: 'dataset-desc', text: m.description }) : el('p', { class: 'dataset-desc missing', text: 'No description listed.' }),
            el('p', { class: 'dataset-meta', title: m.updatedAt || null }, meta, m.sourceUrl ? [' \u00B7 ', extLink(m.sourceUrl, 'Source')] : null),
            c && c.status === 'error' ? el('p', { class: 'dataset-error', text: 'Could not load: ' + c.error }) : null)));
      });
      const ids = orderedSelection(state.datasets);
      const sum = (key) => ids.reduce((a, id) => (a === null || metaById.get(id)[key] == null ? null : a + metaById.get(id)[key]), 0);
      const nodes = sum('nodeCount'), edges = sum('edgeCount');
      $('home-summary').textContent = !ids.length ? 'Select at least one dataset.' :
        plural(ids.length, 'dataset') + ' selected' + (nodes != null ? ' \u00B7 ' + plural(nodes, 'record') : '') + (edges != null ? ' \u00B7 ' + plural(edges, 'connection') : '') + '. Connections never cross datasets.';
      $('home-open-graph').disabled = !ids.length;
      $('home-open-library').disabled = !ids.length;
      if (manifest.skipped) showHomeStatus(plural(manifest.skipped, 'dataset entry', 'dataset entries') + ' in the dataset list had no usable ID or address and are not shown.', 'warn');
    }
    function showHomeStatus(msg, kind) {
      const box = $('home-status');
      box.textContent = msg; box.className = 'status is-' + kind; box.hidden = false;
    }
    $('dataset-list').addEventListener('change', (e) => {
      const t = e.target;
      if (t.type === 'checkbox' && t.dataset.ds) toggleDataset(t.dataset.ds, t.checked);
    });
    $('dataset-list').addEventListener('click', (e) => {
      if (e.target.closest('a,input,label')) return;
      const card = e.target.closest('.dataset');
      if (!card) return;
      const box = card.querySelector('input[type="checkbox"]');
      box.checked = !box.checked;
      toggleDataset(card.dataset.ds, box.checked);
    });
    $('home-open-graph').addEventListener('click', () => go('graph', true));
    $('home-open-library').addEventListener('click', () => go('library', true));

    // -------------------------------------------------------------- views
    let viewToken = 0;
    function go(view, push) {
      state.view = view;
      commit(push);
      renderView();
    }
    async function renderView() {
      const token = ++viewToken;
      for (const v of ['home', 'graph', 'library']) $('view-' + v).hidden = state.view !== v;
      for (const a of doc.querySelectorAll('[data-nav]')) {
        if (a.dataset.nav === state.view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
      }
      doc.body.dataset.view = state.view;
      for (const b of doc.querySelectorAll('[data-mode]')) b.setAttribute('aria-pressed', b.dataset.mode === state.mode ? 'true' : 'false');
      for (const id of ['graph-search', 'library-search']) { const inp = $(id); if (inp.value !== state.query) inp.value = state.query; }
      if (state.view === 'home') { renderHome(); return; }
      if (state.view === 'graph') { renderTitle(); renderChips(); }
      const ok = await ensureModel();
      if (!ok || token !== viewToken) return;
      if (state.view === 'graph') {
        renderTitle(); renderChips(); renderCounts(); renderTrail(); renderInspector();
        if (state.mode === 'city') activateCity(); else activate2D();
        if (!model.nodes.length) {
          showStageMessage(!orderedSelection(state.datasets).length ? 'No dataset is selected.' : modelProblems.length ? modelProblems.join(' ') : 'The selected datasets have no records.', modelProblems.length ? 'error' : 'empty', { label: 'Choose datasets', run: () => go('home', true) }, 'model');
        } else if (result && !result.count) {
          showStageMessage('No records match “' + state.query + '”.', 'empty', { label: 'Clear search', run: () => setQuery('', null) }, 'query');
        }
        renderLegend();
        if (state.selected.length) revealRecord(selIdx[selIdx.length - 1], false);
      } else {
        populateLibraryFilters();
        computeLibrary();
        renderLibraryRows();
        renderLibraryDetail();
        if (state.selected.length) revealInLibrary(state.selected[state.selected.length - 1]);
      }
    }
    function setMode(mode, push) {
      if (!MODES.includes(mode) || mode === state.mode) return;
      state.mode = mode;
      commit(push);
      for (const b of doc.querySelectorAll('[data-mode]')) b.setAttribute('aria-pressed', b.dataset.mode === mode ? 'true' : 'false');
      showHover(-1);
      if (state.view !== 'graph' || !model) return;
      if (mode === 'city') activateCity();
      else activate2D();
      renderLegend();
    }
    for (const b of doc.querySelectorAll('[data-mode]')) b.addEventListener('click', () => setMode(b.dataset.mode, true));
    for (const a of doc.querySelectorAll('[data-nav]')) {
      a.addEventListener('click', (e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        if (state.view !== a.dataset.nav) go(a.dataset.nav, true);
      });
    }
    $('zoom-in').addEventListener('click', () => zoomBy(1.5));
    $('zoom-out').addEventListener('click', () => zoomBy(1 / 1.5));
    $('zoom-fit').addEventListener('click', () => zoomToFrame(-1));
    $('theme-toggle').addEventListener('click', () => setTheme(doc.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true));

    root.addEventListener('popstate', (e) => {
      histDepth = e.state && e.state.explorer ? e.state.depth || 0 : 0;
      const r = parseHash();
      applyRoute(r);
      if (r.legacy) commit(false); // rewrite #sectors and similar to the canonical route
    });
    function applyRoute(r) {
      state.view = r.view;
      if (r.mode) state.mode = r.mode;
      if (r.datasets) { const valid = orderedSelection(r.datasets); if (valid.length || !r.datasets.length) state.datasets = valid; }
      state.selected = r.selected;
      if (state.query !== r.query) { state.query = r.query; runQuery(); }
      if (model) refreshStyles();
      renderView();
      if (model) { requestRender(); if (state.view === 'graph') renderCounts(); }
    }

    doc.addEventListener('keydown', (e) => {
      const t = e.target;
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey && state.view !== 'home') {
        e.preventDefault();
        $(state.view === 'library' ? 'library-search' : 'graph-search').focus();
        return;
      }
      if (e.key === 'Escape') {
        if (!$('filters').hidden) { e.preventDefault(); openFilters(false); return; }
        const help = doc.querySelector('details.help[open]');
        if (help) { e.preventDefault(); help.open = false; help.querySelector('summary').focus(); return; }
        if (state.selected.length && state.view !== 'home') { e.preventDefault(); select([], { push: true }); return; }
      }
      if (!typing && state.view === 'graph' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const m = { 1: 'graph', 2: 'treemap', 3: 'city' }[e.key];
        if (m) { e.preventDefault(); setMode(m, true); }
      }
    });

    narrow.addEventListener && narrow.addEventListener('change', () => { resize2d(); });
    if (root.ResizeObserver) new ResizeObserver(() => { if (state.view === 'graph') { resize2d(); if (city && state.mode === 'city') city.resize(); } }).observe($('stage'));
    else root.addEventListener('resize', () => { resize2d(); if (city) city.resize(); });

    // -------------------------------------------------------------- debug surface (read-only)
    const rectOf = (i) => { const o = i * 4, R = layout.rects; return { x: R[o], y: R[o + 1], w: R[o + 2], h: R[o + 3] }; };
    root.explorerDebug = Object.freeze({
      version: VERSION,
      get view() { return state.view; },
      get mode() { return state.mode; },
      get datasets() { return orderedSelection(state.datasets); },
      get selectedIds() { return state.selected.slice(); },
      get query() { return state.query; },
      get nodeCount() { return model ? model.nodes.length : 0; },
      get edgeCount() { return model ? model.edges.length : 0; },
      get matchCount() { return result ? result.count : null; },
      get crossDatasetEdges() { return model ? model.crossDataset : 0; },
      get layoutHash() { return layout ? layout.hash : null; },
      get world() { return layout ? { width: layout.W, height: layout.H } : null; },
      get camera2d() { return { k: v2.k, tx: v2.tx, ty: v2.ty, fitK: v2.fitK }; },
      get cityCamera() { return city ? city.camera() : null; },
      get cityState() { return city ? 'ready' : cityUnavailable ? 'unavailable' : cityLoading ? 'loading' : 'not loaded'; },
      get domElements() { return doc.getElementsByTagName('*').length; },
      get timings() { return JSON.parse(JSON.stringify(timings)); },
      datasetReports() {
        return model ? model.datasets.map((d) => ({
          id: d.id, label: d.label, records: d.nodeEnd - d.nodeStart, connections: d.edgeCount, unresolvedEdges: d.unresolvedEdges,
          invalidEdges: d.invalidEdges, invalidNodes: d.invalidNodes, duplicateNodes: d.duplicateNodes, duplicateEdges: d.duplicateEdges,
          selfLoops: d.selfLoops, rejectedUrls: d.rejectedUrls, missingNodes: d.missingNodes, idMismatch: d.idMismatch
        })) : [];
      },
      layout(uid) { const nd = model && model.byUid.get(uid); return nd ? rectOf(nd.i) : null; },
      layoutAll(limit) {
        if (!model) return [];
        const n = Math.min(model.nodes.length, limit == null ? model.nodes.length : limit);
        const out = new Array(n);
        for (let i = 0; i < n; i++) out[i] = Object.assign({ id: model.nodes[i].uid }, rectOf(i));
        return out;
      },
      frames() { return layout ? layout.frames.map((f) => ({ level: f.level, label: f.label, x: f.x, y: f.y, w: f.w, h: f.h, count: f.count })) : []; },
      edges(limit) {
        if (!model) return [];
        return model.edges.slice(0, limit == null ? 1000 : limit).map((e) => ({ source: model.nodes[e.s].uid, target: model.nodes[e.t].uid, type: e.type, evidence: e.evidence, directed: e.directed, dataset: model.datasets[e.d].id }));
      },
      neighbors(uid) {
        const nd = model && model.byUid.get(uid);
        if (!nd) return [];
        const out = [];
        for (let p = model.adjStart[nd.i]; p < model.adjStart[nd.i + 1]; p++) out.push(model.nodes[other(model.edges[model.adj[p]], nd.i)].uid);
        return out;
      },
      cityFootprints(limit) { return city ? city.footprints(limit) : null; },
      compareCityFootprints() {
        if (!city || !layout) return null;
        const fp = city.footprintBuffer();
        if (!fp) return null;
        let mismatches = 0;
        const R = layout.rects;
        if (fp.length !== R.length) return { checked: 0, mismatches: -1 };
        for (let q = 0; q < R.length; q++) if (fp[q] !== R[q]) mismatches++;
        return { checked: R.length / 4, mismatches, idsMatch: city.ids().every((u, i) => u === model.nodes[i].uid) };
      },
      search(q) { return search ? Array.from((runSearch(search, q) || { indices: [] }).indices.subarray(0, 50)).map((i) => model.nodes[i].uid) : []; }
    });

    // -------------------------------------------------------------- start
    readTheme();
    const btn = $('theme-toggle');
    btn.setAttribute('aria-label', doc.documentElement.dataset.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    if (!cfg) {
      showHomeStatus('This page is missing its explorer configuration, so no datasets can load.', 'error');
      for (const v of ['graph', 'library']) $('view-' + v).hidden = true;
      $('view-home').hidden = false;
      timings.bootMs = now() - bootStart;
      return;
    }
    loadManifest().then(() => {
      const r = parseHash();
      const fromCfg = Array.isArray(cfg.defaultDatasets) ? orderedSelection(cfg.defaultDatasets.map((s) => text(s))) : [];
      const defaults = fromCfg.length ? fromCfg : manifest.defaultSelection.length ? orderedSelection(manifest.defaultSelection) : manifest.datasets.slice(0, 1).map((m) => m.id);
      state.datasets = r.datasets ? orderedSelection(r.datasets) : defaults;
      if (r.datasets && !state.datasets.length && r.datasets.length) state.datasets = defaults;
      state.view = r.view;
      state.mode = r.mode || 'treemap';
      state.selected = r.selected;
      state.query = r.query;
      try { history.replaceState({ explorer: 1, depth: 0 }, '', hashFor()); } catch (e) { /* ignore */ }
      timings.bootMs = now() - bootStart;
      renderView();
    }).catch((err) => {
      showHomeStatus('The dataset list could not load. ' + describeError(err), 'error');
      for (const v of ['graph', 'library']) $('view-' + v).hidden = true;
      $('view-home').hidden = false;
      $('home-open-graph').disabled = true;
      $('home-open-library').disabled = true;
      timings.bootMs = now() - bootStart;
    });
  }

  return {
    VERSION, WORLD_W, WORLD_H, boot, safeUrl, text, fold, buildModel, squarify, computeLayout, hitTest,
    nearestInDirection, createSearchIndex, parseQuery, runSearch, hexToRgb, evidenceFor, evidenceEntry, watchEvidence, metricText, LEGACY_ROUTES, overlapWarnings, preparedLabel
  };
});
