/* 3d.js — Web 版 3D 地图模式（three.js r128，本地 vendor，无外部依赖）
 *
 * 数据：/api/map 提供房间 2D 轮廓 + z、门、楼梯、点位；/api/3d 提供 map3d.py
 *       从 paks 提取的家具/道具占位盒与房间 3D 体块（可选，缺失时只画基础体量）。
 * 坐标：UE 是 Z-up，three.js 是 Y-up。为了让 3D 俯视和 2D 地图朝向一致，
 *       world(x,y,z) -> three(fx*x, z, -fy*y)，fx/fy 就是 2D 视图的镜像符号；
 *       UE yaw -> three rotation.y = fx*fy*yaw。
 * 交互：左键拖动旋转、右键拖动平移、滚轮缩放、单击查看、双击聚焦、D 回 2D。
 */
(() => {
  'use strict';
  const T = window.THREE;
  const NOOP = () => {};
  if (!T) {
    console.error('[3D] three.js 未加载');
    window.Map3D = { available: false, init: NOOP, load: NOOP, resize: NOOP,
                     setActive: NOOP, resetView: NOOP, rotate: NOOP, setView: NOOP };
    return;
  }

  const CAT_COLORS = {
    desk: '#b98a55', table: '#c39a63', chair: '#8a8f98', bench: '#a07a52',
    sofa: '#8f6f78', bed: '#a6a2b8', cabinet: '#7d8b74', box: '#a9793f',
    books: '#7b93a8', column: '#c9c4b4', statue: '#b0a89a', barrel: '#6f8d7a',
    machine: '#6b8396', screen: '#4d6b86', projector: '#8d6a9c', cart: '#8b8069',
    sink: '#9aa5a7', safe: '#716f80', divider: '#8c8c8c', misc: '#8d8b84',
    wall: '#8d97a5', structure: '#9aa2ab',
  };
  const DOOR_COLORS = {
    spawn: '#ef4444', normal: '#8b5cf6', rolling: '#3b82f6', sliding: '#06b6d4',
    access: '#f59e0b', backdrop: '#64748b', other: '#94a3b8',
  };
  const LAYERS = ['rooms', 'walls', 'solids', 'doors', 'stairs',
                  'props', 'structures', 'points', 'markers'];

  let app = null;
  let canvas, mapCanvas, container, panel, labelLayer, tip, badge;
  let renderer = null, scene = null, camera = null, raycaster = null;
  let ready = false, active = false, raf = null;
  let db = null, d3 = null, level = null;
  let fx = -1, fy = 1;
  let root = null, groups = {}, pickables = [], labels = [];
  let labelDirty = true, markerSig = '', zoneSig = '', floorSig = '', themeDark = null;
  let lastLevel = null, pendingView = null;
  const cam = { theta: 0.0, phi: 0.86, radius: 12000, target: new T.Vector3() };
  const cfg = {
    walls: 'low', props: true, structures: false, solids: false,
    labels: false, onlyFloor: false, rooms: true, view: 'iso',
  };

  // ------------------------------------------------------------------ 坐标
  function P(x, y, z) { return [fx * x, z, -fy * y]; }
  function rotY(yawDeg) { return fx * fy * (yawDeg || 0) * Math.PI / 180; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function shade(hex, k) {
    const c = new T.Color(hex || '#8892a0');
    c.multiplyScalar(k);
    return c;
  }
  function zoneColor(zid) {
    const z = (db?.zones || []).find(q => q.id === zid);
    return z ? z.color : '#7b8794';
  }
  function floorOfZ(z) {
    const fs = db?.floors || [];
    if (!fs.length) return 0;
    let best = 0, dist = Infinity;
    fs.forEach((f, i) => {
      const d = Math.abs((f.level ?? 0) - z);
      if (d < dist) { dist = d; best = i; }
    });
    return best;
  }
  function allowedFloor(z) {
    return !cfg.onlyFloor || floorOfZ(z) === (app.state.floor || 0);
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // ------------------------------------------------------------------ 初始化
  function init(bridge) {
    app = bridge;
    canvas = document.getElementById('map3dCanvas');
    mapCanvas = document.getElementById('mapCanvas');
    container = document.getElementById('mapContainer');
    badge = document.getElementById('viewBadge');
    if (!canvas || !container) return;

    try {
      renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: false });
    } catch (e) {
      console.error('[3D] WebGL 初始化失败', e);
      window.Map3D.available = false;
      app.showToast('本环境不支持 WebGL，3D 模式不可用');
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    scene = new T.Scene();
    scene.background = new T.Color('#e9eef5');
    camera = new T.PerspectiveCamera(48, 1, 5, 300000);
    raycaster = new T.Raycaster();
    scene.add(new T.HemisphereLight(0xffffff, 0x50606f, 0.9));
    const sun = new T.DirectionalLight(0xffffff, 0.55);
    sun.position.set(0.4, 1, 0.55);
    scene.add(sun);

    buildPanel();
    buildOverlays();
    bindEvents();
    resize();
    ready = true;
    window.Map3D.available = true;
  }

  function buildOverlays() {
    labelLayer = document.createElement('div');
    labelLayer.id = 'map3dLabels';
    container.appendChild(labelLayer);

    tip = document.createElement('div');
    tip.id = 'map3dTooltip';
    tip.className = 'hover-tooltip hidden';
    container.appendChild(tip);
  }

  function buildPanel() {
    panel = document.createElement('div');
    panel.id = 'map3dPanel';
    panel.className = 'map3d-panel hidden';
    panel.innerHTML = `
      <div class="map3d-head"><strong>3D 视图</strong><span id="map3dInfo"></span></div>
      <div class="map3d-row">
        <span class="map3d-key">视角</span>
        <button data-view="top">俯视</button>
        <button data-view="iso" class="active">斜视</button>
        <button data-view="side">平视</button>
        <button data-act="reset" title="复位相机 (F)">复位</button>
      </div>
      <div class="map3d-row">
        <span class="map3d-key">墙体</span>
        <button data-walls="none">无</button>
        <button data-walls="low" class="active">矮墙</button>
        <button data-walls="full">全高</button>
      </div>
      <div class="map3d-row map3d-checks">
        <label><input type="checkbox" id="d3Props" checked> 家具道具</label>
        <label><input type="checkbox" id="d3Struct"> 原始墙体</label>
        <label><input type="checkbox" id="d3Solids"> 房间体块</label>
        <label><input type="checkbox" id="d3Labels"> 房间名</label>
        <label><input type="checkbox" id="d3Floor"> 仅本层</label>
      </div>
      <div class="map3d-hint">左键拖动旋转 · 右键拖动平移 · 滚轮缩放<br>
        单击查看物体 · 双击聚焦 · <b>D</b> 返回 2D · <b>F</b> 复位</div>`;
    container.appendChild(panel);

    panel.querySelectorAll('[data-view]').forEach(b => {
      b.addEventListener('click', () => setView(b.dataset.view));
    });
    panel.querySelectorAll('[data-walls]').forEach(b => {
      b.addEventListener('click', () => {
        cfg.walls = b.dataset.walls;
        syncPanel();
        build(true);
      });
    });
    panel.querySelector('[data-act="reset"]').addEventListener('click', () => resetView());
    const binds = {
      d3Props: v => { cfg.props = v; applyLayers(); },
      d3Struct: v => { cfg.structures = v; applyLayers(); },
      d3Solids: v => { cfg.solids = v; applyLayers(); },
      d3Labels: v => { cfg.labels = v; labelDirty = true; applyLayers(); },
      d3Floor: v => { cfg.onlyFloor = v; build(true); },
    };
    Object.entries(binds).forEach(([id, fn]) => {
      const el = panel.querySelector('#' + id);
      el.addEventListener('change', () => fn(el.checked));
    });
  }

  function syncPanel() {
    if (!panel) return;
    panel.querySelectorAll('[data-view]').forEach(b =>
      b.classList.toggle('active', b.dataset.view === cfg.view));
    panel.querySelectorAll('[data-walls]').forEach(b =>
      b.classList.toggle('active', b.dataset.walls === cfg.walls));
    const info = panel.querySelector('#map3dInfo');
    if (info) {
      info.textContent = `${(d3?.props || []).length} 道具 · ${(db?.rooms || []).length} 房间`;
    }
  }

  // ------------------------------------------------------------------ 几何工具
  function disposeRoot() {
    if (!root) return;
    scene.remove(root);
    root.traverse(o => {
      if (o.geometry) o.geometry.dispose();
      const m = o.material;
      if (m) (Array.isArray(m) ? m : [m]).forEach(x => x.dispose());
    });
    root = null;
    if (labelLayer) labelLayer.innerHTML = '';
    labels = [];
    pickables = [];
  }

  /** 一组占位盒：一个 InstancedMesh，逐实例颜色；p 是底面中心（UE 世界坐标）。 */
  function boxInstances(group, items, kind, opts = {}) {
    if (!items.length) return null;
    const geo = new T.BoxGeometry(1, 1, 1);
    const opacity = opts.opacity ?? 1;
    const mat = new T.MeshLambertMaterial({
      color: 0xffffff, side: T.DoubleSide,
      transparent: opacity < 1, opacity,
      depthWrite: opacity >= 1,
    });
    const mesh = new T.InstancedMesh(geo, mat, items.length);
    const dummy = new T.Object3D();
    const col = new T.Color();
    const ids = [];
    items.forEach((it, i) => {
      const [x, y, z] = P(it.p[0], it.p[1], it.p[2]);
      dummy.position.set(x, y + it.size[2] / 2, z);
      dummy.rotation.set(0, rotY(it.yaw), 0);
      dummy.scale.set(
        Math.max(1, it.size[0]), Math.max(1, it.size[2]), Math.max(1, it.size[1]));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, col.set(it.color || opts.color || '#9aa3af'));
      ids.push(it._id);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.userData.pick = { kind, ids };
    group.add(mesh);
    pickables.push(mesh);
    return mesh;
  }

  /** 房间地板：凸多边形棱柱（hull 已是凸包，扇形三角化即可）。 */
  function prismGeometry(pts, topY, thickness) {
    const n = pts.length;
    const botY = topY - thickness;
    let cx = 0, cz = 0;
    pts.forEach(q => { cx += q[0]; cz += q[1]; });
    cx /= n; cz /= n;
    const v = [];
    const tri = (a, b, c) => v.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]);
    for (let i = 0; i < n; i++) {
      const a = pts[i], b = pts[(i + 1) % n];
      tri([cx, topY, cz], [a[0], topY, a[1]], [b[0], topY, b[1]]);
      tri([cx, botY, cz], [b[0], botY, b[1]], [a[0], botY, a[1]]);
      tri([a[0], topY, a[1]], [a[0], botY, a[1]], [b[0], botY, b[1]]);
      tri([a[0], topY, a[1]], [b[0], botY, b[1]], [b[0], topY, b[1]]);
    }
    const g = new T.BufferGeometry();
    g.setAttribute('position', new T.Float32BufferAttribute(v, 3));
    g.computeVertexNormals();
    return g;
  }

  function buildRooms() {
    const wallItems = [];
    const seenEdges = new Set();
    (db.rooms || []).forEach((r, ri) => {
      if (!allowedFloor(r.z[0])) return;
      if (app.state.hiddenZones && app.state.hiddenZones.has(r.zone)) return;
      const color = zoneColor(r.zone);
      (r.hulls || []).forEach(hull => {
        if (!hull || hull.length < 3) return;
        const pts = hull.map(([x, y]) => [fx * x, -fy * y]);
        const mesh = new T.Mesh(
          prismGeometry(pts, r.z[0], 18),
          new T.MeshLambertMaterial({ color, side: T.DoubleSide,
                                     transparent: true, opacity: 0.88 }));
        mesh.userData.pick = { kind: 'room', id: ri };
        groups.rooms.add(mesh);
        pickables.push(mesh);

        const linePts = pts.map(q => new T.Vector3(q[0], r.z[0] + 3, q[1]));
        linePts.push(linePts[0].clone());
        groups.rooms.add(new T.Line(
          new T.BufferGeometry().setFromPoints(linePts),
          new T.LineBasicMaterial({ color: shade(color, 0.55), transparent: true, opacity: 0.9 })));

        if (cfg.walls === 'none') return;
        const height = cfg.walls === 'full'
          ? clamp((r.z[1] - r.z[0]) * 0.82, 200, 420) : 135;
        for (let i = 0; i < hull.length; i++) {
          const a = hull[i], b = hull[(i + 1) % hull.length];
          const A = pts[i], B = pts[(i + 1) % pts.length];
          const len = Math.hypot(B[0] - A[0], B[1] - A[1]);
          if (len < 12) continue;
          const key = [a, b].map(q => q.map(n => Math.round(n / 8)).join(',')).sort().join('|');
          if (seenEdges.has(key)) continue;
          seenEdges.add(key);
          // 屏幕空间边方向 -> UE 下的角度，再换算成 three 的 rotation.y
          const ueAngle = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
          wallItems.push({
            p: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, r.z[0]],
            yaw: ueAngle, size: [len, 16, height],
            color: '#' + shade(color, 0.72).getHexString(), _id: ri,
          });
        }
      });
    });
    boxInstances(groups.walls, wallItems, 'wall',
                 { opacity: cfg.walls === 'full' ? 0.5 : 0.42 });
  }

  function buildSolids() {
    const items = [];
    const byRaw = {};
    (db.rooms || []).forEach((r, i) => { byRaw[r.raw] = r; });
    (d3?.solids || []).forEach(s => {
      const room = byRaw[s.raw];
      if (room && !allowedFloor(room.z[0])) return;
      (s.boxes || []).forEach(b => {
        const dx = b[3] - b[0], dy = b[4] - b[1], dz = b[5] - b[2];
        if (dx <= 0 || dy <= 0 || dz <= 0) return;
        items.push({
          p: [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, b[2]],
          yaw: 0, size: [dx, dy, dz],
          color: room ? '#' + shade(zoneColor(room.zone), 1.25).getHexString() : '#8fb6d9',
          _id: null,
        });
      });
    });
    boxInstances(groups.solids, items, 'solid', { opacity: 0.085 });
  }

  function doorColor(d) {
    if (d.trial_only) return '#eab308';
    return DOOR_COLORS[d.kind] || DOOR_COLORS.other;
  }

  function buildDoors() {
    const frame = [], leaf = [];
    (db.doors || []).forEach(d => {
      const [x, y, z] = d.p || [0, 0, 0];
      if (Math.abs(x) < 1 && Math.abs(y) < 1 && Math.abs(z) < 1) return; // 模板占位
      if (!allowedFloor(z)) return;
      const w = clamp(d.w || 230, 140, 420);
      const h = 235, t = 18, post = 20;
      const a = ((d.yaw || 0) + 90) * Math.PI / 180;
      const ux = Math.cos(a), uy = Math.sin(a);
      const yaw = (d.yaw || 0) + 90;
      const color = doorColor(d);
      [-1, 1].forEach(s => {
        frame.push({
          p: [x + ux * (w / 2 - post / 2) * s, y + uy * (w / 2 - post / 2) * s, z],
          yaw, size: [post, t, h], color, _id: d.id,
        });
      });
      frame.push({ p: [x, y, z + h - 20], yaw, size: [w, t, 22], color, _id: d.id });
      leaf.push({ p: [x, y, z + 8], yaw, size: [w - post * 2, 8, h - 30],
                  color, _id: d.id });
    });
    boxInstances(groups.doors, frame, 'door', {});
    boxInstances(groups.doors, leaf, 'door', { opacity: 0.34 });
  }

  function buildStairs() {
    (db.stairs || []).forEach((s, i) => {
      if (!s.a || !s.b) return;
      if (!allowedFloor((s.a[2] + s.b[2]) / 2)) return;
      const A = P(s.a[0], s.a[1], s.a[2]);
      const B = P(s.b[0], s.b[1], s.b[2]);
      const dx = B[0] - A[0], dy = B[1] - A[1], dz = B[2] - A[2];
      const len = Math.hypot(dx, dy, dz);
      if (len < 5) return;
      const mesh = new T.Mesh(
        new T.BoxGeometry(clamp(s.w || 130, 60, 400), 16, len),
        new T.MeshLambertMaterial({ color: '#d9a441', side: T.DoubleSide,
                                   transparent: true, opacity: 0.85 }));
      mesh.position.set((A[0] + B[0]) / 2, (A[1] + B[1]) / 2, (A[2] + B[2]) / 2);
      mesh.quaternion.setFromUnitVectors(
        new T.Vector3(0, 0, 1), new T.Vector3(dx, dy, dz).normalize());
      mesh.userData.pick = { kind: 'stair', id: i };
      groups.stairs.add(mesh);
      pickables.push(mesh);
    });
  }

  function buildProps(list, group, kind, fallbackColor) {
    const items = [];
    (list || []).forEach((p, i) => {
      if (!allowedFloor(p.p[2])) return;
      items.push({
        p: p.p, yaw: p.yaw, size: p.size,
        color: CAT_COLORS[p.cat] || fallbackColor, _id: i,
      });
    });
    boxInstances(group, items, kind, { opacity: kind === 'structure' ? 0.5 : 1 });
  }

  function buildPoints() {
    const pts = (db.points || []).filter(p => allowedFloor(p.p[2]));
    if (!pts.length) return;
    const mesh = new T.InstancedMesh(
      new T.OctahedronGeometry(36, 0),
      new T.MeshLambertMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 }),
      pts.length);
    const dummy = new T.Object3D(), col = new T.Color();
    const ids = [];
    pts.forEach((p, i) => {
      const [x, y, z] = P(p.p[0], p.p[1], p.p[2]);
      dummy.position.set(x, y + 105, z);
      dummy.scale.setScalar(1);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, col.set(p.color || zoneColor(p.zone) || '#f59e0b'));
      ids.push(p.id != null ? p.id : i);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.userData.pick = { kind: 'point', ids };
    groups.points.add(mesh);
    pickables.push(mesh);
  }

  function syncMarkers() {
    const ms = app.state.seedMarkers || [];
    const sig = ms.length + ':' + ms.map(m => (m.p || []).join(',')).join('|');
    if (sig === markerSig) return;
    markerSig = sig;
    const g = groups.markers;
    while (g.children.length) {
      const c = g.children.pop();
      if (c.geometry) c.geometry.dispose();
      if (c.material) c.material.dispose();
    }
    const usable = ms.filter(m => m.p && m.p.length >= 2);
    if (!usable.length) return;
    const mesh = new T.InstancedMesh(
      new T.ConeGeometry(38, 150, 6),
      new T.MeshLambertMaterial({ color: '#facc15', emissive: '#7a5b00' }),
      usable.length);
    const dummy = new T.Object3D();
    const ids = [];
    usable.forEach((m, i) => {
      const [x, y, z] = P(m.p[0], m.p[1], m.p[2] || (db.zrange || [0, 0])[0] + 100);
      dummy.position.set(x, y + 120, z);
      dummy.rotation.set(Math.PI, 0, 0);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      ids.push(i);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.userData.pick = { kind: 'seed', ids };
    g.add(mesh);
    pickables = pickables.filter(o => o.parent !== g).concat(mesh);
  }

  function buildLabels() {
    if (!labelLayer) return;
    labelLayer.innerHTML = '';
    labels = [];
    (db.rooms || []).forEach((r, i) => {
      if (!allowedFloor(r.z[0])) return;
      if (app.state.hiddenZones && app.state.hiddenZones.has(r.zone)) return;
      const el = document.createElement('span');
      el.className = 'map3d-label';
      el.textContent = (app.state.db.notes?.rooms?.[r.raw]) || r.name || r.raw;
      labelLayer.appendChild(el);
      labels.push({ el, pos: new T.Vector3(fx * r.c[0], r.z[0] + 40, -fy * r.c[1]), id: i });
    });
    labelDirty = true;
  }

  // ------------------------------------------------------------------ 场景组装
  function build(keepCamera = true) {
    if (!ready || !app?.state?.db) return;
    db = app.state.db;
    fx = app.view.flipx ? -1 : 1;
    fy = app.view.flipy ? -1 : 1;
    disposeRoot();
    root = new T.Group();
    scene.add(root);
    groups = {};
    LAYERS.forEach(k => { groups[k] = new T.Group(); root.add(groups[k]); });
    floorSig = cfg.onlyFloor + ':' + app.state.floor;
    zoneSig = [...(app.state.hiddenZones || [])].sort().join('|');
    markerSig = '';

    buildRooms();
    buildSolids();
    buildDoors();
    buildStairs();
    buildProps(d3?.props || [], groups.props, 'prop', '#9aa3af');
    buildProps(d3?.structures || [], groups.structures, 'structure', '#9aa2ab');
    buildPoints();
    buildLabels();
    if (!keepCamera || lastLevel !== level) {
      fitCamera();
      lastLevel = level;
      if (pendingView && pendingView !== 'iso') applyView(pendingView);
    }
    applyLayers();
    syncMarkers();
    syncPanel();
    labelDirty = true;
  }

  function applyLayers() {
    if (!groups.rooms) return;
    const st = app.state;
    groups.rooms.visible = cfg.rooms;
    groups.walls.visible = cfg.walls !== 'none';
    groups.solids.visible = cfg.solids;
    groups.props.visible = cfg.props;
    groups.structures.visible = cfg.structures;
    groups.doors.visible = st.showDoors;
    groups.stairs.visible = st.showStairs;
    groups.points.visible = st.showPoints;
    groups.markers.visible = st.showSeed;
    if (labelLayer) labelLayer.style.display = cfg.labels ? '' : 'none';
  }

  // ------------------------------------------------------------------ 相机
  function fitCamera() {
    const [x0, y0, x1, y1] = db.bbox || [0, 0, 1000, 1000];
    const [z0, z1] = db.zrange || [0, 400];
    cam.target.set(fx * (x0 + x1) / 2, (z0 + z1) / 2, -fy * (y0 + y1) / 2);
    cam.radius = Math.max(x1 - x0, y1 - y0, 1000) * 0.80;
    camera.near = Math.max(1, cam.radius / 3000);
    camera.far = cam.radius * 12;
    camera.updateProjectionMatrix();
    cam.theta = 0.30;
    cam.phi = 0.72;
    cfg.view = 'iso';
    syncPanel();
    updateCamera();
  }

  function updateCamera() {
    const s = Math.sin(cam.phi), c = Math.cos(cam.phi);
    camera.position.set(
      cam.target.x + cam.radius * s * Math.sin(cam.theta),
      cam.target.y + cam.radius * c,
      cam.target.z + cam.radius * s * Math.cos(cam.theta));
    camera.up.set(0, 1, 0);
    camera.lookAt(cam.target);
    camera.updateMatrixWorld();
    labelDirty = true;
  }

  function resetView() { fitCamera(); }

  function applyView(name) {
    cfg.view = name;
    if (name === 'top') { cam.phi = 0.035; cam.theta = 0; }
    else if (name === 'side') { cam.phi = 1.42; cam.theta = 0.45; }
    else { cam.phi = 0.72; cam.theta = 0.30; }
    syncPanel();
    updateCamera();
  }

  function setView(name) {
    pendingView = name;      // 数据还没到时先记着，build() 之后再套用
    applyView(name);
  }

  function rotate(rad) { cam.theta += rad; syncPanel(); updateCamera(); }

  function resize() {
    if (!renderer || !container) return;
    const rect = container.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    labelDirty = true;
  }

  // ------------------------------------------------------------------ 拾取
  function isVisible(o) {
    let cur = o;
    while (cur && cur !== scene) {
      if (!cur.visible) return false;
      cur = cur.parent;
    }
    return true;
  }

  function pick(clientX, clientY) {
    if (!ready || !camera || !pickables.length) return null;
    const rect = canvas.getBoundingClientRect();
    const nx = ((clientX - rect.left) / rect.width) * 2 - 1;
    const ny = -((clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(new T.Vector2(nx, ny), camera);
    const hits = raycaster.intersectObjects(pickables.filter(isVisible), false);
    for (const h of hits) {
      const p = h.object.userData.pick;
      if (!p) continue;
      const id = p.ids ? p.ids[h.instanceId] : p.id;
      if (id == null) continue;
      return { kind: p.kind, id, point: h.point };
    }
    return null;
  }

  function infoFor(kind, id) {
    if (kind === 'prop' || kind === 'structure') {
      const row = (kind === 'prop' ? d3?.props : d3?.structures)?.[id];
      if (!row) return null;
      return {
        title: `${kind === 'prop' ? '道具' : '结构网格'} · ${row.mesh}`,
        sub: `类别: ${row.cat}  |  坐标: (${row.p.join(', ')})  |  ` +
             `尺寸: ${row.size.map(n => Math.round(n)).join('×')}  |  来源: ${row.file}`,
        copyRaw: row.mesh,
      };
    }
    if (kind === 'solid') return null;
    if (kind === 'wall') return { kind: 'room', id };
    return { kind, id };
  }

  function showTip(clientX, clientY, target) {
    if (!tip) return;
    let desc = target ? infoFor(target.kind, target.id) : null;
    if (desc?.kind) desc = app.describe(desc);
    if (!desc || !desc.title) { tip.classList.add('hidden'); return; }
    tip.innerHTML = `<strong>${esc(desc.title)}</strong>` +
      `<div style="color:var(--muted);margin-top:2px">${esc(desc.sub || '')}</div>`;
    const rect = container.getBoundingClientRect();
    tip.style.left = `${Math.min(rect.width - 300, clientX - rect.left + 14)}px`;
    tip.style.top = `${Math.max(12, clientY - rect.top - 18)}px`;
    tip.classList.remove('hidden');
  }

  function focusOn(point) {
    if (!point) return;
    cam.target.copy(point);
    cam.radius = clamp(cam.radius * 0.55, 900, 9000);
    updateCamera();
  }

  // ------------------------------------------------------------------ 事件
  let drag = null;

  function bindEvents() {
    canvas.addEventListener('contextmenu', e => e.preventDefault());
    canvas.addEventListener('mousedown', e => {
      if (!active) return;
      drag = { x: e.clientX, y: e.clientY, lx: e.clientX, ly: e.clientY,
               button: e.button, shift: e.shiftKey, moved: false };
      if (tip) tip.classList.add('hidden');
    });
    window.addEventListener('mousemove', e => {
      if (!active) return;
      if (drag) {
        const dx = e.clientX - drag.lx, dy = e.clientY - drag.ly;
        if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 4) drag.moved = true;
        drag.lx = e.clientX; drag.ly = e.clientY;
        if (drag.button === 0 && !drag.shift) {
          cam.theta -= dx * 0.006;
          cam.phi = clamp(cam.phi - dy * 0.006, 0.02, 1.5);
        } else {
          const k = cam.radius * 0.0013;
          const right = new T.Vector3(Math.cos(cam.theta), 0, -Math.sin(cam.theta));
          const fwd = new T.Vector3(-Math.sin(cam.theta), 0, -Math.cos(cam.theta));
          cam.target.addScaledVector(right, -dx * k);
          cam.target.addScaledVector(fwd, dy * k);
        }
        cfg.view = 'free';
        syncPanel();
        updateCamera();
        return;
      }
      showTip(e.clientX, e.clientY, pick(e.clientX, e.clientY));
    });
    window.addEventListener('mouseup', e => {
      if (!active || !drag) return;
      const d = drag;
      drag = null;
      if (d.moved || d.button !== 0) return;
      const target = pick(e.clientX, e.clientY);
      if (!target || !target.kind) {
        app.select(null, false);
        return;
      }
      const info = infoFor(target.kind, target.id);
      if (!info) {
        app.select(null, false);
        return;
      }
      if (info.kind) app.select(info, true);
      else app.select({ kind: 'custom', info }, true);
    });
    canvas.addEventListener('dblclick', e => {
      if (!active) return;
      const t = pick(e.clientX, e.clientY);
      if (t) focusOn(t.point);
    });
    canvas.addEventListener('wheel', e => {
      if (!active) return;
      e.preventDefault();
      cam.radius = clamp(cam.radius * (e.deltaY < 0 ? 0.88 : 1.14), 300, 120000);
      updateCamera();
    }, { passive: false });
    window.addEventListener('resize', () => { if (active) resize(); });
  }

  // ------------------------------------------------------------------ 循环
  function loop() {
    if (!active) return;
    raf = requestAnimationFrame(loop);
    const st = app.state;
    const dark = !st.lightTheme;
    if (dark !== themeDark) {
      themeDark = dark;
      scene.background = new T.Color(dark ? '#0d1522' : '#e9eef5');
    }
    const nfx = app.view.flipx ? -1 : 1, nfy = app.view.flipy ? -1 : 1;
    const fsig = cfg.onlyFloor + ':' + st.floor;
    const zsig = [...(st.hiddenZones || [])].sort().join('|');
    if (nfx !== fx || nfy !== fy || fsig !== floorSig || zsig !== zoneSig) {
      build(true);
    } else {
      applyLayers();
    }
    syncMarkers();
    if (labelDirty) updateLabels();
    renderer.render(scene, camera);
    if (badge) {
      const views = { top: '俯视', iso: '斜视', side: '平视', free: '自由' };
      const nprops = (d3?.props || []).length;
      badge.textContent = `3D · ${views[cfg.view] || '自由'} · ` +
        `${(db?.rooms || []).length} 房间 · ${nprops} 道具` +
        (cfg.onlyFloor ? ` · 仅 ${(db?.floors || [])[st.floor]?.label || st.floor + 1}` : '');
    }
  }

  function updateLabels() {
    labelDirty = false;
    if (!labels.length || !camera) return;
    const w = container.clientWidth, h = container.clientHeight;
    const v = new T.Vector3();
    labels.forEach(l => {
      v.copy(l.pos).project(camera);
      if (v.z < -1 || v.z > 1 || Math.abs(v.x) > 1.05 || Math.abs(v.y) > 1.05) {
        l.el.style.display = 'none';
        return;
      }
      l.el.style.display = '';
      l.el.style.transform = `translate(-50%,-50%) translate(${(v.x * 0.5 + 0.5) * w}px,${(-v.y * 0.5 + 0.5) * h}px)`;
    });
  }

  function setActive(v) {
    if (!ready) return;
    const want = !!v;
    if (want === active) return;
    active = want;
    canvas.classList.toggle('hidden', !want);
    mapCanvas.classList.toggle('hidden', want);
    if (panel) panel.classList.toggle('hidden', !want);
    if (labelLayer) labelLayer.classList.toggle('hidden', !want);
    if (tip) tip.classList.add('hidden');
    if (want) {
      if (!root) build(false);
      resize();
      updateCamera();
      loop();
    } else if (raf) {
      cancelAnimationFrame(raf);
      raf = null;
    }
  }

  async function load(lv) {
    if (!ready) return;
    try {
      const res = await fetch('/api/3d?level=' + encodeURIComponent(lv || ''));
      const j = await res.json();
      d3 = j.ok ? j.data : null;
    } catch (e) {
      console.warn('[3D] 3D 数据读取失败，只用 2D 数据搭基础场景', e);
      d3 = null;
    }
    const changed = level !== lv;
    level = lv;
    if (changed) lastLevel = null;
    // 只有换关卡才重置相机；用户已经转过视角时，3D 数据晚到不打断操作
    build(!changed && !!root);
    if (active) { resize(); labelDirty = true; }
  }

  window.Map3D = {
    available: false, init, load, resize, setActive,
    resetView, rotate, setView,
    get active() { return active; },
    get hasData() { return !!d3; },
  };
})();
