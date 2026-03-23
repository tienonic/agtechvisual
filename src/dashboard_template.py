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
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI Variable Display", "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: #2e2f31;
  color: rgba(255,255,255,0.9);
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.header {
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
  background: #242426;
}
.header h1 { font-size: 18px; font-weight: 600; }
.header h1 span { color: #4ade80; }

/* Stats bar */
.stats-bar {
  display: flex;
  gap: 24px;
  padding: 10px 20px;
  background: #242426;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
  flex-wrap: wrap;
}
.stat { text-align: center; min-width: 52px; }
.stat .value { font-size: 18px; font-weight: 700; color: rgba(255,255,255,0.9); }
.stat .label { font-size: 10px; font-weight: 600; color: rgba(255,255,255,0.3); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 1px; }

/* Filter bar */
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 20px;
  background: #2e2f31;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-wrap: wrap;
  flex-shrink: 0;
}
.filter-group { display: flex; align-items: center; gap: 6px; }
.filter-group label { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.4); white-space: nowrap; }
.toggle-btn {
  padding: 4px 12px;
  height: 30px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  color: rgba(255,255,255,0.7);
  transition: background 100ms ease-out;
  box-shadow: rgba(15,15,15,0.1) 0px 0px 0px 1px inset, rgba(15,15,15,0.1) 0px 1px 2px;
}
.toggle-btn.active { background: #4ade80; color: #000; border-color: #4ade80; font-weight: 600; }
.toggle-btn:hover:not(.active) { background: rgba(255,255,255,0.12); }
.search-inline {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 17px;
  padding: 5px 14px;
  color: rgba(255,255,255,0.9);
  font-size: 14px;
  width: 220px;
  outline: none;
}
.search-inline:focus { border-color: rgb(58,151,212); box-shadow: rgb(58 151 212 / 36%) 0px 0px 0px 3px; }
.search-inline::placeholder { color: rgba(255,255,255,0.3); }
.funding-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100px;
  height: 4px;
  background: rgba(255,255,255,0.15);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.funding-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #4ade80;
  cursor: pointer;
  border: 2px solid #242426;
}
.funding-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #4ade80;
  cursor: pointer;
  border: 2px solid #242426;
}

