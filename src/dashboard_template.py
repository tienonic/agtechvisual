"""Generate interactive market map dashboard HTML."""

from __future__ import annotations

import json
from pathlib import Path

SECTOR_DESCRIPTIONS = {
    "PRECISION_AG": "Sensors, drones, satellite imagery, and data analytics for field-level decision making",
    "FARM_SOFTWARE": "Farm management platforms, ERP systems, marketplace software, and agricultural SaaS",
    "BIOTECH": "Gene editing, biologicals, alternative proteins, microbial products, and synthetic biology",
    "ROBOTICS": "Autonomous farm equipment, harvesting robots, weeding systems, and drone sprayers",
    "SUPPLY_CHAIN": "Post-harvest logistics, traceability, cold chain, food distribution, and ag marketplaces",
    "WATER_IRRIGATION": "Smart irrigation, soil moisture sensing, water conservation, and desalination tech",
    "INDOOR_CEA": "Vertical farming, controlled environment agriculture, greenhouse automation, and hydroponics",
    "AG_FINTECH": "Crop insurance, farm lending, commodity trading, and agricultural financial services",
    "LIVESTOCK": "Animal health monitoring, feed optimization, dairy tech, aquaculture, and herd management",
    "FOOD_SAFETY": "Pathogen detection, quality assurance, food testing, and contamination prevention",
    "AG_BIOCONTROL": "Biological pest control, biopesticides, pheromone-based protection, and IPM systems",
    "CONNECTIVITY": "Rural broadband, agricultural IoT infrastructure, and farm connectivity solutions",
    "UNKNOWN": "Companies not yet classified into a specific agricultural technology sector",
}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgTech Industry Classification</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: #0a0a0a;
  color: #e0e0e0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.header {
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}
.header h1 { font-size: 1.2rem; font-weight: 600; }
.header h1 span { color: #4ade80; }

/* Stats bar */
.stats-bar {
  display: flex;
  gap: 20px;
  padding: 6px 20px;
  background: #111;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.stat { text-align: center; min-width: 48px; }
.stat .value { font-size: 1.1rem; font-weight: 700; color: #fff; }
.stat .label { font-size: 0.62rem; color: #555; text-transform: uppercase; letter-spacing: 0.05em; }

/* Filter bar */
.filter-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 6px 20px;
  background: #0d0d0d;
  border-bottom: 1px solid #222;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.filter-group { display: flex; align-items: center; gap: 5px; }
.filter-group label { font-size: 0.7rem; color: #555; white-space: nowrap; }
.toggle-btn {
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 0.73rem;
  cursor: pointer;
  background: #1a1a1a;
  border: 1px solid #333;
  color: #e0e0e0;
  transition: background 0.15s;
}
.toggle-btn.active { background: #4ade80; color: #000; border-color: #4ade80; font-weight: 600; }
.toggle-btn:hover:not(.active) { background: #222; }
.search-inline {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 6px;
  padding: 4px 10px;
  color: #e0e0e0;
  font-size: 0.78rem;
  width: 200px;
  outline: none;
}
.search-inline:focus { border-color: #4ade80; }

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  padding: 0 20px;
  background: #0d0d0d;
  border-bottom: 1px solid #222;
  flex-shrink: 0;
}
.tab {
  padding: 8px 18px;
  font-size: 0.8rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  color: #666;
  transition: color 0.15s, border-color 0.15s;
  white-space: nowrap;
  user-select: none;
}
.tab:hover { color: #aaa; }
.tab.active { color: #4ade80; border-bottom-color: #4ade80; }
.tab.hidden { display: none; }

/* Main layout */
.main { display: flex; flex: 1; min-height: 0; }

/* View panels */
.view-panel { flex: 1; min-width: 0; overflow: hidden; display: flex; flex-direction: column; }
.view-panel.hidden { display: none; }

/* Circle packing view */
#view-pack {
  position: relative;
  background: #0a0a0a;
  flex-direction: row;
}
#pack-svg { width: 100%; height: 100%; display: block; }
.pack-size-toggle {
  display: flex;
  gap: 0;
  background: #111;
  border: 1px solid #333;
  border-radius: 5px;
  overflow: hidden;
}
.pack-size-toggle button {
  padding: 4px 12px;
  font-size: 0.72rem;
  cursor: pointer;
  background: transparent;
  border: none;
  color: #888;
  transition: background 0.15s, color 0.15s;
}
.pack-size-toggle button.active { background: #1e3a1e; color: #4ade80; font-weight: 600; }
.pack-size-toggle button:hover:not(.active) { background: #1a1a1a; color: #ccc; }
.sector-checks {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
}
.sector-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  cursor: pointer;
  user-select: none;
  padding: 2px 4px;
  border-radius: 4px;
}
.sector-check:hover { background: #1a1a1a; }
.sector-check input[type=checkbox] { accent-color: var(--sector-color, #4ade80); width: 14px; height: 14px; cursor: pointer; }
.sector-check .swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.sector-check.excluded { opacity: 0.35; }
.sector-check .check-label { flex: 1; }
.sector-check .check-count { color: #666; font-size: 0.65rem; }
.pack-methodology {
  position: absolute;
  bottom: 8px;
  left: 182px;
  font-size: 0.65rem;
  color: #444;
  pointer-events: none;
}

/* Sectors view */
#view-sectors {
  overflow-y: auto;
  padding: 12px;
}
.sectors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 8px;
}
.sector-card {
  background: #111;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 14px 14px 14px 18px;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.1s;
  position: relative;
  overflow: hidden;
}
.sector-card:hover { border-color: #3a3a3a; transform: translateY(-1px); }
.sector-card .sector-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  border-radius: 8px 0 0 8px;
}
.sector-card .sector-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 5px;
}
.sector-card .sector-name { font-size: 0.95rem; font-weight: 600; }
.sector-card .sector-funding { font-size: 1rem; font-weight: 700; color: #4ade80; }
.sector-card .sector-count { font-size: 0.68rem; color: #666; margin-top: 1px; text-align: right; }
.sector-card .sector-desc { font-size: 0.7rem; color: #555; margin-bottom: 8px; line-height: 1.45; }
.top-companies { display: flex; flex-wrap: wrap; gap: 4px; }
.company-chip {
  background: #181818;
  border: 1px solid #2a2a2a;
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 0.68rem;
  white-space: nowrap;
}
.company-chip.dead { opacity: 0.35; text-decoration: line-through; }
.company-chip .chip-funding { color: #4ade80; margin-left: 3px; }

/* Detail treemap view */
#view-detail {
  padding: 10px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-shrink: 0;
}
.back-btn {
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 5px;
  padding: 4px 12px;
  color: #4ade80;
  font-size: 0.78rem;
  cursor: pointer;
}
.back-btn:hover { background: #222; }
.detail-title { font-size: 1rem; font-weight: 600; }
#detail-treemap-wrap { flex: 1; min-height: 0; }
#detail-treemap-wrap svg { display: block; }

/* Sidebar */
.sidebar {
  width: 300px;
  border-left: 1px solid #222;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  background: #0d0d0d;
}
.sidebar-header {
  padding: 7px 12px;
  font-size: 0.68rem;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #1a1a1a;
  flex-shrink: 0;
}
.company-list { flex: 1; overflow-y: auto; }
.company-item {
  padding: 6px 12px;
  border-bottom: 1px solid #111;
  cursor: default;
  transition: background 0.1s;
}
.company-item:hover { background: #141414; }
.company-item.clickable { cursor: pointer; }
.company-item .ci-name { font-size: 0.8rem; font-weight: 500; display: flex; align-items: baseline; gap: 5px; }
.company-item .ci-funding {
  display: inline-block;
  background: #0f2a0f;
  color: #4ade80;
  font-size: 0.64rem;
  padding: 1px 5px;
  border-radius: 3px;
}
.company-item .ci-meta { color: #555; font-size: 0.65rem; margin-top: 1px; }
.company-item.dead .ci-name { color: #f87171; text-decoration: line-through; opacity: 0.6; }

/* Tooltip */
#tooltip {
  position: fixed;
  background: #181818;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 11px 13px;
  font-size: 0.78rem;
  pointer-events: none;
  z-index: 9999;
  max-width: 280px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.7);
  display: none;
}
#tooltip .tt-name { font-weight: 600; font-size: 0.88rem; margin-bottom: 6px; }
#tooltip .tt-row { display: flex; justify-content: space-between; gap: 12px; padding: 2px 0; }
#tooltip .tt-label { color: #666; }
#tooltip .tt-desc { margin-top: 6px; color: #777; font-size: 0.7rem; line-height: 1.4; border-top: 1px solid #222; padding-top: 6px; }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <h1><span>AgTech</span> Industry Classification <span style="font-size:0.75rem;color:#666;font-weight:400">2022 &ndash; 2026</span></h1>
  <div style="font-size:0.72rem;color:#444">Hover circles for details &middot; Click sector to zoom &middot; Double-click company to visit</div>
</div>

<!-- Stats bar -->
<div class="stats-bar">
  <div class="stat"><div class="value" id="stat-total">0</div><div class="label">Total</div></div>
  <div class="stat"><div class="value" id="stat-funding">$0</div><div class="label">Funding</div></div>
  <div class="stat"><div class="value" id="stat-sectors">0</div><div class="label">Sectors</div></div>
  <div class="stat"><div class="value" id="stat-live" style="color:#4ade80">0</div><div class="label">Live</div></div>
  <div class="stat"><div class="value" id="stat-dead" style="color:#f87171">0</div><div class="label">Dead</div></div>
  <div class="stat"><div class="value" id="stat-showing" style="color:#fbbf24">0</div><div class="label">Showing</div></div>
</div>

<!-- Filter bar -->
<div class="filter-bar">
  <div class="filter-group">
    <label>Region:</label>
    <button class="toggle-btn active" id="btnAll" onclick="setGeo('ALL')">All</button>
    <button class="toggle-btn" id="btnUS" onclick="setGeo('US')">US</button>
    <button class="toggle-btn" id="btnCA" onclick="setGeo('CA')">California</button>
  </div>
  <div class="filter-group">
    <label>Show:</label>
    <button class="toggle-btn active" id="btnClassified" onclick="setClass('CLASSIFIED')">Classified</button>
    <button class="toggle-btn" id="btnAllClass" onclick="setClass('ALL')">All</button>
  </div>
  <div class="filter-group">
    <input type="text" class="search-inline" id="search" placeholder="Search companies...">
  </div>
</div>

<!-- Tab bar -->
<div class="tab-bar">
  <div class="tab active" id="tab-pack" onclick="switchView('pack')">Overview</div>
  <div class="tab" id="tab-sectors" onclick="switchView('sectors')">Sectors</div>
  <div class="tab hidden" id="tab-detail">Detail</div>
</div>

<!-- Main -->
<div class="main">

  <!-- Circle Packing View -->
  <div class="view-panel" id="view-pack" style="display:flex;gap:0">
    <!-- Left sidebar: sector filters + size toggle -->
    <div style="width:170px;flex-shrink:0;border-right:1px solid #222;padding:8px;overflow-y:auto;background:#0a0a0a">
      <div style="font-size:0.68rem;color:#555;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Sectors</div>
      <div class="sector-checks" id="sector-checks"></div>
      <div style="margin-top:10px;border-top:1px solid #222;padding-top:8px">
        <div style="font-size:0.68rem;color:#555;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Size by</div>
        <div class="pack-size-toggle">
          <button id="btn-size-funding" class="active" onclick="setSizeMode('funding')">Funding</button>
          <button id="btn-size-count" onclick="setSizeMode('count')">Count</button>
        </div>
      </div>
    </div>
    <!-- Pack canvas -->
    <div style="flex:1;position:relative;overflow:hidden">
      <svg id="pack-svg"></svg>
      <div class="pack-methodology" id="pack-methodology">Circle area proportional to log(funding)</div>
    </div>
  </div>

  <!-- Sectors Grid View -->
  <div class="view-panel hidden" id="view-sectors">
    <div class="sectors-grid" id="sectors-grid"></div>
  </div>

  <!-- Detail Treemap View -->
  <div class="view-panel hidden" id="view-detail">
    <div class="detail-header">
      <button class="back-btn" id="back-btn" onclick="goBack()">&#8592; Back</button>
      <div class="detail-title" id="detail-title"></div>
    </div>
    <div id="detail-treemap-wrap" style="flex:1;min-height:0"></div>
  </div>

  <!-- Sidebar: company list -->
  <div class="sidebar">
    <div class="sidebar-header">Companies &mdash; <span id="list-count">0</span></div>
    <div class="company-list" id="company-list"></div>
  </div>

</div>

<div id="tooltip"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
// ─────────────────────────────────────────────
// Injected data
// ─────────────────────────────────────────────
const DATA = __DATA_PLACEHOLDER__;
const SECTOR_DESC = __SECTOR_DESC__;

const COLORS = {
  PRECISION_AG:    '#3b82f6',
  FARM_SOFTWARE:   '#8b5cf6',
  BIOTECH:         '#10b981',
  ROBOTICS:        '#f59e0b',
  SUPPLY_CHAIN:    '#ec4899',
  WATER_IRRIGATION:'#06b6d4',
  INDOOR_CEA:      '#84cc16',
  AG_FINTECH:      '#f97316',
  LIVESTOCK:       '#a855f7',
  FOOD_SAFETY:     '#ef4444',
  AG_BIOCONTROL:   '#14b8a6',
  CONNECTIVITY:    '#6366f1',
  UNKNOWN:         '#444444',
};

const LABELS = {
  PRECISION_AG:    'Precision Ag',
  FARM_SOFTWARE:   'Farm Software',
  BIOTECH:         'Biotech',
  ROBOTICS:        'Robotics',
  SUPPLY_CHAIN:    'Supply Chain',
  WATER_IRRIGATION:'Water & Irrigation',
  INDOOR_CEA:      'Indoor / CEA',
  AG_FINTECH:      'AgFintech',
  LIVESTOCK:       'Livestock',
  FOOD_SAFETY:     'Food Safety',
  AG_BIOCONTROL:   'Biocontrol',
  CONNECTIVITY:    'Connectivity',
  UNKNOWN:         'Unclassified',
};

// ─────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────
const ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
function esc(s) { return s ? String(s).replace(/[&<>"']/g, c => ESC_MAP[c]) : ''; }

function fmt(v) {
  if (!v || v <= 0) return '';
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(0) + 'M';
  if (v >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
  return '$' + v;
}

function safeUrl(u) {
  if (!u) return null;
  try {
    const p = new URL(u);
    return ['http:', 'https:'].includes(p.protocol) ? p.href : null;
  } catch (e) { return null; }
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
}

// ─────────────────────────────────────────────
// Application state
// ─────────────────────────────────────────────
var filters = { geo: 'ALL', classification: 'CLASSIFIED', search: '' };
var sizeMode = 'funding';
var excludedSectors = new Set();
var currentView = 'pack';
var detailSector = null;
var prevView = 'pack';

// ─────────────────────────────────────────────
// Filter helpers
// ─────────────────────────────────────────────
function setGeo(mode) {
  filters.geo = mode;
  ['btnAll', 'btnUS', 'btnCA'].forEach(function(id) {
    document.getElementById(id).classList.remove('active');
  });
  var map = { ALL: 'btnAll', US: 'btnUS', CA: 'btnCA' };
  document.getElementById(map[mode]).classList.add('active');
  refresh();
}

function setClass(mode) {
  filters.classification = mode;
  document.getElementById('btnClassified').classList.toggle('active', mode === 'CLASSIFIED');
  document.getElementById('btnAllClass').classList.toggle('active', mode === 'ALL');
  refresh();
}

function setSizeMode(mode) {
  sizeMode = mode;
  document.getElementById('btn-size-funding').classList.toggle('active', mode === 'funding');
  document.getElementById('btn-size-count').classList.toggle('active', mode === 'count');
  document.getElementById('pack-methodology').textContent =
    mode === 'funding' ? 'Circle area proportional to log(funding)' : 'Equal area per company';
  buildCirclePacking(getFiltered());
}

function getFiltered() {
  var q = filters.search.toLowerCase();
  return DATA.companies.filter(function(c) {
    if (filters.geo === 'CA' && c.hq_state !== 'CA') return false;
    if (filters.geo === 'US' && c.country && c.country !== 'US') return false;
    if (filters.classification === 'CLASSIFIED' && c.category === 'UNKNOWN') return false;
    if (q && !c.name.toLowerCase().includes(q) && !(c.description || '').toLowerCase().includes(q)) return false;
    return true;
  });
}

function buildSectors(filtered) {
  var map = {};
  filtered.forEach(function(c) {
    if (!map[c.category]) map[c.category] = { companies: [], totalFunding: 0 };
    map[c.category].companies.push(c);
    map[c.category].totalFunding += (c.funding || 0);
  });
  return Object.entries(map)
    .map(function(entry) {
      var cat = entry[0];
      var d = entry[1];
      return {
        category: cat,
        label: LABELS[cat] || cat,
        color: COLORS[cat] || '#444',
        description: SECTOR_DESC[cat] || '',
        companies: d.companies.sort(function(a, b) { return (b.funding || 0) - (a.funding || 0); }),
        totalFunding: d.totalFunding,
        count: d.companies.length,
      };
    })
    .sort(function(a, b) { return b.totalFunding - a.totalFunding || b.count - a.count; });
}

function updateStats(filtered, sectors) {
  var funding = filtered.reduce(function(s, c) { return s + (c.funding || 0); }, 0);
  var live = filtered.filter(function(c) { return c.status === 'LIVE'; }).length;
  var dead = filtered.filter(function(c) { return c.status === 'DEAD'; }).length;
  document.getElementById('stat-total').textContent = DATA.companies.length.toLocaleString();
  document.getElementById('stat-funding').textContent = fmt(funding) || '$0';
  document.getElementById('stat-sectors').textContent = sectors.length;
  document.getElementById('stat-live').textContent = live;
  document.getElementById('stat-dead').textContent = dead;
  document.getElementById('stat-showing').textContent = filtered.length;
}

// ─────────────────────────────────────────────
// View switching
// ─────────────────────────────────────────────
function switchView(view, sector) {
  if (view === 'detail' && !sector && !detailSector) return;

  prevView = currentView;
  currentView = view;

  ['pack', 'sectors', 'detail'].forEach(function(v) {
    document.getElementById('view-' + v).classList.toggle('hidden', v !== view);
    document.getElementById('tab-' + v).classList.toggle('active', v === view);
  });

  var detailTab = document.getElementById('tab-detail');
  if (view === 'detail') {
    detailTab.classList.remove('hidden');
    if (sector) detailSector = sector;
  } else {
    detailTab.classList.add('hidden');
    detailSector = null;
  }

  refresh();
}

function goBack() {
  switchView(prevView === 'detail' ? 'pack' : prevView);
}

function showSectorDetail(category) {
  switchView('detail', category);
}

// ─────────────────────────────────────────────
// Sector filter checkboxes
// ─────────────────────────────────────────────
function buildSectorChips(sectors) {
  var container = document.getElementById('sector-checks');
  container.innerHTML = '';
  sectors.forEach(function(s) {
    var row = document.createElement('label');
    row.className = 'sector-check' + (excludedSectors.has(s.category) ? ' excluded' : '');
    row.style.setProperty('--sector-color', s.color);

    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = !excludedSectors.has(s.category);

    var swatch = document.createElement('span');
    swatch.className = 'swatch';
    swatch.style.background = s.color;

    var lbl = document.createElement('span');
    lbl.className = 'check-label';
    lbl.style.color = s.color;
    lbl.textContent = s.label;

    var cnt = document.createElement('span');
    cnt.className = 'check-count';
    cnt.textContent = s.count;

    cb.addEventListener('change', (function(sector, rowEl) {
      return function() {
        if (cb.checked) {
          excludedSectors.delete(sector.category);
          rowEl.classList.remove('excluded');
        } else {
          excludedSectors.add(sector.category);
          rowEl.classList.add('excluded');
        }
        buildCirclePacking(getFiltered());
      };
    })(s, row));

    row.appendChild(cb);
    row.appendChild(swatch);
    row.appendChild(lbl);
    row.appendChild(cnt);
    container.appendChild(row);
  });
}

// ─────────────────────────────────────────────
// Circle Packing (D3 v7, interpolateZoom)
// ─────────────────────────────────────────────
function buildCirclePacking(filtered) {
  var svgEl = document.getElementById('pack-svg');
  var W = svgEl.clientWidth || 800;
  var H = svgEl.clientHeight || 600;

  // Build hierarchy — exclude filtered-out sectors
  var active = filtered.filter(function(c) { return !excludedSectors.has(c.category); });
  var sectorMap = {};
  active.forEach(function(c) {
    if (!sectorMap[c.category]) sectorMap[c.category] = [];
    sectorMap[c.category].push(c);
  });

  var children = Object.entries(sectorMap).map(function(entry) {
    var cat = entry[0];
    var cos = entry[1];
    return {
      name: cat,
      category: cat,
      isSector: true,
      children: cos.map(function(c) {
        return Object.assign({}, c, {
          isSector: false,
          leafValue: sizeMode === 'funding' ? Math.log10((c.funding || 0) + 1000) : 1,
        });
      }),
    };
  });

  var hierarchyData = { name: 'root', children: children };
  var root = d3.hierarchy(hierarchyData)
    .sum(function(d) { return d.leafValue || 0; })
    .sort(function(a, b) { return b.value - a.value; });

  d3.pack().size([W, H]).padding(3)(root);

  // Clear SVG and rebuild
  var svg = d3.select('#pack-svg');
  svg.selectAll('*').remove();
  svg.attr('viewBox', '0 0 ' + W + ' ' + H)
     .attr('width', W)
     .attr('height', H);

  var g = svg.append('g');
  var tooltip = document.getElementById('tooltip');

  // Zoom state
  var currentZoom = root;

  function applyTransform(node, durationMs) {
    var fitDim = Math.min(W, H);
    var scale = fitDim / (node.r * 2);
    if (node === root) scale *= 1.05;
    if (node !== root) scale *= 0.9;
    var tx = W / 2 - node.x * scale;
    var ty = H / 2 - node.y * scale;

    if (!durationMs) {
      g.attr('transform', 'translate(' + tx + ',' + ty + ') scale(' + scale + ')');
      updateCompanyLabels(scale);
      return;
    }

    // Animate with interpolateZoom
    var startView = [currentZoom.x, currentZoom.y, currentZoom.r * 2];
    var endView   = [node.x,         node.y,         node.r * 2];

    svg.transition().duration(durationMs)
      .tween('zoom', function() {
        var interp = d3.interpolateZoom(startView, endView);
        return function(t) {
          var v = interp(t);
          var s = Math.min(W, H) / v[2];
          g.attr('transform', 'translate(' + (W / 2 - v[0] * s) + ',' + (H / 2 - v[1] * s) + ') scale(' + s + ')');
        };
      })
      .on('end', function() {
        var finalScale = Math.min(W, H) / (node.r * 2);
        updateCompanyLabels(finalScale);
      });
  }

  function zoomTo(node) {
    currentZoom = node;
    applyTransform(node, 750);
    updateSectorLabelVisibility(null);
  }

  // Render sector circles
  var sectorNodes = root.children || [];
  sectorNodes.forEach(function(sNode) {
    var cat = sNode.data.category;
    var color = COLORS[cat] || '#444';

    g.append('circle')
      .datum(sNode)
      .attr('cx', sNode.x)
      .attr('cy', sNode.y)
      .attr('r', sNode.r)
      .attr('fill', hexToRgba(color, 0.12))
      .attr('stroke', color)
      .attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('click', function(e) {
        e.stopPropagation();
        tooltip.style.display = 'none';
        if (currentZoom === sNode) {
          zoomTo(root);
        } else {
          zoomTo(sNode);
        }
      });
  });

  // Render company circles
  var leafNodes = root.leaves();
  leafNodes.forEach(function(lNode) {
    var c = lNode.data;
    var cat = c.category;
    var color = COLORS[cat] || '#444';
    var isDead = c.status === 'DEAD';

    g.append('circle')
      .datum(lNode)
      .attr('cx', lNode.x)
      .attr('cy', lNode.y)
      .attr('r', Math.max(lNode.r, 0))
      .attr('fill', color)
      .attr('stroke', '#0a0a0a')
      .attr('stroke-width', 0.5)
      .style('opacity', isDead ? 0.3 : 0.85)
      .style('filter', isDead ? 'grayscale(100%)' : 'none')
      .style('cursor', 'pointer')
      .on('mousemove', function(e) {
        updateSectorLabelVisibility(lNode.parent);
        var desc = c.description || '';
        var shortDesc = desc.length > 100 ? desc.slice(0, 100) + '...' : desc;
        var statusColor = c.status === 'LIVE' ? '#4ade80' : c.status === 'DEAD' ? '#f87171' : '#888';
        tooltip.innerHTML =
          '<div class="tt-name">' + esc(c.name) + '</div>' +
          '<div class="tt-row"><span class="tt-label">Funding</span><span>' + (fmt(c.funding) || 'N/A') + '</span></div>' +
          '<div class="tt-row"><span class="tt-label">Sector</span><span>' + esc(LABELS[cat] || cat) + '</span></div>' +
          '<div class="tt-row"><span class="tt-label">Status</span><span style="color:' + statusColor + '">' + esc(c.status) + '</span></div>' +
          (shortDesc ? '<div class="tt-desc">' + esc(shortDesc) + '</div>' : '');
        tooltip.style.display = 'block';
        tooltip.style.left = Math.min(e.clientX + 14, window.innerWidth - 295) + 'px';
        tooltip.style.top = Math.min(e.clientY - 10, window.innerHeight - 180) + 'px';
      })
      .on('mouseleave', function() {
        tooltip.style.display = 'none';
        updateSectorLabelVisibility(null);
      })
      .on('click', function(e) {
        e.stopPropagation();
        tooltip.style.display = 'none';
        if (currentZoom !== lNode.parent) {
          zoomTo(lNode.parent);
        }
      })
      .on('dblclick', function(e) {
        e.stopPropagation();
        tooltip.style.display = 'none';
        var url = isDead ? safeUrl(c.wayback_url) : safeUrl(c.website);
        if (url) window.open(url, '_blank', 'noopener');
      });
  });

  // Render sector labels ON TOP of company circles
  sectorNodes.forEach(function(sNode) {
    var cat = sNode.data.category;
    var label = LABELS[cat] || cat;
    var totalFunding = sNode.children
      ? sNode.children.reduce(function(s, n) { return s + (n.data.funding || 0); }, 0)
      : 0;
    var labelSize = Math.max(10, Math.min(18, sNode.r * 0.18));

    g.append('text')
      .datum(sNode)
      .attr('class', 'sector-label')
      .attr('x', sNode.x)
      .attr('y', totalFunding > 0 ? sNode.y - labelSize * 0.4 : sNode.y)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('font-size', labelSize)
      .attr('fill', '#fff')
      .attr('font-weight', '700')
      .attr('pointer-events', 'none')
      .style('text-shadow', '0 1px 6px rgba(0,0,0,0.9), 0 0 12px rgba(0,0,0,0.6)')
      .text(label);

    if (totalFunding > 0) {
      g.append('text')
        .datum(sNode)
        .attr('class', 'sector-funding-label')
        .attr('x', sNode.x)
        .attr('y', sNode.y + labelSize * 0.7)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('font-size', Math.max(8, Math.min(13, sNode.r * 0.12)))
        .attr('fill', '#fff')
        .attr('font-weight', '500')
        .attr('pointer-events', 'none')
        .style('text-shadow', '0 1px 6px rgba(0,0,0,0.9), 0 0 12px rgba(0,0,0,0.6)')
        .text(fmt(totalFunding));
    }
  });

  // Sector label visibility
  function updateSectorLabelVisibility(hoveredParent) {
    var zoomedToSector = currentZoom !== root;
    g.selectAll('.sector-label, .sector-funding-label').style('opacity', function(d) {
      if (zoomedToSector && d === currentZoom) return 0;
      if (hoveredParent && d === hoveredParent) return 0.15;
      if (zoomedToSector) return 0;
      return 1;
    });
  }

  // Company name labels — shown when screen-space radius > 20px
  function updateCompanyLabels(scale) {
    g.selectAll('.company-name-label').remove();
    leafNodes.forEach(function(lNode) {
      if (lNode.r * scale > 20) {
        var c = lNode.data;
        var maxChars = Math.floor((lNode.r * scale * 2) / 6.5);
        var label = c.name;
        if (label.length > maxChars) label = label.slice(0, Math.max(maxChars - 1, 3)) + '\u2026';
        g.append('text')
          .attr('class', 'company-name-label')
          .attr('x', lNode.x)
          .attr('y', lNode.y)
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'middle')
          .attr('font-size', Math.max(5, Math.min(10, lNode.r * 0.45)) / scale)
          .attr('fill', '#fff')
          .attr('pointer-events', 'none')
          .text(label);
      }
    });
  }

  // Set initial transform (fit root)
  applyTransform(root, 0);

  // Click SVG background to zoom out
  svg.on('click', function(e) {
    if (e.target === svg.node()) {
      tooltip.style.display = 'none';
      if (currentZoom !== root) zoomTo(root);
    }
  });
}

// ─────────────────────────────────────────────
// Sectors grid view
// ─────────────────────────────────────────────
function renderSectorsView(sectors) {
  var grid = document.getElementById('sectors-grid');
  grid.innerHTML = '';
  sectors.forEach(function(sector) {
    var card = document.createElement('div');
    card.className = 'sector-card';
    card.addEventListener('click', function() { showSectorDetail(sector.category); });

    var topCos = sector.companies.slice(0, 8);
    var chipsHtml = topCos.map(function(c) {
      var deadClass = c.status === 'DEAD' ? ' dead' : '';
      var f = c.funding > 0 ? '<span class="chip-funding">' + fmt(c.funding) + '</span>' : '';
      return '<span class="company-chip' + deadClass + '">' + esc(c.name) + f + '</span>';
    }).join('');

    card.innerHTML =
      '<div class="sector-bar" style="background:' + sector.color + '"></div>' +
      '<div class="sector-header">' +
        '<div class="sector-name" style="color:' + sector.color + '">' + esc(sector.label) + '</div>' +
        '<div>' +
          '<div class="sector-funding">' + (fmt(sector.totalFunding) || '$0') + '</div>' +
          '<div class="sector-count">' + sector.count + ' companies</div>' +
        '</div>' +
      '</div>' +
      '<div class="sector-desc">' + esc(sector.description) + '</div>' +
      '<div class="top-companies">' + chipsHtml + '</div>';

    grid.appendChild(card);
  });
}

// ─────────────────────────────────────────────
// Detail treemap view
// ─────────────────────────────────────────────
function renderDetailView(companies, category) {
  var label = LABELS[category] || category;
  document.getElementById('detail-title').textContent = label;

  var wrap = document.getElementById('detail-treemap-wrap');
  wrap.innerHTML = '';
  if (!companies.length) return;

  var W = wrap.clientWidth || 600;
  var H = Math.max(wrap.clientHeight || 400, 200);
  var color = COLORS[category] || '#444';
  var tooltip = document.getElementById('tooltip');

  var root = d3.hierarchy({
    name: 'root',
    children: companies.map(function(c) { return Object.assign({}, c, { value: Math.max(c.funding || 1, 1) }); })
  })
    .sum(function(d) { return d.value; })
    .sort(function(a, b) { return b.value - a.value; });

  d3.treemap().size([W, H]).padding(2).round(true)(root);

  var svg = d3.select(wrap).append('svg').attr('width', W).attr('height', H);

  var leaves = svg.selectAll('.leaf').data(root.leaves()).join('g')
    .attr('transform', function(d) { return 'translate(' + d.x0 + ',' + d.y0 + ')'; });

  leaves.append('rect')
    .attr('width', function(d) { return Math.max(d.x1 - d.x0, 0); })
    .attr('height', function(d) { return Math.max(d.y1 - d.y0, 0); })
    .attr('fill', color)
    .attr('rx', 3)
    .attr('stroke', '#0a0a0a')
    .attr('stroke-width', 0.5)
    .style('opacity', function(d) { return d.data.status === 'DEAD' ? 0.3 : 0.85; })
    .style('filter', function(d) { return d.data.status === 'DEAD' ? 'grayscale(100%)' : 'none'; })
    .style('cursor', 'pointer')
    .on('mousemove', function(e, d) {
      var desc = d.data.description || '';
      var shortDesc = desc.length > 100 ? desc.slice(0, 100) + '...' : desc;
      var statusColor = d.data.status === 'LIVE' ? '#4ade80' : d.data.status === 'DEAD' ? '#f87171' : '#888';
      tooltip.innerHTML =
        '<div class="tt-name">' + esc(d.data.name) + '</div>' +
        '<div class="tt-row"><span class="tt-label">Funding</span><span>' + (fmt(d.data.funding) || 'N/A') + '</span></div>' +
        '<div class="tt-row"><span class="tt-label">Status</span><span style="color:' + statusColor + '">' + esc(d.data.status) + '</span></div>' +
        (shortDesc ? '<div class="tt-desc">' + esc(shortDesc) + '</div>' : '');
      tooltip.style.display = 'block';
      tooltip.style.left = Math.min(e.clientX + 14, window.innerWidth - 295) + 'px';
      tooltip.style.top = Math.min(e.clientY - 10, window.innerHeight - 180) + 'px';
    })
    .on('mouseleave', function() { tooltip.style.display = 'none'; })
    .on('click', function(e, d) {
      var url = d.data.status === 'DEAD' ? safeUrl(d.data.wayback_url) : safeUrl(d.data.website);
      if (url) window.open(url, '_blank', 'noopener');
    });

  leaves.append('text')
    .attr('x', 4)
    .attr('y', 14)
    .attr('font-size', '9px')
    .attr('fill', '#fff')
    .attr('pointer-events', 'none')
    .style('text-shadow', '0 1px 2px rgba(0,0,0,0.8)')
    .text(function(d) {
      var rectW = d.x1 - d.x0;
      if (rectW < 36) return '';
      var maxLen = Math.floor(rectW / 5.5);
      var lbl = d.data.funding > 0 ? (d.data.name + ' ' + fmt(d.data.funding)) : d.data.name;
      return lbl.length > maxLen ? lbl.slice(0, Math.max(maxLen - 1, 3)) + '\u2026' : lbl;
    });
}

// ─────────────────────────────────────────────
// Sidebar company list
// ─────────────────────────────────────────────
function renderList(companies) {
  var sorted = companies.slice().sort(function(a, b) { return (b.funding || 0) - (a.funding || 0); });
  document.getElementById('list-count').textContent = sorted.length;

  var el = document.getElementById('company-list');
  el.innerHTML = '';

  sorted.slice(0, 300).forEach(function(c) {
    var isDead = c.status === 'DEAD';
    var siteUrl = !isDead ? safeUrl(c.website) : null;

    var div = document.createElement('div');
    div.className = 'company-item' + (isDead ? ' dead' : '') + (siteUrl ? ' clickable' : '');
    if (siteUrl) {
      div.addEventListener('click', function() { window.open(siteUrl, '_blank', 'noopener'); });
    }

    var nameDiv = document.createElement('div');
    nameDiv.className = 'ci-name';
    nameDiv.textContent = c.name;
    if (c.funding > 0) {
      var badge = document.createElement('span');
      badge.className = 'ci-funding';
      badge.textContent = fmt(c.funding);
      nameDiv.appendChild(badge);
    }

    var metaDiv = document.createElement('div');
    metaDiv.className = 'ci-meta';
    metaDiv.textContent = (LABELS[c.category] || c.category) + ' \u00b7 ' + (c.country || 'US') + ' \u00b7 ' + c.status;

    div.appendChild(nameDiv);
    div.appendChild(metaDiv);
    el.appendChild(div);
  });
}

// ─────────────────────────────────────────────
// Main refresh
// ─────────────────────────────────────────────
function refresh() {
  var filtered = getFiltered();
  var sectors = buildSectors(filtered);
  updateStats(filtered, sectors);

  if (currentView === 'pack') {
    buildSectorChips(sectors);
    buildCirclePacking(filtered);
    renderList(filtered);
  } else if (currentView === 'sectors') {
    renderSectorsView(sectors);
    renderList(filtered);
  } else if (currentView === 'detail' && detailSector) {
    var sectorCompanies = filtered.filter(function(c) { return c.category === detailSector; });
    renderDetailView(sectorCompanies, detailSector);
    renderList(sectorCompanies);
  }
}

// ─────────────────────────────────────────────
// Event listeners
// ─────────────────────────────────────────────
document.getElementById('search').addEventListener('input', function(e) {
  filters.search = e.target.value;
  refresh();
});

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    // Trigger a click on the SVG background to zoom out (handled in buildCirclePacking)
    var packSvg = document.getElementById('pack-svg');
    if (packSvg && currentView === 'pack') {
      packSvg.dispatchEvent(new MouseEvent('click', { bubbles: false }));
    }
  }
});

window.addEventListener('resize', function() {
  if (currentView === 'pack') {
    buildCirclePacking(getFiltered());
  } else if (currentView === 'detail' && detailSector) {
    var filtered = getFiltered();
    renderDetailView(filtered.filter(function(c) { return c.category === detailSector; }), detailSector);
  }
});

// ─────────────────────────────────────────────
// Boot
// ─────────────────────────────────────────────
refresh();
</script>
</body>
</html>"""


def render_dashboard(data: dict, output_path: Path):
    """Write the dashboard HTML with embedded data."""
    data_json = json.dumps(data, ensure_ascii=False)
    desc_json = json.dumps(SECTOR_DESCRIPTIONS, ensure_ascii=False)
    html = TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)
    html = html.replace("__SECTOR_DESC__", desc_json)
    output_path.write_text(html, encoding="utf-8")
