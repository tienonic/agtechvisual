/*! Research explorer city view, v1. Original WebGL 2 code with no third-party
 *  dependencies. Loaded on demand by explorer.js. Footprints are the treemap
 *  rectangles exactly as supplied; the renderer never recomputes a layout. */
(function (root) {
  'use strict';

  const now = () => (root.performance ? root.performance.now() : Date.now());
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const FOV = 38 * Math.PI / 180;

  const BOX_VS = `#version 300 es
layout(location=0) in vec3 a_pos;
layout(location=1) in vec3 a_nrm;
layout(location=2) in vec4 a_rect;
layout(location=3) in vec2 a_yh;
layout(location=4) in vec4 a_col;
uniform mat4 u_vp;
uniform float u_gap;
out vec3 v_col;
out vec3 v_nrm;
out float v_up;
void main() {
  float g = min(u_gap, 0.18 * min(a_rect.z, a_rect.w));
  vec3 p = vec3(a_rect.x + g + a_pos.x * max(a_rect.z - 2.0 * g, 0.0),
                a_yh.x + a_pos.y * a_yh.y,
                a_rect.y + g + a_pos.z * max(a_rect.w - 2.0 * g, 0.0));
  v_col = a_col.rgb;
  v_nrm = a_nrm;
  v_up = a_pos.y;
  gl_Position = u_vp * vec4(p, 1.0);
}`;
  const BOX_FS = `#version 300 es
precision mediump float;
in vec3 v_col;
in vec3 v_nrm;
in float v_up;
uniform vec3 u_light;
uniform float u_ambient;
out vec4 o;
void main() {
  float d = max(dot(normalize(v_nrm), u_light), 0.0);
  vec3 c = v_col * (u_ambient + (1.0 - u_ambient) * d);
  c *= mix(0.9, 1.0, v_up);
  o = vec4(c, 1.0);
}`;
  const LINE_VS = `#version 300 es
layout(location=0) in vec3 a_p;
layout(location=1) in vec4 a_c;
uniform mat4 u_vp;
out vec4 v_c;
void main() { v_c = a_c; gl_Position = u_vp * vec4(a_p, 1.0); }`;
  const LINE_FS = `#version 300 es
precision mediump float;
in vec4 v_c;
out vec4 o;
void main() { o = v_c; }`;

  // Unit box without a bottom face; counter-clockwise from outside.
  function boxGeometry() {
    const faces = [
      [[0, 1, 0], [0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]],
      [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]],
      [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, -1]],
      [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1], [1, 0, 0]],
      [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0], [-1, 0, 0]]
    ];
    const v = [], idx = [];
    faces.forEach((f, q) => {
      for (let k = 0; k < 4; k++) v.push(f[k][0], f[k][1], f[k][2], f[4][0], f[4][1], f[4][2]);
      const b = q * 4;
      idx.push(b, b + 1, b + 2, b, b + 2, b + 3);
    });
    return { verts: new Float32Array(v), index: new Uint16Array(idx), count: idx.length };
  }

  // ---- small matrix helpers (column-major, OpenGL conventions)
  function perspective(out, fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
    out.fill(0);
    out[0] = f / aspect; out[5] = f; out[10] = (far + near) * nf; out[11] = -1; out[14] = 2 * far * near * nf;
    return out;
  }
  function basis(eye, center) {
    let zx = eye[0] - center[0], zy = eye[1] - center[1], zz = eye[2] - center[2];
    let l = Math.hypot(zx, zy, zz) || 1; zx /= l; zy /= l; zz /= l;
    // x = up(0,1,0) × z
    let xx = zz, xy = 0, xz = -zx;
    l = Math.hypot(xx, xy, xz) || 1; xx /= l; xz /= l;
    const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
    return { x: [xx, xy, xz], y: [yx, yy, yz], z: [zx, zy, zz] };
  }
  function lookAt(out, eye, b) {
    const { x, y, z } = b;
    out[0] = x[0]; out[1] = y[0]; out[2] = z[0]; out[3] = 0;
    out[4] = x[1]; out[5] = y[1]; out[6] = z[1]; out[7] = 0;
    out[8] = x[2]; out[9] = y[2]; out[10] = z[2]; out[11] = 0;
    out[12] = -(x[0] * eye[0] + x[1] * eye[1] + x[2] * eye[2]);
    out[13] = -(y[0] * eye[0] + y[1] * eye[1] + y[2] * eye[2]);
    out[14] = -(z[0] * eye[0] + z[1] * eye[1] + z[2] * eye[2]);
    out[15] = 1;
    return out;
  }
  function multiply(out, a, b) {
    for (let c = 0; c < 4; c++) {
      for (let r = 0; r < 4; r++) {
        out[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1] + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
    }
    return out;
  }

  function compile(gl, vs, fs) {
    const make = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'Shader failed to compile.');
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, make(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, make(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || 'Shader failed to link.');
    return p;
  }

  function create(canvas, hooks) {
    hooks = hooks || {};
    const gl = canvas.getContext('webgl2', { antialias: true, alpha: false, powerPreference: 'high-performance' });
    if (!gl) return null;

    let res = null;           // GPU resources
    let scene = null;         // last scene, kept for context restore and picking
    let links = { pairs: new Int32Array(0), styles: new Uint8Array(0) };
    let linkVerts = 0;
    let theme = { bg: [0.95, 0.95, 0.93], surface: [1, 1, 1], line: [0.88, 0.88, 0.85], edge: [[0.18, 0.31, 0.6], [0.76, 0.38, 0.1], [0.55, 0.54, 0.52]] };
    let w = 0, h = 0, dpr = 1, raf = 0, lost = false, anim = 0;
    const cam = { tx: 600, tz: 400, yaw: -0.45, pitch: 0.82, dist: 1500 };
    const proj = new Float32Array(16), view = new Float32Array(16), vp = new Float32Array(16);
    let eye = [0, 0, 0], camBasis = null;
    const samples = [];
    const labelEls = [];

    function init() {
      const geo = boxGeometry();
      const box = compile(gl, BOX_VS, BOX_FS);
      const line = compile(gl, LINE_VS, LINE_FS);
      const cube = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, cube); gl.bufferData(gl.ARRAY_BUFFER, geo.verts, gl.STATIC_DRAW);
      const ibo = gl.createBuffer();
      const mkVao = () => {
        const vao = gl.createVertexArray();
        gl.bindVertexArray(vao);
        gl.bindBuffer(gl.ARRAY_BUFFER, cube);
        gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 24, 0);
        gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 24, 12);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
        const rect = gl.createBuffer(), yh = gl.createBuffer(), col = gl.createBuffer();
        const inst = (loc, buf, size) => {
          gl.bindBuffer(gl.ARRAY_BUFFER, buf);
          gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
          gl.vertexAttribDivisor(loc, 1);
        };
        inst(2, rect, 4); inst(3, yh, 2); inst(4, col, 4);
        gl.bindVertexArray(null);
        return { vao, rect, yh, col, count: 0 };
      };
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, geo.index, gl.STATIC_DRAW);
      const lineVao = gl.createVertexArray(), lineBuf = gl.createBuffer();
      gl.bindVertexArray(lineVao);
      gl.bindBuffer(gl.ARRAY_BUFFER, lineBuf);
      gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 28, 0);
      gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 28, 12);
      gl.bindVertexArray(null);
      res = {
        box, line, geoCount: geo.count, buildings: mkVao(), plates: mkVao(), lineVao, lineBuf,
        u: {
          vp: gl.getUniformLocation(box, 'u_vp'), gap: gl.getUniformLocation(box, 'u_gap'),
          light: gl.getUniformLocation(box, 'u_light'), ambient: gl.getUniformLocation(box, 'u_ambient'),
          lvp: gl.getUniformLocation(line, 'u_vp')
        }
      };
    }
    init();

    canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); lost = true; res = null; if (hooks.onLost) hooks.onLost(); });
    canvas.addEventListener('webglcontextrestored', () => {
      lost = false; init();
      if (scene) upload(scene);
      if (hooks.onRestored) hooks.onRestored();
    });

    function upload(s) {
      const B = res.buildings, P = res.plates;
      gl.bindBuffer(gl.ARRAY_BUFFER, B.rect); gl.bufferData(gl.ARRAY_BUFFER, s.rects, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, B.yh); gl.bufferData(gl.ARRAY_BUFFER, s.yh, gl.DYNAMIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, B.col); gl.bufferData(gl.ARRAY_BUFFER, s.colors, gl.DYNAMIC_DRAW);
      B.count = s.rects.length / 4;
      const m = s.frameLevels.length;
      const pyh = new Float32Array(m * 2);
      for (let q = 0; q < m; q++) { pyh[q * 2] = s.frameLevels[q] * 0.6; pyh[q * 2 + 1] = 0.6; }
      gl.bindBuffer(gl.ARRAY_BUFFER, P.rect); gl.bufferData(gl.ARRAY_BUFFER, s.frames, gl.STATIC_DRAW);
      gl.bindBuffer(gl.ARRAY_BUFFER, P.yh); gl.bufferData(gl.ARRAY_BUFFER, pyh, gl.STATIC_DRAW);
      P.count = m;
      uploadPlateColors();
      buildLinks();
    }
    function uploadPlateColors() {
      if (!scene || !res) return;
      const m = scene.frameLevels.length, out = new Float32Array(m * 4);
      for (let q = 0; q < m; q++) {
        const t = [0.0, 0.45, 0.75][scene.frameLevels[q]] || 0.75;
        const s = theme.surface, l = theme.line;
        out[q * 4] = s[0] + (l[0] - s[0]) * t; out[q * 4 + 1] = s[1] + (l[1] - s[1]) * t; out[q * 4 + 2] = s[2] + (l[2] - s[2]) * t; out[q * 4 + 3] = 1;
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, res.plates.col); gl.bufferData(gl.ARRAY_BUFFER, out, gl.STATIC_DRAW);
    }

    function buildLinks() {
      if (!scene || !res) return;
      const pairs = links.pairs, styles = links.styles;
      const count = Math.min(styles.length, 1500), SEG = 20;
      const data = new Float32Array(count * SEG * 2 * 7);
      const R = scene.rects, YH = scene.yh;
      let p = 0;
      const top = (i) => [R[i * 4] + R[i * 4 + 2] / 2, YH[i * 2] + YH[i * 2 + 1] + 0.5, R[i * 4 + 1] + R[i * 4 + 3] / 2];
      for (let q = 0; q < count; q++) {
        const a = top(pairs[q * 2]), b = top(pairs[q * 2 + 1]);
        const span = Math.hypot(b[0] - a[0], b[2] - a[2]);
        const lift = span * 0.22 + 6;
        const st = styles[q], c = theme.edge[st] || theme.edge[0];
        const at = (u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u + Math.sin(Math.PI * u) * lift, a[2] + (b[2] - a[2]) * u];
        for (let s = 0; s < SEG; s++) {
          if (st === 1 && s % 2 === 1) continue;  // inferred: dashed
          if (st === 2 && s % 3 !== 0) continue;  // evidence not stated: dotted
          const u0 = at(s / SEG), u1 = at((s + 1) / SEG);
          for (const v of [u0, u1]) { data[p++] = v[0]; data[p++] = v[1]; data[p++] = v[2]; data[p++] = c[0]; data[p++] = c[1]; data[p++] = c[2]; data[p++] = 0.95; }
        }
      }
      linkVerts = p / 7;
      gl.bindBuffer(gl.ARRAY_BUFFER, res.lineBuf);
      gl.bufferData(gl.ARRAY_BUFFER, data.subarray(0, p), gl.DYNAMIC_DRAW);
    }

    // ---- camera
    function updateCamera() {
      const cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
      eye = [cam.tx + cam.dist * cp * Math.sin(cam.yaw), cam.dist * sp, cam.tz + cam.dist * cp * Math.cos(cam.yaw)];
      camBasis = basis(eye, [cam.tx, 0, cam.tz]);
      const diag = scene ? Math.hypot(scene.W, scene.H) : 1500;
      perspective(proj, FOV, w / Math.max(h, 1), Math.max(0.5, cam.dist * 0.01), cam.dist * 2 + diag * 2 + 600);
      lookAt(view, eye, camBasis);
      multiply(vp, proj, view);
    }
    function distLimits() {
      const diag = scene ? Math.hypot(scene.W, scene.H) : 1500;
      return [4, diag * 5];
    }
    function setCam(next, animate) {
      cancelAnimationFrame(anim); anim = 0;
      if (!animate || (hooks.reducedMotion && hooks.reducedMotion())) { Object.assign(cam, next); requestRender(); return; }
      const from = Object.assign({}, cam), t0 = now(), dur = 260;
      const step = () => {
        const p = Math.min(1, (now() - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        for (const k of Object.keys(next)) cam[k] = k === 'dist' ? Math.exp(Math.log(from[k]) + (Math.log(next[k]) - Math.log(from[k])) * e) : from[k] + (next[k] - from[k]) * e;
        render();
        anim = p < 1 ? requestAnimationFrame(step) : 0;
      };
      anim = requestAnimationFrame(step);
    }
    function fitRect(x, y, rw, rh, animate) {
      const aspect = w / Math.max(h, 1) || 1.5;
      const half = Math.min(FOV / 2, Math.atan(Math.tan(FOV / 2) * aspect));
      const radius = 0.5 * Math.hypot(rw, rh);
      const [dmin, dmax] = distLimits();
      setCam({ tx: x + rw / 2, tz: y + rh / 2, dist: clamp((radius / Math.sin(half)) * 0.95, dmin, dmax) }, animate !== false);
    }

    // ---- input
    const pointers = new Map();
    let drag = null, pinch = null, hoverRaf = 0, hoverAt = null;
    canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    canvas.addEventListener('pointerdown', (e) => {
      canvas.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      const pan = e.button === 2 || e.button === 1 || e.shiftKey || e.ctrlKey || e.metaKey;
      if (pointers.size === 1) drag = { sx: e.clientX, sy: e.clientY, lx: e.clientX, ly: e.clientY, moved: false, pan, button: e.button };
      else if (pointers.size === 2) {
        const [a, b] = [...pointers.values()];
        pinch = { dist: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 };
        if (drag) drag.moved = true;
      }
    });
    canvas.addEventListener('pointermove', (e) => {
      const p = pointers.get(e.pointerId);
      if (!p) {
        if (e.pointerType === 'mouse') {
          hoverAt = { x: e.clientX, y: e.clientY };
          if (!hoverRaf) hoverRaf = requestAnimationFrame(() => {
            hoverRaf = 0;
            if (!hoverAt || !hooks.onHover) return;
            const r = canvas.getBoundingClientRect();
            hooks.onHover(pick(hoverAt.x - r.left, hoverAt.y - r.top), hoverAt.x, hoverAt.y);
          });
        }
        return;
      }
      p.x = e.clientX; p.y = e.clientY;
      if (pointers.size >= 2 && pinch) {
        const [a, b] = [...pointers.values()];
        const d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
        panBy(mx - pinch.mx, my - pinch.my);
        if (pinch.dist > 0 && d > 0) zoomAt(mx, my, d / pinch.dist);
        pinch = { dist: d, mx, my };
        return;
      }
      if (!drag) return;
      const dx = e.clientX - drag.lx, dy = e.clientY - drag.ly;
      if (!drag.moved && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 4) {
        drag.moved = true; canvas.classList.add('is-dragging');
        if (hooks.onHover) hooks.onHover(-1, 0, 0);
      }
      if (drag.moved) {
        if (drag.pan) panBy(dx, dy);
        else rotate(-dx * 0.006, dy * 0.005);
      }
      drag.lx = e.clientX; drag.ly = e.clientY;
    });
    const end = (e, cancelled) => {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinch = null;
      if (!pointers.size) {
        if (drag && !drag.moved && !cancelled && drag.button === 0 && hooks.onPick) {
          const r = canvas.getBoundingClientRect();
          hooks.onPick(pick(e.clientX - r.left, e.clientY - r.top), e);
        }
        drag = null;
        canvas.classList.remove('is-dragging');
      }
    };
    canvas.addEventListener('pointerup', (e) => end(e, false));
    canvas.addEventListener('pointercancel', (e) => end(e, true));
    canvas.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !pointers.size) { hoverAt = null; if (hooks.onHover) hooks.onHover(-1, 0, 0); } });
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      zoomAt(e.clientX, e.clientY, Math.exp(-dy * (e.ctrlKey ? 0.01 : 0.0018)));
    }, { passive: false });

    function rotate(dYaw, dPitch) {
      cancelAnimationFrame(anim); anim = 0;
      cam.yaw += dYaw;
      cam.pitch = clamp(cam.pitch + dPitch, 0.14, 1.52);
      requestRender();
    }
    function panBy(dx, dy) {
      cancelAnimationFrame(anim); anim = 0;
      const per = (2 * cam.dist * Math.tan(FOV / 2)) / Math.max(h, 1);
      const sy = Math.sin(cam.yaw), cy = Math.cos(cam.yaw);
      const vert = per / Math.max(Math.sin(cam.pitch), 0.3);
      cam.tx -= cy * dx * per + sy * dy * vert;
      cam.tz -= -sy * dx * per + cy * dy * vert;
      requestRender();
    }
    function rayAt(sx, sy) {
      updateCamera();
      const nx = (sx / Math.max(w, 1)) * 2 - 1, ny = 1 - (sy / Math.max(h, 1)) * 2;
      const t = Math.tan(FOV / 2), aspect = w / Math.max(h, 1);
      const { x, y, z } = camBasis;
      const d = [-z[0] + x[0] * nx * t * aspect + y[0] * ny * t, -z[1] + x[1] * nx * t * aspect + y[1] * ny * t, -z[2] + x[2] * nx * t * aspect + y[2] * ny * t];
      const l = Math.hypot(d[0], d[1], d[2]) || 1;
      return { o: eye.slice(), d: [d[0] / l, d[1] / l, d[2] / l] };
    }
    function zoomAt(clientX, clientY, f) {
      cancelAnimationFrame(anim); anim = 0;
      const r = canvas.getBoundingClientRect();
      const ray = rayAt(clientX - r.left, clientY - r.top);
      const [dmin, dmax] = distLimits();
      const nd = clamp(cam.dist / f, dmin, dmax);
      if (ray.d[1] < -1e-4) {
        const t = -ray.o[1] / ray.d[1];
        const px = ray.o[0] + ray.d[0] * t, pz = ray.o[2] + ray.d[2] * t;
        const k = 1 - nd / cam.dist;
        cam.tx += (px - cam.tx) * k; cam.tz += (pz - cam.tz) * k;
      }
      cam.dist = nd;
      requestRender();
    }

    /** Nearest building hit by the ray through canvas point (sx, sy). */
    function pick(sx, sy) {
      if (!scene) return -1;
      const ray = rayAt(sx, sy);
      const [ox, oy, oz] = ray.o;
      const ix = 1 / (ray.d[0] || 1e-12), iy = 1 / (ray.d[1] || 1e-12), iz = 1 / (ray.d[2] || 1e-12);
      const R = scene.rects, YH = scene.yh, n = R.length / 4;
      let best = -1, bestT = Infinity;
      for (let i = 0; i < n; i++) {
        const o = i * 4;
        let t1 = (R[o] - ox) * ix, t2 = (R[o] + R[o + 2] - ox) * ix;
        let tmin = t1 < t2 ? t1 : t2, tmax = t1 < t2 ? t2 : t1;
        const base = YH[i * 2];
        t1 = (base - oy) * iy; t2 = (base + YH[i * 2 + 1] - oy) * iy;
        tmin = Math.max(tmin, t1 < t2 ? t1 : t2); tmax = Math.min(tmax, t1 < t2 ? t2 : t1);
        if (tmin > tmax) continue;
        t1 = (R[o + 1] - oz) * iz; t2 = (R[o + 1] + R[o + 3] - oz) * iz;
        tmin = Math.max(tmin, t1 < t2 ? t1 : t2); tmax = Math.min(tmax, t1 < t2 ? t2 : t1);
        if (tmin > tmax || tmax < 0) continue;
        const t = tmin >= 0 ? tmin : tmax;
        if (t < bestT) { bestT = t; best = i; }
      }
      return best;
    }

    function project(x, y, z) {
      const cx = vp[0] * x + vp[4] * y + vp[8] * z + vp[12];
      const cy = vp[1] * x + vp[5] * y + vp[9] * z + vp[13];
      const cw = vp[3] * x + vp[7] * y + vp[11] * z + vp[15];
      if (cw <= 0) return null;
      return [(cx / cw * 0.5 + 0.5) * w, (1 - (cy / cw * 0.5 + 0.5)) * h];
    }

    // ---- drawing
    function resize() {
      const r = canvas.getBoundingClientRect();
      const nd = Math.min(root.devicePixelRatio || 1, 2);
      const nw = Math.round(r.width), nh = Math.round(r.height);
      if (!nw || !nh) return;
      if (nw === w && nh === h && nd === dpr) return;
      w = nw; h = nh; dpr = nd;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      requestRender();
    }
    function requestRender() { if (!raf) raf = requestAnimationFrame(render); }
    function render() {
      raf = 0;
      if (lost || !res || canvas.hidden) return;
      if (!w) resize();
      if (!w) return;
      const t0 = now();
      updateCamera();
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(theme.bg[0], theme.bg[1], theme.bg[2], 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (scene) {
        gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK);
        gl.useProgram(res.box);
        gl.uniformMatrix4fv(res.u.vp, false, vp);
        gl.uniform3f(res.u.light, -0.34, 0.86, 0.38);
        gl.uniform1f(res.u.ambient, theme.dark ? 0.58 : 0.64);
        gl.uniform1f(res.u.gap, 0);
        gl.bindVertexArray(res.plates.vao);
        gl.drawElementsInstanced(gl.TRIANGLES, res.geoCount, gl.UNSIGNED_SHORT, 0, res.plates.count);
        gl.uniform1f(res.u.gap, 0.3);
        gl.bindVertexArray(res.buildings.vao);
        gl.drawElementsInstanced(gl.TRIANGLES, res.geoCount, gl.UNSIGNED_SHORT, 0, res.buildings.count);
        if (linkVerts) {
          gl.disable(gl.DEPTH_TEST);
          gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.useProgram(res.line);
          gl.uniformMatrix4fv(res.u.lvp, false, vp);
          gl.bindVertexArray(res.lineVao);
          gl.drawArrays(gl.LINES, 0, linkVerts);
          gl.disable(gl.BLEND);
        }
        gl.bindVertexArray(null);
        placeLabels();
      }
      const ms = now() - t0;
      samples.push(ms); if (samples.length > 60) samples.shift();
      if (hooks.onFrame) hooks.onFrame({ ms, avg: samples.reduce((a, b) => a + b, 0) / samples.length });
    }
    function placeLabels() {
      for (let q = 0; q < labelEls.length; q++) {
        const L = scene.labels[q], node = labelEls[q];
        const p = project(L.x, L.y, L.z);
        if (!p || p[0] < -40 || p[1] < -20 || p[0] > w || p[1] > h) { node.style.visibility = 'hidden'; continue; }
        node.style.visibility = 'visible';
        node.style.transform = 'translate(' + Math.round(p[0]) + 'px,' + Math.round(p[1] - 18) + 'px)';
      }
    }
    function buildLabels() {
      const box = hooks.labels;
      if (!box) return;
      box.replaceChildren();
      labelEls.length = 0;
      for (const L of scene.labels || []) {
        const span = document.createElement('span');
        span.className = 'city-label';
        span.textContent = L.text;
        box.appendChild(span);
        labelEls.push(span);
      }
    }

    // ---- public API
    const api = {
      setScene(s) {
        // Keep a private copy of exactly what is uploaded, so tests can compare it with the layout.
        scene = Object.assign({}, s, { rects: new Float32Array(s.rects), yh: new Float32Array(s.yh), colors: new Float32Array(s.colors), ids: s.ids.slice() });
        if (res) upload(scene);
        buildLabels();
        requestRender();
      },
      setColors(c) {
        if (!scene) return;
        scene.colors = new Float32Array(c);
        if (res) { gl.bindBuffer(gl.ARRAY_BUFFER, res.buildings.col); gl.bufferData(gl.ARRAY_BUFFER, scene.colors, gl.DYNAMIC_DRAW); }
        requestRender();
      },
      setHeights(yh) {
        if (!scene) return;
        scene.yh = new Float32Array(yh);
        if (res) { gl.bindBuffer(gl.ARRAY_BUFFER, res.buildings.yh); gl.bufferData(gl.ARRAY_BUFFER, scene.yh, gl.DYNAMIC_DRAW); buildLinks(); }
        requestRender();
      },
      setLinks(l) { links = l || { pairs: new Int32Array(0), styles: new Uint8Array(0) }; buildLinks(); requestRender(); },
      setTheme(t) { theme = Object.assign({}, theme, t); uploadPlateColors(); buildLinks(); requestRender(); },
      resize, requestRender, render,
      fit() { if (scene) fitRect(0, 0, scene.W, scene.H, false); },
      fitRect(x, y, rw, rh) { fitRect(x, y, rw, rh, true); },
      zoomBy(f) { const r = canvas.getBoundingClientRect(); zoomAt(r.left + r.width / 2, r.top + r.height / 2, f); },
      rotate,
      focus(i, zoom) {
        if (!scene || i < 0) return;
        const R = scene.rects, o = i * 4;
        const cx = R[o] + R[o + 2] / 2, cz = R[o + 1] + R[o + 3] / 2;
        if (!zoom) {
          updateCamera();
          const p = project(cx, scene.yh[i * 2] + scene.yh[i * 2 + 1], cz);
          if (p && p[0] > w * 0.12 && p[0] < w * 0.88 && p[1] > h * 0.12 && p[1] < h * 0.88) return;
          setCam({ tx: cx, tz: cz }, false);
          return;
        }
        const span = Math.max(R[o + 2], R[o + 3]) * 14 + 60;
        const [dmin, dmax] = distLimits();
        setCam({ tx: cx, tz: cz, dist: clamp(Math.min(cam.dist, span), dmin, dmax) }, true);
      },
      target() { return [cam.tx, cam.tz]; },
      screenDirToWorld(dx, dy) {
        const s = Math.sin(cam.yaw), c = Math.cos(cam.yaw);
        return [dx * c + dy * s, -dx * s + dy * c];
      },
      camera() { return { yaw: cam.yaw, pitch: cam.pitch, dist: cam.dist, target: [cam.tx, cam.tz] }; },
      pick,
      ids() { return scene ? scene.ids.slice() : []; },
      footprintBuffer() { return scene ? new Float32Array(scene.rects) : null; },
      footprints(limit) {
        if (!scene) return [];
        const n = Math.min(scene.rects.length / 4, limit == null ? 200 : limit), out = [];
        for (let i = 0; i < n; i++) {
          const o = i * 4;
          out.push({ id: scene.ids[i], x: scene.rects[o], z: scene.rects[o + 1], w: scene.rects[o + 2], d: scene.rects[o + 3], base: scene.yh[i * 2], height: scene.yh[i * 2 + 1] });
        }
        return out;
      },
      destroy() {
        cancelAnimationFrame(raf); cancelAnimationFrame(anim);
        const ext = gl.getExtension('WEBGL_lose_context');
        if (ext) ext.loseContext();
      }
    };
    return api;
  }

  root.ExplorerCity = Object.freeze({ create, version: '1.0.0' });
})(typeof globalThis !== 'undefined' ? globalThis : this);