/* Tab bar */
.tab-bar {
  display: flex;
  gap: 0;
  padding: 0 20px;
  background: #242426;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
  position: relative;
}
.tab-bar .zoom-label {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  font-size: 15px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  pointer-events: none;
  opacity: 0;
  transition: opacity 250ms;
}
.tab-bar .zoom-label.visible { opacity: 1; }
.tab {
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  color: rgba(255,255,255,0.4);
  transition: color 150ms, border-color 150ms;
  white-space: nowrap;
  user-select: none;
}
.tab:hover { color: rgba(255,255,255,0.7); }
.tab.active { color: #4ade80; border-bottom-color: #4ade80; font-weight: 600; }
.tab.hidden { display: none; }

/* Main layout */
.main { display: flex; flex: 1; min-height: 0; }

/* View panels */
.view-panel { flex: 1; min-width: 0; overflow: hidden; display: flex; flex-direction: column; }
.view-panel.hidden { display: none; }

/* Circle packing view */
#view-pack {
  position: relative;
  background: #2e2f31;
  flex-direction: row;
  display: flex;
  gap: 0;
}
#view-pack.hidden { display: none !important; }
#pack-svg { width: 100%; height: 100%; display: block; }
.pack-size-toggle {
  display: flex;
  gap: 0;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  overflow: hidden;
}
.pack-size-toggle button {
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  background: transparent;
  border: none;
  color: rgba(255,255,255,0.4);
  transition: background 100ms ease-out, color 150ms;
}
.pack-size-toggle button.active { background: rgba(74,222,128,0.15); color: #4ade80; font-weight: 600; }
.pack-size-toggle button:hover:not(.active) { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); }
.sector-checks {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 8px 0;
}
.sector-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  padding: 3px 6px;
  border-radius: 5px;
}
.sector-check:hover { background: rgba(255,255,255,0.06); }
.sector-check input[type=checkbox] { accent-color: var(--sector-color, #4ade80); width: 14px; height: 14px; cursor: pointer; }
.sector-check .swatch { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
.sector-check.excluded { opacity: 0.35; }
.sector-check .check-label { flex: 1; }
.sector-check .check-count { color: rgba(255,255,255,0.3); font-size: 12px; font-weight: 500; }
.pack-methodology {
  position: absolute;
  bottom: 10px;
  left: 182px;
  font-size: 11px;
  color: rgba(255,255,255,0.2);
  pointer-events: none;
}

/* Sectors view */
#view-sectors {
  overflow-y: auto;
  padding: 16px;
}
.sectors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
}
.sector-card {
  background: #242426;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 16px 16px 16px 20px;
  cursor: pointer;
  transition: border-color 200ms, transform 100ms, box-shadow 200ms;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.sector-card:hover { border-color: rgba(255,255,255,0.18); transform: translateY(-1px); box-shadow: 0 4px 16px rgba(0,0,0,0.25); }
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
  margin-bottom: 6px;
}
.sector-card .sector-name { font-size: 16px; font-weight: 600; }
.sector-card .sector-funding { font-size: 16px; font-weight: 700; color: #4ade80; }
.sector-card .sector-count { font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.4); margin-top: 2px; text-align: right; }
.sector-card .sector-desc { font-size: 13px; color: rgba(255,255,255,0.45); margin-bottom: 10px; line-height: 1.5; }
.top-companies { display: flex; flex-wrap: wrap; gap: 5px; }
.company-chip {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 12px;
  white-space: nowrap;
}
.company-chip.dead { opacity: 0.35; text-decoration: line-through; }
.company-chip .chip-funding { color: #4ade80; margin-left: 4px; font-weight: 500; }

/* Detail treemap view */
#view-detail {
  padding: 12px 16px;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.back-btn {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 6px;
  padding: 5px 14px;
  color: rgba(255,255,255,0.9);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: rgba(15,15,15,0.1) 0px 0px 0px 1px inset, rgba(15,15,15,0.1) 0px 1px 2px;
  transition: background 100ms ease-out;
}
.back-btn:hover { background: rgba(255,255,255,0.12); }
.detail-title { font-size: 18px; font-weight: 600; }
#detail-treemap-wrap { flex: 1; min-height: 0; }
#detail-treemap-wrap svg { display: block; }

/* Sidebar */
.sidebar {
  width: 300px;
  border-left: 1px solid rgba(255,255,255,0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  background: #242426;
}
.sidebar-header {
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 700;
  color: rgba(255,255,255,0.4);
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}
.company-list { flex: 1; overflow-y: auto; }
.company-item {
  padding: 8px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  cursor: default;
  transition: background 100ms ease-out;
}
.company-item:hover { background: rgba(255,255,255,0.04); }
.company-item.clickable { cursor: pointer; }
.company-item .ci-name { font-size: 14px; font-weight: 500; display: flex; align-items: baseline; gap: 6px; }
.company-item .ci-funding {
  display: inline-block;
  background: rgba(74,222,128,0.15);
  color: #4ade80;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
}
.company-item .ci-meta { color: rgba(255,255,255,0.35); font-size: 12px; margin-top: 2px; }
.company-item.dead .ci-name { color: #f87171; text-decoration: line-through; opacity: 0.6; }

/* Tooltip */
#tooltip {
  position: fixed;
  background: rgb(15,15,15);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  padding: 12px 14px;
  font-size: 14px;
  pointer-events: none;
  z-index: 9999;
  max-width: 300px;
  box-shadow: rgba(15,15,15,0.05) 0px 0px 0px 1px, rgba(15,15,15,0.1) 0px 5px 10px, rgba(15,15,15,0.2) 0px 15px 40px;
  display: none;
  color: rgba(255,255,255,0.9);
}
#tooltip .tt-name { font-weight: 600; font-size: 15px; margin-bottom: 8px; }
#tooltip .tt-row { display: flex; justify-content: space-between; gap: 16px; padding: 3px 0; font-size: 13px; }
#tooltip .tt-label { color: rgba(255,255,255,0.4); }
#tooltip .tt-desc { margin-top: 8px; color: rgba(255,255,255,0.6); font-size: 13px; line-height: 1.5; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; }
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
    <button class="toggle-btn" id="btnFunded" onclick="setClass('FUNDED')">Funded</button>
    <button class="toggle-btn" id="btnAllClass" onclick="setClass('ALL')">All</button>
  </div>
  <div class="filter-group">
    <input type="text" class="search-inline" id="search" placeholder="Search companies...">
  </div>
  <div class="filter-group">
    <label>Funded:</label>
    <input type="range" id="funding-slider" min="0" max="7" value="0" class="funding-slider">
    <span id="funding-slider-label" style="font-size:12px;font-weight:500;color:rgba(255,255,255,0.7);min-width:36px">Any</span>
  </div>
</div>

<!-- Tab bar -->
<div class="tab-bar">
  <div class="tab active" id="tab-pack" onclick="switchView('pack')">Overview</div>
  <div class="tab" id="tab-sectors" onclick="switchView('sectors')">Sectors</div>
  <div class="tab hidden" id="tab-detail">Detail</div>
  <div class="zoom-label" id="zoom-label"></div>
</div>

<!-- Main -->
<div class="main">

  <!-- Circle Packing View -->
  <div class="view-panel" id="view-pack">
    <!-- Left sidebar: sector filters + size toggle -->
    <div data-pack-sidebar style="width:170px;flex-shrink:0;border-right:1px solid rgba(255,255,255,0.1);padding:8px;overflow-y:auto;background:#242426">
      <div style="font-size:0.68rem;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Sectors</div>
      <div class="sector-checks" id="sector-checks"></div>
      <div style="margin-top:10px;border-top:1px solid rgba(255,255,255,0.1);padding-top:8px">
        <div style="font-size:0.68rem;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px">Size by</div>
        <div class="pack-size-toggle">
          <button id="btn-size-funding" class="active" onclick="setSizeMode('funding')">Funding</button>
          <button id="btn-size-count" onclick="setSizeMode('count')">Count</button>
        </div>
      </div>
    </div>
    <!-- Pack canvas -->
    <div style="flex:1;position:relative;overflow:hidden" id="pack-canvas">
      <svg id="pack-svg"></svg>
      <div id="pack-treemap-overlay" style="display:none;position:absolute;inset:0;background:#2e2f31;overflow:hidden;flex-direction:column"></div>
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
    <div class="sidebar-header"><span id="sidebar-label">Companies</span> &mdash; <span id="list-count">0</span></div>
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
var filters = { geo: 'ALL', classification: 'CLASSIFIED', search: '', minFunding: 0 };
var FUNDING_STEPS = [0, 1e5, 5e5, 1e6, 5e6, 10e6, 50e6, 100e6];
var sizeMode = 'funding';
var excludedSectors = new Set();
var currentView = 'pack';
var detailSector = null;
var prevView = 'pack';
var zoomedCategory = null;  // track which sector is zoomed in circle packing
var _renderPackTreemap = null;  // reference to treemap renderer inside buildCirclePacking

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
  document.getElementById('btnFunded').classList.toggle('active', mode === 'FUNDED');
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
  var minF = filters.minFunding;
  return DATA.companies.filter(function(c) {
    if (filters.geo === 'CA' && c.hq_state !== 'CA') return false;
    if (filters.geo === 'US' && c.country && c.country !== 'US') return false;
    if (filters.classification === 'CLASSIFIED' && c.category === 'UNKNOWN') return false;
    if (filters.classification === 'FUNDED' && !(c.funding > 0)) return false;
    if (minF > 0 && (c.funding || 0) < minF) return false;
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

  // Hide sidebar for sectors and detail views — give them full width
  var sidebar = document.querySelector('.sidebar');
  sidebar.style.display = (view === 'pack') ? '' : 'none';

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
    cb.dataset.category = s.category;

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
    if (node !== root) scale *= 2.2;
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
    updateSectorLabelVisibility(null);

    var zl = document.getElementById('zoom-label');
    var overlay = document.getElementById('pack-treemap-overlay');
    var packSvg = document.getElementById('pack-svg');
    var leftSidebar = packSvg.closest('#view-pack').querySelector('[data-pack-sidebar]');
    var methodology = document.getElementById('pack-methodology');

    if (node !== root && node.data && node.data.category) {
      zoomedCategory = node.data.category;
      zl.textContent = LABELS[zoomedCategory] || zoomedCategory;
      zl.classList.add('visible');

      // Hide circle packing + left sidebar, show full-width treemap
      packSvg.style.display = 'none';
      if (leftSidebar) leftSidebar.style.display = 'none';
      if (methodology) methodology.style.display = 'none';
      overlay.style.display = 'flex';
      renderPackTreemap(zoomedCategory);
    } else {
      zoomedCategory = null;
      zl.classList.remove('visible');

      // Restore circle packing + left sidebar
      overlay.style.display = 'none';
      overlay.innerHTML = '';
      packSvg.style.display = '';
      if (leftSidebar) leftSidebar.style.display = '';
      if (methodology) methodology.style.display = '';
    }
    updateSidebarForZoom();
  }

  function renderPackTreemap(category) {
    _renderPackTreemap = renderPackTreemap;  // expose for refresh()
    var overlay = document.getElementById('pack-treemap-overlay');
    overlay.innerHTML = '';

    // Back button
    var backBar = document.createElement('div');
    backBar.style.cssText = 'display:flex;align-items:center;gap:10px;padding:6px 10px;flex-shrink:0;';
    var backBtn = document.createElement('button');
    backBtn.className = 'back-btn';
    backBtn.innerHTML = '&#8592; Overview';
    backBtn.addEventListener('click', function() { zoomTo(root); });
    backBar.appendChild(backBtn);
    overlay.appendChild(backBar);

    var companies = getFiltered().filter(function(c) { return c.category === category; });
    if (!companies.length) return;

    // Wrapper div that flex-grows to fill remaining space
    var treemapWrap = document.createElement('div');
    treemapWrap.style.cssText = 'flex:1;min-height:0;overflow:hidden;';
    overlay.appendChild(treemapWrap);

    var W = treemapWrap.clientWidth || overlay.clientWidth || 800;
    var H = treemapWrap.clientHeight || (overlay.clientHeight - 40) || 500;
    var color = COLORS[category] || '#444';
    var tooltip = document.getElementById('tooltip');

    var treemapRoot = d3.hierarchy({
      name: 'root',
      children: companies.map(function(c) {
        return Object.assign({}, c, { value: Math.max(c.funding || 1, 1) });
      })
    })
      .sum(function(d) { return d.value; })
      .sort(function(a, b) { return b.value - a.value; });

    d3.treemap().size([W, H]).padding(3).round(true)(treemapRoot);

    var treeSvg = d3.select(treemapWrap).append('svg').attr('width', W).attr('height', H);

    var leaves = treeSvg.selectAll('.leaf').data(treemapRoot.leaves()).join('g')
      .attr('transform', function(d) { return 'translate(' + d.x0 + ',' + d.y0 + ')'; });

    leaves.append('rect')
      .attr('width', function(d) { return Math.max(d.x1 - d.x0, 0); })
      .attr('height', function(d) { return Math.max(d.y1 - d.y0, 0); })
      .attr('fill', color)
      .attr('rx', 3)
      .attr('stroke', '#2e2f31')
      .attr('stroke-width', 1)
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
      .on('dblclick', function(e, d) {
        var url = d.data.status === 'DEAD' ? safeUrl(d.data.wayback_url) : safeUrl(d.data.website);
        if (url) window.open(url, '_blank', 'noopener');
      });

    // Company name labels — fit to rectangle
    leaves.each(function(d) {
      var rectW = d.x1 - d.x0;
      var rectH = d.y1 - d.y0;
      if (rectW < 28 || rectH < 14) return;

      var name = d.data.name;
      var funding = d.data.funding > 0 ? fmt(d.data.funding) : '';
      var fontSize = Math.max(9, Math.min(16, Math.min(rectW / 8, rectH / 3)));

      var nameEl = d3.select(this).append('text')
        .attr('x', 5)
        .attr('y', fontSize + 3)
        .attr('font-size', fontSize + 'px')
        .attr('font-weight', '600')
        .attr('fill', '#fff')
        .attr('pointer-events', 'none')
        .style('text-shadow', '0 1px 3px rgba(0,0,0,0.9)');

      // Truncate name to fit
      var maxChars = Math.floor((rectW - 10) / (fontSize * 0.58));
      var label = name.length > maxChars ? name.slice(0, Math.max(maxChars - 1, 3)) + '\u2026' : name;
      nameEl.text(label);

      // Funding on second line if space
      if (funding && rectH > fontSize * 2 + 8) {
        d3.select(this).append('text')
          .attr('x', 5)
          .attr('y', fontSize * 2 + 5)
          .attr('font-size', Math.max(8, fontSize * 0.75) + 'px')
          .attr('fill', '#4ade80')
          .attr('pointer-events', 'none')
          .style('text-shadow', '0 1px 2px rgba(0,0,0,0.8)')
          .text(funding);
      }
    });

    // Click overlay background to zoom back out
    treeSvg.on('click', function(e) {
      if (e.target === treeSvg.node()) {
        tooltip.style.display = 'none';
        zoomTo(root);
      }
    });
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
      .on('mouseenter', function() {
        updateSectorLabelVisibility(sNode);
      })
      .on('mouseleave', function() {
        updateSectorLabelVisibility(null);
      })
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
      .attr('stroke', '#2e2f31')
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

  // Company name labels — disabled in circle view (treemap handles labels when zoomed)
  function updateCompanyLabels(scale) {}

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
    .attr('stroke', '#2e2f31')
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

  leaves.each(function(d) {
    var rectW = d.x1 - d.x0;
    var rectH = d.y1 - d.y0;
    if (rectW < 28 || rectH < 14) return;

    var name = d.data.name;
    var funding = d.data.funding > 0 ? fmt(d.data.funding) : '';
    var fontSize = Math.max(9, Math.min(16, Math.min(rectW / 8, rectH / 3)));

    var maxChars = Math.floor((rectW - 10) / (fontSize * 0.58));
    var label = name.length > maxChars ? name.slice(0, Math.max(maxChars - 1, 3)) + '\u2026' : name;

    d3.select(this).append('text')
      .attr('x', 5)
      .attr('y', fontSize + 3)
      .attr('font-size', fontSize + 'px')
      .attr('font-weight', '600')
      .attr('fill', '#fff')
      .attr('pointer-events', 'none')
      .style('text-shadow', '0 1px 3px rgba(0,0,0,0.9)')
      .text(label);

    if (funding && rectH > fontSize * 2 + 8) {
      d3.select(this).append('text')
        .attr('x', 5)
        .attr('y', fontSize * 2 + 5)
        .attr('font-size', Math.max(8, fontSize * 0.75) + 'px')
        .attr('fill', '#4ade80')
        .attr('pointer-events', 'none')
        .style('text-shadow', '0 1px 2px rgba(0,0,0,0.8)')
        .text(funding);
    }
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
// Sidebar + sector checks sync with zoom
// ─────────────────────────────────────────────
function updateSidebarForZoom() {
  var filtered = getFiltered();
  var sidebarLabel = document.getElementById('sidebar-label');
  var sidebarHeader = document.querySelector('.sidebar-header');
  if (zoomedCategory) {
    var sectorCompanies = filtered.filter(function(c) { return c.category === zoomedCategory; });
    sidebarLabel.textContent = LABELS[zoomedCategory] || zoomedCategory;
    sidebarHeader.style.color = '#e0e0e0';
    renderList(sectorCompanies);
    // Visually untick other sectors in the sidebar checkboxes
    document.querySelectorAll('.sector-check').forEach(function(row) {
      var cb = row.querySelector('input[type=checkbox]');
      var cat = cb ? cb.dataset.category : null;
      if (cat) {
        var isZoomed = cat === zoomedCategory;
        cb.checked = isZoomed;
        row.classList.toggle('excluded', !isZoomed);
      }
    });
  } else {
    sidebarLabel.textContent = 'Companies';
    sidebarHeader.style.color = '';
    renderList(filtered);
    // Restore checkboxes to match actual excludedSectors state
    document.querySelectorAll('.sector-check').forEach(function(row) {
      var cb = row.querySelector('input[type=checkbox]');
      var cat = cb ? cb.dataset.category : null;
      if (cat) {
        var isExcluded = excludedSectors.has(cat);
        cb.checked = !isExcluded;
        row.classList.toggle('excluded', isExcluded);
      }
    });
  }
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
    if (zoomedCategory && _renderPackTreemap) {
      // Zoomed into a sector — re-render treemap overlay, don't rebuild circles
      _renderPackTreemap(zoomedCategory);
      var zoomedCompanies = filtered.filter(function(c) { return c.category === zoomedCategory; });
      renderList(zoomedCompanies);
      document.getElementById('sidebar-label').textContent = LABELS[zoomedCategory] || zoomedCategory;
      document.querySelector('.sidebar-header').style.color = 'rgba(255,255,255,0.9)';
    } else {
      buildCirclePacking(filtered);
      renderList(filtered);
      document.getElementById('sidebar-label').textContent = 'Companies';
      document.querySelector('.sidebar-header').style.color = '';
    }
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

// Funding slider
var fundingSlider = document.getElementById('funding-slider');
var fundingLabel = document.getElementById('funding-slider-label');
fundingSlider.addEventListener('input', function() {
  var idx = parseInt(fundingSlider.value);
  filters.minFunding = FUNDING_STEPS[idx];
  fundingLabel.textContent = idx === 0 ? 'Any' : fmt(FUNDING_STEPS[idx]) + '+';
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
