/* app.js — OPP Web 交互式地图前端 */
(() => {
  const DOOR_KINDS = {
    spawn:    { label: '刷怪门 (Monster Closet)', color: '#ef4444', width: 3.0, dash: [5, 3] },
    normal:   { label: '普通门 (Normal)',         color: '#8b5cf6', width: 2.0, dash: [] },
    rolling:  { label: '卷帘门 (Rolling)',        color: '#3b82f6', width: 2.2, dash: [] },
    sliding:  { label: '滑门 (Sliding)',          color: '#06b6d4', width: 2.0, dash: [] },
    access:   { label: '权限门 (SAS / Employee)', color: '#f59e0b', width: 2.2, dash: [] },
    backdrop: { label: '背景门 (Backdrop)',       color: '#64748b', width: 1.4, dash: [2, 3] },
    other:    { label: '其他门 (Other)',          color: '#94a3b8', width: 2.0, dash: [] },
  };
  const TRIAL_DOOR = { label: '本关专属门 (Trial-only)', color: '#eab308', width: 3.0, dash: [6, 3] };

  const state = {
    db: null,
    level: null,
    mode: 'overlay',
    prev2dMode: 'overlay',     // 从 3D 返回时回到原来的叠加/分层模式
    floor: 0,
    showDoors: true,
    showStairs: true,
    showPoints: true,
    showAllNames: false,
    showSeed: true,
    showLegend: false,
    showBarrels: false,
    showHidespots: false,
    hiddenBarrelTypes: new Set(),
    hiddenHideTypes: new Set(),
    variators: [],
    autoVariatorLayersFor: null,
    followGame: true,
    lightTheme: true,
    coordTarget: null,
    hiddenZones: new Set(),
    seedMarkers: [],
    analysis: null,
    analysisRoomColor: new Map(),
    autoHiddenPointsFor: null,
    seedLine: '',
    selected: null,
    hovered: null,
    lastSeedSig: '',
  };

  const view = {
    box: [0, 0, 1000, 1000],
    scale: 0.1,
    ox: 0,
    oy: 0,
    w: 800,
    h: 600,
    flipx: true,
    flipy: false,
    turns: 0,

    _flip(x, y) {
      return [this.flipx ? -x : x, this.flipy ? -y : y];
    },
    _rot(sx, sy) {
      const t = ((this.turns % 4) + 4) % 4;
      if (!t) return [sx, sy];
      const ax = this.w / 2, ay = this.h / 2;
      const dx = sx - ax, dy = sy - ay;
      if (t === 1) return [ax - dy, ay + dx];
      if (t === 2) return [ax - dx, ay - dy];
      return [ax + dy, ay - dx];
    },
    _unrot(sx, sy) {
      const t = ((this.turns % 4) + 4) % 4;
      if (!t) return [sx, sy];
      const ax = this.w / 2, ay = this.h / 2;
      const dx = sx - ax, dy = sy - ay;
      if (t === 1) return [ax + dy, ay - dx];
      if (t === 2) return [ax - dx, ay - dy];
      return [ax - dy, ay + dx];
    },
    pt(x, y) {
      const [fx, fy] = this._flip(x, y);
      return this._rot(this.ox + fx * this.scale, this.oy - fy * this.scale);
    },
    fit(pad = 54) {
      const [x0, y0, x1, y1] = this.box;
      let bw = Math.max(1, x1 - x0);
      let bh = Math.max(1, y1 - y0);
      if (this.turns % 2 !== 0) [bw, bh] = [bh, bw];
      this.scale = Math.min((this.w - pad * 2) / bw, (this.h - pad * 2) / bh);
      const [cx, cy] = this._flip((x0 + x1) / 2, (y0 + y1) / 2);
      this.ox = this.w / 2 - cx * this.scale;
      this.oy = this.h / 2 + cy * this.scale;
    },
    panBy(dx, dy) {
      const t = ((this.turns % 4) + 4) % 4;
      if (t === 0) { this.ox += dx; this.oy += dy; }
      else if (t === 1) { this.ox += dy; this.oy -= dx; }
      else if (t === 2) { this.ox -= dx; this.oy -= dy; }
      else { this.ox -= dy; this.oy += dx; }
    },
    zoomAt(sx, sy, factor) {
      const [px, py] = this._unrot(sx, sy);
      const fx = (px - this.ox) / this.scale;
      const fy = (this.oy - py) / this.scale;
      this.scale = Math.max(0.008, Math.min(4.0, this.scale * factor));
      this.ox = px - fx * this.scale;
      this.oy = py + fy * this.scale;
    },
    centerOnWorld(wx, wy) {
      const [fx, fy] = this._flip(wx, wy);
      this.ox = this.w / 2 - fx * this.scale;
      this.oy = this.h / 2 + fy * this.scale;
    }
  };

  const canvas = document.getElementById('mapCanvas');
  const ctx = canvas.getContext('2d');
  const levelSelect = document.getElementById('levelSelect');
  const floorButtons = document.getElementById('floorButtons');
  const legendCard = document.getElementById('legendCard');
  const zoneList = document.getElementById('zoneList');
  const doorLegendList = document.getElementById('doorLegendList');
  const hoverTooltip = document.getElementById('hoverTooltip');
  const viewBadge = document.getElementById('viewBadge');
  const inspTitle = document.getElementById('inspTitle');
  const inspSub = document.getElementById('inspSub');
  const toastMsg = document.getElementById('toastMsg');
  const btnCopyRaw = document.getElementById('btnCopyRaw');
  const btnEditNote = document.getElementById('btnEditNote');

  let hitTargets = [];

  function showToast(msg) {
    toastMsg.textContent = msg;
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => { toastMsg.textContent = ''; }, 3200);
  }

  async function copyText(text, label) {
    if (!text) return;
    const msg = label || `已复制: ${text}`;
    try {
      await navigator.clipboard.writeText(text);
      showToast(msg);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      showToast(msg);
    }
  }

  function copySeedLine() {
    if (!state.seedLine) {
      showToast('还没有读到本局 seed 信息');
      return;
    }
    const trial = (state.seedLine.match(/Trial ID: ([^,]+)/) || [])[1] || '';
    const seed = (state.seedLine.match(/Seed: (\d+)/) || [])[1] || '';
    copyText(state.seedLine, `已复制 Seed：${trial}${seed ? ' / ' + seed : ''}`);
  }

  function hexToRgba(hex, alpha) {
    const c = (hex || '#64748b').replace('#', '');
    const r = parseInt(c.slice(0, 2), 16) || 100;
    const g = parseInt(c.slice(2, 4), 16) || 116;
    const b = parseInt(c.slice(4, 6), 16) || 139;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function noteOf(kind, key) {
    return ((state.db?.notes || {})[kind] || {})[key] || '';
  }

  function roomDisplayName(room) {
    return noteOf('rooms', room.raw) || room.name || room.raw;
  }

  function zoneDisplayName(zone) {
    return noteOf('zones', zone.id) || zone.name || zone.id;
  }

  function zoneColor(zid) {
    const z = (state.db?.zones || []).find(item => item.id === zid);
    return z ? z.color : '#64748b';
  }

  function floorLabel(idx) {
    const f = (state.db?.floors || []).find(item => item.index === idx);
    return f ? f.label : `${idx + 1}F`;
  }

  async function loadMap(level, fitView = true) {
    const res = await fetch(`/api/map?level=${encodeURIComponent(level || '')}`);
    const data = await res.json();
    if (!data.ok || !data.map) {
      showToast(data.error || '加载地图失败');
      return;
    }
    state.db = data.map;
    state.level = state.db.level;
    levelSelect.value = state.level;
    state.hiddenZones.clear();
    state.selected = null;
    state.coordTarget = null;      // 换关卡就作废：坐标只属于当前这张图

    if (state.db._default_flip) {
      view.flipx = !!state.db._default_flip.x;
      view.flipy = !!state.db._default_flip.y;
    }
    view.box = state.db.bbox || [0, 0, 1000, 1000];
    if (state.floor >= (state.db.floors || []).length) {
      state.floor = 0;
    }
    buildFloorButtons();
    buildLegend();
    state.hiddenBarrelTypes.clear();
    state.hiddenHideTypes.clear();
    document.getElementById('lblBarrelCount').textContent =
      `火桶点位 (${(state.db.barrels || []).length})`;
    document.getElementById('lblHideCount').textContent =
      `隐藏点 (${(state.db.hidespots || []).length})`;
    buildVariatorTypeLegend();
    syncVariatorPills();
    syncVariatorLayers();
    if (fitView) view.fit();
    updateInspector();
    if (window.Map3D) window.Map3D.load(state.level);
    requestRender();
  }

  function buildFloorButtons() {
    floorButtons.innerHTML = '';
    if (!state.db) return;
    (state.db.floors || []).forEach(f => {
      const btn = document.createElement('button');
      btn.textContent = f.label;
      if (state.mode === 'floor' && state.floor === f.index) btn.classList.add('active');
      btn.addEventListener('click', () => {
        if (state.mode !== '3d') state.mode = 'floor';
        state.floor = f.index;
        syncModeUI();
        requestRender();
      });
      floorButtons.appendChild(btn);
    });
  }

  function syncModeUI() {
    document.querySelectorAll('#modeSwitch button').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === state.mode);
    });
    Array.from(floorButtons.children).forEach((btn, idx) => {
      btn.classList.toggle('active',
        (state.mode === 'floor' || state.mode === '3d') && state.floor === idx);
    });
  }

  function buildLegend() {
    if (!state.db) return;
    document.getElementById('legendTitle').textContent = `${state.db.level} · 分区图例`;
    zoneList.innerHTML = '';
    const zones = state.db.zones || [];
    if (!zones.length) {
      zoneList.innerHTML = '<div style="font-size:12px;color:var(--muted)">本关暂无预设分区</div>';
    } else {
      zones.forEach(z => {
        const row = document.createElement('div');
        row.className = 'zone-row' + (state.hiddenZones.has(z.id) ? ' hidden-zone' : '');
        row.innerHTML = `
          <span class="zone-Swatch" style="background:${z.color}"></span>
          <span style="flex:1">${z.id} · ${zoneDisplayName(z)}</span>
        `;
        row.title = '单击切换显示/隐藏；双击修改分区备注名';
        row.addEventListener('click', () => {
          if (state.hiddenZones.has(z.id)) state.hiddenZones.delete(z.id);
          else state.hiddenZones.add(z.id);
          buildLegend();
          requestRender();
        });
        row.addEventListener('dblclick', (e) => {
          e.stopPropagation();
          openNoteModal('zones', z.id, `分区 ${z.id} 备注`, noteOf('zones', z.id));
        });
        zoneList.appendChild(row);
      });
    }

    doorLegendList.innerHTML = '';
    const doors = state.db.doors || [];
    const appeared = new Set(doors.map(d => d.kind || 'other'));
    Object.entries(DOOR_KINDS).forEach(([k, meta]) => {
      if (!appeared.has(k)) return;
      const row = document.createElement('div');
      row.className = 'door-legend-row';
      row.innerHTML = `<span class="door-line-sample" style="background:${meta.color}"></span><span>${meta.label}</span>`;
      doorLegendList.appendChild(row);
    });
    if (doors.some(d => d.trial_only)) {
      const row = document.createElement('div');
      row.className = 'door-legend-row';
      row.innerHTML = `<span class="door-line-sample" style="background:${TRIAL_DOOR.color}"></span><span>${TRIAL_DOOR.label}</span>`;
      doorLegendList.appendChild(row);
    }
  }

  let rafId = null;
  function toggle3D() {
    if (state.mode !== '3d' && window.Map3D && !window.Map3D.available) {
      showToast('本环境不支持 WebGL，3D 模式不可用');
      return;
    }
    if (state.mode === '3d') state.mode = state.prev2dMode || 'overlay';
    else { state.prev2dMode = state.mode; state.mode = '3d'; }
    syncModeUI();
    requestRender();
  }

  function requestRender() {
    // 3D 模式用独立的连续渲染循环，2D 那套单次 rAF 合并绘制在这里让路
    if (window.Map3D) window.Map3D.setActive(state.mode === '3d');
    if (state.mode === '3d') return;
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      rafId = null;
      render();
    });
  }

  function resizeCanvas() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    view.w = rect.width;
    view.h = rect.height;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (window.Map3D) window.Map3D.resize();
    requestRender();
  }

  function render() {
    if (state.mode === '3d') return;
    ctx.clearRect(0, 0, view.w, view.h);
    hitTargets = [];

    if (!state.db) {
      ctx.fillStyle = state.lightTheme ? '#64748b' : '#94a3b8';
      ctx.font = 'bold 16px "Microsoft YaHei UI", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('正在加载地图数据…', view.w / 2, view.h / 2);
      return;
    }

    const db = state.db;
    const rooms = db.rooms || [];
    const points = db.points || [];
    const doors = db.doors || [];

    const zoneHidden = (zid) => zid && state.hiddenZones.has(zid);

    let contextRooms = [];
    let visibleRooms = [];
    if (state.mode === 'floor') {
      contextRooms = rooms.filter(r => r.floors?.length && !r.floors.includes(state.floor) && !zoneHidden(r.zone));
      visibleRooms = rooms.filter(r => (!r.floors?.length || r.floors.includes(state.floor)) && !zoneHidden(r.zone));
    } else {
      visibleRooms = rooms
        .filter(r => !zoneHidden(r.zone))
        .slice()
        .sort((a, b) => Math.max(...(a.floors || [0])) - Math.max(...(b.floors || [0])));
    }

    ctx.save();
    ctx.setLineDash([3, 4]);
    ctx.strokeStyle = state.lightTheme ? '#cbd5e1' : 'rgba(148, 163, 184, 0.2)';
    ctx.lineWidth = 1;
    contextRooms.forEach(r => {
      r.hulls.forEach(h => {
        const pts = h.map(([x, y]) => view.pt(x, y));
        drawPoly(pts);
        ctx.stroke();
        hitTargets.push({ kind: 'room', id: r.id, poly: pts });
      });
    });
    ctx.restore();

    visibleRooms.forEach(r => {
      const zColor = zoneColor(r.zone);
      const isSelected = state.selected?.kind === 'room' && state.selected?.id === r.id;
      const isSeedRoom = state.selected?.kind === 'seed' && state.seedMarkers[state.selected.id]?.room === r.raw;
      const isHovered = state.hovered?.kind === 'room' && state.hovered?.id === r.id;

      let fillAlpha = r.kind === 'corridor' ? 0.14 : 0.26;
      if (state.lightTheme) fillAlpha = r.kind === 'corridor' ? 0.16 : 0.28;

      let fill = r.zone ? hexToRgba(zColor, fillAlpha) : (state.lightTheme ? '#e2e8f0' : '#1e293b');
      let stroke = r.zone ? hexToRgba(zColor, 0.85) : (state.lightTheme ? '#94a3b8' : '#475569');
      let lw = 1.5;

      const anColor = state.showSeed ? state.analysisRoomColor.get(r.raw) : null;
      if (anColor) {
        fill = hexToRgba(anColor, state.lightTheme ? 0.3 : 0.22);
        stroke = anColor;
        lw = 2.2;
      }

      if (isHovered) {
        lw = Math.max(lw, 2.4);
      }
      if (isSelected || isSeedRoom) {
        fill = hexToRgba('#f59e0b', state.lightTheme ? 0.38 : 0.35);
        stroke = '#f59e0b';
        lw = 3.0;
      }

      r.hulls.forEach(h => {
        const pts = h.map(([x, y]) => view.pt(x, y));
        drawPoly(pts);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.lineWidth = lw;
        ctx.strokeStyle = stroke;
        ctx.stroke();
        hitTargets.push({ kind: 'room', id: r.id, poly: pts });
      });
    });

    if (state.showDoors) {
      doors.forEach(d => {
        if (state.mode === 'floor' && d.floor != null && d.floor !== state.floor) return;
        const [x, y] = d.p;
        const half = Math.max(160, d.w || 230) / 2;
        const rad = ((d.yaw || 0) + 90) * Math.PI / 180;
        const dx = Math.cos(rad) * half;
        const dy = Math.sin(rad) * half;
        const p1 = view.pt(x - dx, y - dy);
        const p2 = view.pt(x + dx, y + dy);

        const style = d.kind === 'spawn'
          ? DOOR_KINDS.spawn
          : (d.trial_only ? TRIAL_DOOR : (DOOR_KINDS[d.kind] || DOOR_KINDS.other));

        const isSel = state.selected?.kind === 'door' && state.selected?.id === d.id;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.strokeStyle = isSel ? '#f59e0b' : style.color;
        ctx.lineWidth = isSel ? style.width + 2 : style.width;
        ctx.setLineDash(style.dash || []);
        ctx.stroke();
        ctx.restore();

        hitTargets.push({ kind: 'door', id: d.id, p1, p2 });
      });
    }

    // 楼梯：一段要么是单层的一级台阶/坡道，要么跨层（floors 里不止一层）——
    // 跨层的楼梯在它覆盖的每一层都会画一次，所以两层里都能看到楼梯在哪。
    if (state.showStairs) {
      (db.stairs || []).forEach(s => {
        const fls = s.floors || [];
        if (state.mode === 'floor' && fls.length && !fls.includes(state.floor)) return;
        const [x0, y0] = s.a;
        const [x1, y1] = s.b;
        let dx = x1 - x0, dy = y1 - y0;
        let len = Math.hypot(dx, dy);
        if (len < 1) { dx = 0; dy = -1; len = 1; }
        const halfW = Math.max(90, s.w || 200) / 2;
        const nx = -dy / len * halfW;
        const ny = dx / len * halfW;
        const quad = [
          view.pt(x0 - nx, y0 - ny), view.pt(x1 - nx, y1 - ny),
          view.pt(x1 + nx, y1 + ny), view.pt(x0 + nx, y0 + ny),
        ];
        const multi = fls.length > 1;
        const isSel = state.selected?.kind === 'stair' && state.selected?.id === s.id;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(quad[0][0], quad[0][1]);
        for (let i = 1; i < quad.length; i++) ctx.lineTo(quad[i][0], quad[i][1]);
        ctx.closePath();
        ctx.fillStyle = multi
          ? hexToRgba('#22d3ee', state.lightTheme ? 0.26 : 0.2)
          : hexToRgba('#22d3ee', state.lightTheme ? 0.16 : 0.12);
        ctx.fill();
        ctx.setLineDash(multi ? [] : [4, 3]);
        ctx.strokeStyle = isSel ? '#f59e0b' : (multi ? '#22d3ee' : 'rgba(34, 211, 238, 0.7)');
        ctx.lineWidth = isSel ? 3 : (multi ? 2.0 : 1.3);
        ctx.stroke();
        // 中线：从低端指向高端，方便看出上行方向
        const p0 = view.pt(x0, y0);
        const p1 = view.pt(x1, y1);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(p0[0], p0[1]);
        ctx.lineTo(p1[0], p1[1]);
        ctx.strokeStyle = isSel ? '#f59e0b' : '#22d3ee';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();

        hitTargets.push({ kind: 'stair', id: s.id, p1: p0, p2: p1 });
      });
    }

    const pointRooms = new Set(points.map(p => p.room).filter(r => r != null));
    const seedRoomNames = new Set(state.seedMarkers.map(m => m.room).filter(Boolean));
    const placedBoxes = [];

    const labelCandidates = visibleRooms.filter(r =>
      state.showAllNames ||
      pointRooms.has(r.id) ||
      seedRoomNames.has(r.raw) ||
      r.named ||                                  // 配置里手写了房间名
      Boolean(noteOf('rooms', r.raw)) ||
      (state.selected?.kind === 'room' && state.selected?.id === r.id)
    ).sort((a, b) => b.area - a.area);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    labelCandidates.forEach(r => {
      const box = roomScreenBBox(r);
      const w = box[2] - box[0], h = box[3] - box[1];
      if (w < 28 || h < 14) return;
      const hasNote = Boolean(noteOf('rooms', r.raw));
      const text = roomDisplayName(r);
      if (!text) return;

      ctx.font = `${hasNote ? '700' : '600'} 11.5px "Microsoft YaHei UI", sans-serif`;
      const tw = ctx.measureText(text).width;
      const sx = (box[0] + box[2]) / 2;
      const sy = (box[1] + box[3]) / 2;
      const lbox = [sx - tw / 2 - 4, sy - 8, sx + tw / 2 + 4, sy + 8];
      if (placedBoxes.some(b => !(lbox[2] < b[0] || lbox[0] > b[2] || lbox[3] < b[1] || lbox[1] > b[3]))) {
        return;
      }
      placedBoxes.push(lbox);

      ctx.lineWidth = 3;
      ctx.strokeStyle = state.lightTheme ? 'rgba(255,255,255,0.85)' : 'rgba(11,17,32,0.85)';
      ctx.strokeText(text, sx, sy);
      ctx.fillStyle = hasNote ? '#14b8a6' : (state.lightTheme ? '#1e293b' : '#e2e8f0');
      ctx.fillText(text, sx, sy);
    });

    if (state.showPoints) {
      const visPoints = points.filter(p =>
        !(state.mode === 'floor' && p.floor != null && p.floor !== state.floor) &&
        !zoneHidden(p.zone)
      );
      const showShortName = visPoints.length <= 15;

      visPoints.forEach(p => {
        const [sx, sy] = view.pt(p.p[0], p.p[1]);
        const isGoal = (p.style || '') !== 'clue';
        const zColor = zoneColor(p.zone);
        const tint = p.color || '';
        const isSel = state.selected?.kind === 'point' && state.selected?.id === p.id;
        const r = isSel ? 12 : 9.5;

        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fillStyle = tint || (isGoal ? '#e11d48' : (state.lightTheme ? '#ffffff' : '#0f172a'));
        ctx.fill();
        ctx.lineWidth = isSel ? 3 : 2;
        ctx.strokeStyle = isSel ? '#f59e0b' : (tint ? '#ffffff' : zColor);
        ctx.stroke();

        ctx.font = 'bold 10px Consolas, sans-serif';
        ctx.fillStyle = isGoal ? '#ffffff' : (state.lightTheme ? '#0f172a' : '#f8fafc');
        ctx.textAlign = 'center';
        ctx.fillText(String(p.num || ''), sx, sy + 0.5);

        const customNote = noteOf('points', p.actor);
        if (showShortName || isSel || customNote) {
          const label = customNote || p.short || '';
          ctx.font = '600 11px "Microsoft YaHei UI", sans-serif';
          ctx.textAlign = 'left';
          ctx.lineWidth = 3;
          ctx.strokeStyle = state.lightTheme ? 'rgba(255,255,255,0.9)' : 'rgba(11,17,32,0.9)';
          ctx.strokeText(label, sx + r + 5, sy);
          ctx.fillStyle = customNote ? '#14b8a6' : (state.lightTheme ? '#0f172a' : '#f1f5f9');
          ctx.fillText(label, sx + r + 5, sy);
        }

        hitTargets.push({ kind: 'point', id: p.id, cx: sx, cy: sy, r: r + 4 });
      });
    }

    if (state.showSeed && state.seedMarkers.length) {
      let band = null;
      if (state.mode === 'floor') {
        const f = (db.floors || []).find(item => item.index === state.floor);
        if (f) band = f.band;
      }

      state.seedMarkers.forEach((m, i) => {
        if (band && m.p.length > 2) {
          const [lo, hi] = band;
          const z = m.p[2];
          if ((lo != null && z < lo - 200) || (hi != null && z > hi + 200)) return;
        }
        const [sx, sy] = view.pt(m.p[0], m.p[1]);
        const isSel = state.selected?.kind === 'seed' && state.selected?.id === i;
        const color = m.color || (m.kind === 'goal' ? '#f43f5e' : '#14b8a6');
        const base = 10.5 * (m.size || 1);
        const r = isSel ? base + 2.5 : base;

        ctx.beginPath();
        ctx.arc(sx, sy, r + 4, 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba(color, 0.25);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        const roomOnly = m.exact === false;
        ctx.fillStyle = roomOnly ? hexToRgba(color, 0.5) : color;
        ctx.fill();
        ctx.lineWidth = isSel ? 3 : 2;
        ctx.strokeStyle = isSel ? '#f59e0b' : '#ffffff';
        if (roomOnly) ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);

        const badgeText = m.badge || String(i + 1);
        const badgeFont = badgeText.length >= 3 ? 0.95 : 1;
        ctx.font = `bold ${(10.5 * badgeFont * (m.size || 1) / 1).toFixed(1)}px Consolas, sans-serif`;
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(badgeText, sx, sy + 0.5);

        const tagText = m.label || '';
        if (tagText) {
          ctx.font = 'bold 11.5px "Microsoft YaHei UI", sans-serif';
          ctx.textAlign = 'left';
          ctx.lineWidth = 3.5;
          ctx.strokeStyle = state.lightTheme ? 'rgba(255,255,255,0.92)' : 'rgba(11,17,32,0.92)';
          ctx.strokeText(tagText, sx + r + 6, sy);
          ctx.fillStyle = color;
          ctx.fillText(tagText, sx + r + 6, sy);
        }

        hitTargets.push({ kind: 'seed', id: i, cx: sx, cy: sy, r: r + 5 });
      });
    }

    // 变数点位：火桶候选（菱形）/ 隐藏点（空心圆），各自独立开关、按类型还能再细分
    drawVariatorLayer('barrels', db.barrels || [], state.hiddenBarrelTypes, state.showBarrels);
    drawVariatorLayer('hidespots', db.hidespots || [], state.hiddenHideTypes, state.showHidespots);

    drawCoordTarget();

    const parts = [
      state.mode === 'overlay'
        ? `叠加 (${(db.floors || []).length}层)`
        : `分层 · ${floorLabel(state.floor)}`
    ];
    if (view.turns % 4) parts.push(`旋转 ${(view.turns % 4) * 90}°`);
    if (view.flipx) parts.push('镜像 X');
    viewBadge.textContent = parts.join(' · ');
  }

  // ---- 变数点位图层 ----
  const VP_COLORS = { barrels: '#f97316', hidespots: '#22c55e' };

  function drawVariatorLayer(kind, rows, hiddenTypes, show) {
    if (!show || !rows.length) return;
    let band = null;
    if (state.mode === 'floor') {
      const f = (state.db.floors || []).find(item => item.index === state.floor);
      if (f) band = f.band;
    }
    rows.forEach(rec => {
      if (hiddenTypes.has(rec.type)) return;
      if (band && rec.p.length > 2) {
        const [lo, hi] = band;
        const z = rec.p[2];
        if ((lo != null && z < lo - 200) || (hi != null && z > hi + 200)) return;
      }
      const [sx, sy] = view.pt(rec.p[0], rec.p[1]);
      if (sx < -30 || sy < -30 || sx > view.w + 30 || sy > view.h + 30) return;
      const isSel = state.selected?.kind === kind && state.selected?.id === rec.id;
      const isBarrel = kind === 'barrels';
      const solid = !isBarrel || rec.interaction;
      const color = isBarrel ? (solid ? VP_COLORS.barrels : '#94a3b8') : VP_COLORS.hidespots;
      const r = isSel ? 8 : (isBarrel ? 5.2 : 6.2);

      ctx.save();
      ctx.beginPath();
      if (isBarrel) {
        // 菱形：和普通圆形任务点位一眼分开；灰空心 = 只有空间标记、不可交互
        ctx.moveTo(sx, sy - r);
        ctx.lineTo(sx + r, sy);
        ctx.lineTo(sx, sy + r);
        ctx.lineTo(sx - r, sy);
        ctx.closePath();
        ctx.fillStyle = hexToRgba(color, solid ? 0.85 : 0.3);
      } else {
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba(color, 0.22);
      }
      ctx.fill();
      ctx.lineWidth = isSel ? 2.6 : 1.3;
      ctx.strokeStyle = isSel ? '#f59e0b' : color;
      ctx.stroke();
      ctx.restore();

      hitTargets.push({ kind, id: rec.id, cx: sx, cy: sy, r: r + 4 });
    });
  }

  // ---- 坐标定位：一次只保留一个点，定位下一个会自动清掉上一个 ----
  const COORD_COLOR = '#facc15';
  const coordInput = document.getElementById('coordInput');

  function fmtNum(v) {
    if (v == null || Number.isNaN(v)) return '-';
    return Number(v.toFixed ? v.toFixed(1) : v).toString();
  }

  function roomAtWorld(x, y) {
    let best = null;
    (state.db?.rooms || []).forEach(r => {
      const inside = (r.hulls || []).some(h => pointInPoly(x, y, h));
      if (inside && (!best || (r.area || 0) < (best.area || 0))) best = r;
    });
    return best;
  }

  function floorOfZ(z) {
    if (z == null) return null;
    const f = (state.db?.floors || []).find(item => {
      const band = item.band || [];
      const [lo, hi] = band;
      if (lo == null || hi == null) return false;
      return z >= lo - 200 && z <= hi + 200;
    });
    return f || null;
  }

  function outsideBBox(x, y) {
    const box = state.db?.bbox;
    if (!box) return false;
    const m = 200;
    return x < box[0] - m || x > box[2] + m || y < box[1] - m || y > box[3] + m;
  }

  function parseCoord(text) {
    const nums = (String(text).match(/-?\d+(?:\.\d+)?/g) || []);
    if (nums.length < 2) return null;
    return [Number(nums[0]), Number(nums[1]), nums.length > 2 ? Number(nums[2]) : null];
  }

  function locateCoord() {
    if (!state.db) {
      showToast('地图还没加载好，等一下再定位');
      return;
    }
    const p = parseCoord(coordInput.value);
    if (!p) {
      coordInput.classList.add('bad');
      showToast('坐标至少要两个数：x, y（例如 -139.2, -829.9, 369.2）');
      return;
    }
    coordInput.classList.remove('bad');
    coordInput.value = `${fmtNum(p[0])}, ${fmtNum(p[1])}${p[2] == null ? '' : ', ' + fmtNum(p[2])}`;

    const room = roomAtWorld(p[0], p[1]);
    const floor = floorOfZ(p[2]);
    // 每次定位都重建，旧的点自动消失（同一时刻只展示一个坐标点）
    state.coordTarget = {
      p,
      room: room ? room.raw : null,
      roomName: room ? roomDisplayName(room) : '',
      floorLabel: floor ? floor.label : null,
    };
    state.selected = { kind: 'coord', id: 0 };
    view.centerOnWorld(p[0], p[1]);
    updateInspector(false);
    requestRender();
    const coordTxt = `(${fmtNum(p[0])}, ${fmtNum(p[1])}` +
      (p[2] == null ? ')' : `, ${fmtNum(p[2])})`);
    let msg = floor
      ? `已定位到 ${floor.label}${room ? ' · ' + room.raw : ''}`
      : `已标出坐标点 ${coordTxt}`;
    if (outsideBBox(p[0], p[1])) msg += '（该坐标在本图范围外）';
    showToast(msg);
  }

  function clearCoordTarget() {
    if (!state.coordTarget) return;
    state.coordTarget = null;
    if (state.selected?.kind === 'coord') state.selected = null;
    coordInput.value = '';
    coordInput.classList.remove('bad');
    updateInspector(false);
    requestRender();
    showToast('已清除坐标点');
  }

  function drawCoordTarget() {
    const m = state.coordTarget;
    if (!m) return;
    const [sx, sy] = view.pt(m.p[0], m.p[1]);
    const isSel = state.selected?.kind === 'coord';

    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, sy, 24, 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(COORD_COLOR, 0.18);
    ctx.fill();

    ctx.strokeStyle = hexToRgba(COORD_COLOR, 0.9);
    ctx.lineWidth = 1.6;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(sx - 30, sy); ctx.lineTo(sx - 11, sy);
    ctx.moveTo(sx + 11, sy); ctx.lineTo(sx + 30, sy);
    ctx.moveTo(sx, sy - 30); ctx.lineTo(sx, sy - 11);
    ctx.moveTo(sx, sy + 11); ctx.lineTo(sx, sy + 30);
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(sx, sy, isSel ? 10 : 8.5, 0, Math.PI * 2);
    ctx.fillStyle = COORD_COLOR;
    ctx.fill();
    ctx.lineWidth = isSel ? 3 : 2;
    ctx.strokeStyle = isSel ? '#ffffff' : 'rgba(11,17,32,0.9)';
    ctx.stroke();

    const label = `坐标点 (${fmtNum(m.p[0])}, ${fmtNum(m.p[1])}` +
      (m.p[2] == null ? ')' : `, ${fmtNum(m.p[2])})`);
    ctx.font = 'bold 11.5px "Microsoft YaHei UI", sans-serif';
    ctx.textAlign = 'left';
    ctx.lineWidth = 3.5;
    ctx.strokeStyle = state.lightTheme ? 'rgba(255,255,255,0.92)' : 'rgba(11,17,32,0.95)';
    ctx.strokeText(label, sx + 16, sy);
    ctx.fillStyle = COORD_COLOR;
    ctx.fillText(label, sx + 16, sy);
    ctx.restore();

    hitTargets.push({ kind: 'coord', id: 0, cx: sx, cy: sy, r: 14 });
  }

  function drawPoly(pts) {
    if (pts.length < 3) return;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) {
      ctx.lineTo(pts[i][0], pts[i][1]);
    }
    ctx.closePath();
  }

  function roomScreenBBox(room) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    room.hulls.forEach(h => {
      h.forEach(([x, y]) => {
        const [px, py] = view.pt(x, y);
        if (px < x0) x0 = px;
        if (py < y0) y0 = py;
        if (px > x1) x1 = px;
        if (py > y1) y1 = py;
      });
    });
    return [x0, y0, x1, y1];
  }

  function pickAt(sx, sy) {
    for (let i = hitTargets.length - 1; i >= 0; i--) {
      const t = hitTargets[i];
      if (t.kind === 'seed' || t.kind === 'point' || t.kind === 'coord' ||
          t.kind === 'barrels' || t.kind === 'hidespots') {
        if (Math.hypot(sx - t.cx, sy - t.cy) <= t.r) return { kind: t.kind, id: t.id };
      } else if (t.kind === 'door') {
        if (distToSegment(sx, sy, t.p1, t.p2) <= 6) return { kind: 'door', id: t.id };
      } else if (t.kind === 'stair') {
        if (distToSegment(sx, sy, t.p1, t.p2) <= 8) return { kind: 'stair', id: t.id };
      }
    }
    for (let i = hitTargets.length - 1; i >= 0; i--) {
      const t = hitTargets[i];
      if (t.kind === 'room' && pointInPoly(sx, sy, t.poly)) {
        return { kind: 'room', id: t.id };
      }
    }
    return null;
  }

  function distToSegment(px, py, p1, p2) {
    const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
    const l2 = dx * dx + dy * dy;
    const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - p1[0]) * dx + (py - p1[1]) * dy) / l2));
    return Math.hypot(px - (p1[0] + t * dx), py - (p1[1] + t * dy));
  }

  function pointInPoly(x, y, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
        inside = !inside;
      }
    }
    return inside;
  }

  function describeTarget(target) {
    if (!target || !state.db) return null;
    const db = state.db;
    if (target.kind === 'custom') return target.info || null;   // 3D 道具 / 结构网格
    if (target.kind === 'coord') {
      const m = state.coordTarget;
      if (!m) return null;
      return {
        title: `定位点 · (${fmtNum(m.p[0])}, ${fmtNum(m.p[1])}` +
          (m.p[2] == null ? ')' : `, ${fmtNum(m.p[2])})`),
        sub: `坐标: (${m.p.map(fmtNum).join(', ')})  |  楼层: ${m.floorLabel || '-'}` +
          `  |  房间: ${m.room ? `${m.room}${m.roomName ? ' (' + m.roomName + ')' : ''}` : '不在任何房间轮廓内'}`,
        copyRaw: `${fmtNum(m.p[0])}, ${fmtNum(m.p[1])}` +
          (m.p[2] == null ? '' : `, ${fmtNum(m.p[2])}`),
      };
    }
    if (target.kind === 'room') {
      const r = db.rooms[target.id];
      if (!r) return null;
      const fls = (r.floors || []).map(floorLabel).join('/') || '-';
      const note = noteOf('rooms', r.raw);
      return {
        title: `${roomDisplayName(r)}  ${r.name_zh ? `(${r.name_zh})` : ''}  [${r.kind}]`,
        sub: `raw: ${r.raw}  |  分区: ${r.zone || '-'}  |  楼层: ${fls}  |  z: ${r.z[0]}~${r.z[1]}`,
        copyRaw: r.raw,
        noteKind: 'rooms',
        noteKey: r.raw,
        noteCurrent: note,
      };
    }
    if (target.kind === 'point') {
      const p = db.points[target.id];
      if (!p) return null;
      const room = p.room != null ? db.rooms[p.room] : null;
      const note = noteOf('points', p.actor);
      return {
        title: `${p.label_zh || p.label} #${p.num} · ${note || p.short}`,
        sub: `actor: ${p.actor}  |  房间: ${room ? room.raw : '-'}  |  坐标: (${p.p.join(', ')})`,
        copyRaw: p.actor,
        noteKind: 'points',
        noteKey: p.actor,
        noteCurrent: note,
      };
    }
    if (target.kind === 'door') {
      const d = db.doors[target.id];
      if (!d) return null;
      const meta = DOOR_KINDS[d.kind] || DOOR_KINDS.other;
      return {
        title: `门 · ${d.name} (${meta.label}${d.trial_only ? ' · 本关专属' : ''})`,
        sub: `类型: ${d.type}  |  坐标: (${d.p.join(', ')})`,
        copyRaw: d.name,
      };
    }
    if (target.kind === 'stair') {
      const s = (db.stairs || [])[target.id];
      if (!s) return null;
      const fls = (s.floors || []).map(floorLabel).join('/') || '-';
      return {
        title: `楼梯 · ${s.name || '#' + s.id}`,
        sub: `z: ${s.z[0]}~${s.z[1]}  |  楼层: ${fls}  |  宽: ${s.w}  |  台阶数: ${s.steps}`,
        copyRaw: s.name || '',
      };
    }
    if (target.kind === 'barrels' || target.kind === 'hidespots') {
      const rows = target.kind === 'barrels' ? db.barrels : db.hidespots;
      const r = (rows || [])[target.id];
      if (!r) return null;
      const room = roomAtWorld(r.p[0], r.p[1]);
      const floor = floorOfZ(r.p[2]);
      const isBarrel = target.kind === 'barrels';
      const tag = isBarrel
        ? (r.interaction ? '火桶候选 · 可交互落点' : '火桶候选 · 空间标记')
        : '隐藏点';
      const extra = isBarrel
        ? `  |  标签: ${(r.tags || []).join(', ') || '-'}` +
          `  |  可替换: ${r.replaceable ? '是' : '否'}`
        : '';
      return {
        title: `${tag} · ${r.name}`,
        sub: `类型: ${r.type}  |  坐标: (${r.p.join(', ')})` +
             `  |  房间: ${room ? room.raw : '-'}  |  楼层: ${floor ? floor.label : '-'}` +
             `  |  来源: ${r.file}${extra}`,
        copyRaw: `${r.p[0]}, ${r.p[1]}, ${r.p[2]}`,
      };
    }
    if (target.kind === 'seed') {
      const m = state.seedMarkers[target.id];
      if (!m) return null;
      const coordStr = m.p.join(', ');
      const name = m.label || m.badge || `点位 ${target.id + 1}`;
      const extra = m.badge && m.label ? `  |  值: ${m.badge}` : '';
      return {
        title: `分析点位 #${target.id + 1} · ${name}${m.exact ? '' : ' (≈房间中心)'}`,
        sub: `分组: ${m.section || m.kind || '-'}${extra}  |  房间: ${m.room || '-'}  |  坐标: (${coordStr})`,
        copyRaw: m.room || coordStr,
      };
    }
    return null;
  }

  function updateInspector(autoCopy = false) {
    const info = describeTarget(state.selected);
    document.querySelectorAll('.marker-chip').forEach((el, idx) => {
      el.classList.toggle('active', state.selected?.kind === 'seed' && state.selected?.id === idx);
    });

    if (!info) {
      inspTitle.textContent = '点击房间、点位或门查看详情（点击即自动复制原始名）';
      inspSub.textContent = '滚轮缩放 · 左/右键拖拽平移 · 双击房间或点位添加自定义备注';
      btnCopyRaw.disabled = true;
      btnEditNote.disabled = true;
      return;
    }
    inspTitle.textContent = info.title;
    inspSub.textContent = info.sub;
    btnCopyRaw.disabled = !info.copyRaw;
    btnEditNote.disabled = !info.noteKind;
    if (autoCopy && info.copyRaw) {
      copyText(info.copyRaw);
    }
  }

  let pendingNote = null;
  const noteModal = document.getElementById('noteModal');
  const noteModalInput = document.getElementById('noteModalInput');

  function openNoteModal(kind, key, title, current) {
    pendingNote = { kind, key };
    document.getElementById('noteModalTitle').textContent = title;
    noteModalInput.value = current || '';
    noteModal.classList.remove('hidden');
    setTimeout(() => {
      noteModalInput.focus();
      noteModalInput.select();
    }, 20);
  }

  async function saveNoteModal() {
    if (!pendingNote || !state.db) return;
    const text = noteModalInput.value.trim();
    const res = await fetch('/api/note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level: state.level,
        kind: pendingNote.kind,
        key: pendingNote.key,
        text,
      }),
    });
    const out = await res.json();
    if (out.ok) {
      const bucket = (state.db.notes = state.db.notes || {})[pendingNote.kind] = state.db.notes[pendingNote.kind] || {};
      if (text) bucket[pendingNote.key] = text;
      else delete bucket[pendingNote.key];
      buildLegend();
      updateInspector(false);
      requestRender();
      showToast(out.message);
    }
    noteModal.classList.add('hidden');
    pendingNote = null;
  }

  document.getElementById('btnNoteSave').addEventListener('click', saveNoteModal);
  document.getElementById('btnNoteCancel').addEventListener('click', () => {
    noteModal.classList.add('hidden');
    pendingNote = null;
  });
  noteModalInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') saveNoteModal();
    if (e.key === 'Escape') {
      noteModal.classList.add('hidden');
      pendingNote = null;
    }
  });

  let dragStart = null;
  let dragged = false;

  canvas.addEventListener('mousedown', (e) => {
    if (e.button === 0 || e.button === 1 || e.button === 2) {
      dragStart = { x: e.offsetX, y: e.offsetY, lastX: e.offsetX, lastY: e.offsetY, button: e.button };
      dragged = false;
    }
  });

  window.addEventListener('mousemove', (e) => {
    if (state.mode === '3d') return;      // 3D 画布自己处理旋转/拾取
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (dragStart) {
      if (!dragged && Math.hypot(x - dragStart.x, y - dragStart.y) > 4) {
        dragged = true;
        hoverTooltip.classList.add('hidden');
      }
      if (dragged) {
        view.panBy(x - dragStart.lastX, y - dragStart.lastY);
        dragStart.lastX = x;
        dragStart.lastY = y;
        requestRender();
      }
      return;
    }

    if (x < 0 || y < 0 || x > view.w || y > view.h) {
      hoverTooltip.classList.add('hidden');
      return;
    }
    const hit = pickAt(x, y);
    if (hit?.kind !== state.hovered?.kind || hit?.id !== state.hovered?.id) {
      state.hovered = hit;
      requestRender();
    }
    if (hit) {
      const desc = describeTarget(hit);
      if (desc) {
        hoverTooltip.innerHTML = `<strong>${desc.title}</strong><div style="color:var(--muted);margin-top:2px">${desc.sub}</div>`;
        hoverTooltip.style.left = `${Math.min(view.w - 280, x + 14)}px`;
        hoverTooltip.style.top = `${Math.max(12, y - 18)}px`;
        hoverTooltip.classList.remove('hidden');
      }
    } else {
      hoverTooltip.classList.add('hidden');
    }
  });

  window.addEventListener('mouseup', (e) => {
    if (state.mode === '3d') return;
    if (!dragStart) return;
    const wasDragged = dragged;
    const btn = dragStart.button;
    dragStart = null;
    if (!wasDragged && btn === 0) {
      const rect = canvas.getBoundingClientRect();
      const hit = pickAt(e.clientX - rect.left, e.clientY - rect.top);
      state.selected = hit;
      updateInspector(true);
      requestRender();
    }
  });

  canvas.addEventListener('contextmenu', (e) => e.preventDefault());

  canvas.addEventListener('dblclick', (e) => {
    const hit = pickAt(e.offsetX, e.offsetY);
    if (!hit) return;
    state.selected = hit;
    updateInspector(false);
    const desc = describeTarget(hit);
    if (desc?.noteKind) {
      openNoteModal(desc.noteKind, desc.noteKey, `编辑备注 — ${desc.title}`, desc.noteCurrent);
    }
  });

  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.14 : 1 / 1.14;
    view.zoomAt(e.offsetX, e.offsetY, factor);
    requestRender();
  }, { passive: false });

  document.querySelectorAll('#modeSwitch button').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.mode;
      if (next === '3d' && window.Map3D && !window.Map3D.available) {
        showToast('本环境不支持 WebGL，3D 模式不可用');
        return;
      }
      if (next === '3d' && state.mode !== '3d') state.prev2dMode = state.mode;
      state.mode = next;
      syncModeUI();
      requestRender();
    });
  });

  levelSelect.addEventListener('change', async () => {
    const lv = levelSelect.value;
    /* 手动挑关卡 = 只锁当前这一局，不改「跟随游戏」开关，也不写进 config；
       下一局开始时后端会自动恢复跟随 */
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: lv }),
    });
    loadMap(lv, true);
  });

  document.getElementById('mapHint').addEventListener('click', async (e) => {
    const lv = e.currentTarget.dataset.level;
    if (!lv) return;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ follow_game: true }),
    });
    state.followGame = true;
    document.getElementById('chkFollow').checked = true;
    e.currentTarget.classList.add('hidden');
    await loadMap(lv, true);
  });

  document.getElementById('chkFollow').addEventListener('change', async (e) => {
    state.followGame = e.target.checked;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ follow_game: state.followGame }),
    });
    if (state.followGame) pollState(true);
  });

  document.getElementById('chkDoors').addEventListener('change', (e) => {
    state.showDoors = e.target.checked;
    requestRender();
  });
  document.getElementById('chkStairs').addEventListener('change', (e) => {
    state.showStairs = e.target.checked;
    requestRender();
  });
  document.getElementById('chkPoints').addEventListener('change', (e) => {
    state.showPoints = e.target.checked;
    requestRender();
  });
  document.getElementById('chkAllNames').addEventListener('change', (e) => {
    state.showAllNames = e.target.checked;
    requestRender();
  });
  document.getElementById('chkSeed').addEventListener('change', (e) => {
    state.showSeed = e.target.checked;
    requestRender();
  });
  document.getElementById('chkLegend').addEventListener('change', (e) => {
    state.showLegend = e.target.checked;
    legendCard.classList.toggle('hidden', !state.showLegend);
  });
  document.getElementById('chkBarrels').addEventListener('change', (e) => {
    state.showBarrels = e.target.checked;
    syncVariatorPills();
    requestRender();
  });
  document.getElementById('chkHidespots').addEventListener('change', (e) => {
    state.showHidespots = e.target.checked;
    syncVariatorPills();
    requestRender();
  });

  document.getElementById('btnShowAllZones').addEventListener('click', () => {
    state.hiddenZones.clear();
    buildLegend();
    requestRender();
  });
  document.getElementById('btnShowAllBarrelTypes').addEventListener('click', () => {
    state.hiddenBarrelTypes.clear();
    buildVariatorTypeLegend();
    requestRender();
  });
  document.getElementById('btnShowAllHideTypes').addEventListener('click', () => {
    state.hiddenHideTypes.clear();
    buildVariatorTypeLegend();
    requestRender();
  });

  document.getElementById('btnCoordGo').addEventListener('click', locateCoord);
  document.getElementById('btnCoordClear').addEventListener('click', clearCoordTarget);
  coordInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      locateCoord();
      coordInput.blur();
    } else if (e.key === 'Escape') {
      if (state.coordTarget) clearCoordTarget();
      coordInput.blur();
    }
    e.stopPropagation();
  });

  document.getElementById('btnRotate').addEventListener('click', () => {
    view.turns = (view.turns + 1) % 4;
    view.fit();
    requestRender();
  });

  document.getElementById('btnMirror').addEventListener('click', () => {
    view.flipx = !view.flipx;
    view.fit();
    requestRender();
  });

  document.getElementById('btnFit').addEventListener('click', () => {
    view.fit();
    requestRender();
  });

  document.getElementById('btnTheme').addEventListener('click', (e) => {
    state.lightTheme = !state.lightTheme;
    document.body.classList.toggle('light-theme', state.lightTheme);
    e.target.textContent = state.lightTheme ? '☀️' : '🌙';
    requestRender();
  });

  document.getElementById('btnHideWin').addEventListener('click', () => {
    fetch('/api/window/hide', { method: 'POST' });
  });

  btnCopyRaw.addEventListener('click', () => {
    const desc = describeTarget(state.selected);
    if (desc?.copyRaw) copyText(desc.copyRaw);
  });

  btnEditNote.addEventListener('click', () => {
    const desc = describeTarget(state.selected);
    if (desc?.noteKind) {
      openNoteModal(desc.noteKind, desc.noteKey, `编辑备注 — ${desc.title}`, desc.noteCurrent);
    }
  });

  document.getElementById('btnRefreshSeed').addEventListener('click', () => pollState(true));
  document.getElementById('btnCopySeedLine').addEventListener('click', () => copySeedLine());
  document.getElementById('btnCopySeed').addEventListener('click', () => {
    const txt = document.getElementById('seedText').innerText;
    copyText(txt);
  });

  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (!noteModal.classList.contains('hidden')) return;

    const k = e.key.toLowerCase();
    if (k === 'd') { toggle3D(); return; }        // 2D ⇄ 3D
    if (state.mode === '3d') {
      if (k === 'o') {
        state.mode = state.prev2dMode || 'overlay';
        syncModeUI(); requestRender(); return;
      }
      if (k === 'f') { window.Map3D?.resetView(); return; }
      if (k === 't') { window.Map3D?.rotate(Math.PI / 2); return; }
      if (k === 'x') { document.getElementById('btnMirror').click(); return; }
      if (['1', '2', '3', '4'].includes(k)) {
        const idx = parseInt(k, 10) - 1;
        if (state.db && idx < (state.db.floors || []).length) {
          state.floor = idx;
          syncModeUI(); requestRender();
        }
        return;
      }
    }
    if (k === 'f') { view.fit(); requestRender(); }
    else if (k === 't') { document.getElementById('btnRotate').click(); }
    else if (k === 'x') { document.getElementById('btnMirror').click(); }
    else if (k === 'o') { state.mode = 'overlay'; syncModeUI(); requestRender(); }
    else if (k === 'h') {
      const chk = document.getElementById('chkLegend');
      chk.checked = !chk.checked;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 's') {
      const chk = document.getElementById('chkSeed');
      chk.checked = !chk.checked;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 'b') {
      const chk = document.getElementById('chkBarrels');
      chk.checked = !chk.checked;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 'v') {
      const chk = document.getElementById('chkHidespots');
      chk.checked = !chk.checked;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 'l') {
      const chk = document.getElementById('chkFollow');
      chk.checked = true;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 'r') { pollState(true); }
    else if (k === 'c') { copySeedLine(); }
    else if (k === 'n') { if (!btnEditNote.disabled) btnEditNote.click(); }
    else if (k === 'g') { coordInput.focus(); coordInput.select(); }
    else if (k === 'escape') { state.selected = null; updateInspector(); requestRender(); }
    else if (['1', '2', '3', '4'].includes(k)) {
      const idx = parseInt(k, 10) - 1;
      if (state.db && idx < (state.db.floors || []).length) {
        state.mode = 'floor';
        state.floor = idx;
        syncModeUI();
        requestRender();
      }
    }
  });

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  /* 右侧「本局关卡变量」：中文名来自 data/variators.json，点一下直接开对应图层 */
  function renderVariators() {
    const bar = document.getElementById('variatorBar');
    const box = document.getElementById('variatorChips');
    const meta = document.getElementById('variatorMeta');
    if (!state.variators.length) {
      bar.classList.add('hidden');
      box.innerHTML = '';
      meta.textContent = '';
      return;
    }
    bar.classList.remove('hidden');
    meta.textContent = `${state.variators.length} 个 · 来自 OPP.log`;
    box.innerHTML = state.variators.map(v => {
      const layerName = v.layer === 'barrels' ? '火桶点位'
        : (v.layer === 'hidespots' ? '隐藏点' : '');
      return `<span class="variator-chip${v.layer ? ' has-layer' : ''}" ` +
             `title="ID: ${escapeHtml(v.id)}${layerName ? ' · 对应图层: ' + layerName : ''}">` +
             `${escapeHtml(v.name)}${layerName ? `<small> · ${layerName}</small>` : ''}</span>`;
    }).join('');
    box.querySelectorAll('.variator-chip').forEach((el, i) => {
      el.addEventListener('click', () => {
        const layer = state.variators[i]?.layer;
        if (!layer) return;
        const chk = document.getElementById(layer === 'barrels' ? 'chkBarrels' : 'chkHidespots');
        chk.checked = true;
        chk.dispatchEvent(new Event('change'));
      });
    });
  }

  /* 图例里按 actor 类型单独切换显示（火桶候选很多时可以只看某一类） */
  function buildVariatorTypeLegend() {
    const cfg = [
      ['barrelTypeList', 'barrels', state.hiddenBarrelTypes],
      ['hideTypeList', 'hidespots', state.hiddenHideTypes],
    ];
    cfg.forEach(([elId, key, hidden]) => {
      const el = document.getElementById(elId);
      if (!el) return;
      const counts = new Map();
      (state.db?.[key] || []).forEach(r =>
        counts.set(r.type, (counts.get(r.type) || 0) + 1));
      if (!counts.size) {
        el.innerHTML = '<div class="type-legend-empty">本关暂无点位数据（先跑 variatorpoints.py）</div>';
        return;
      }
      el.innerHTML = [...counts.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([type, n]) => {
          const color = key === 'barrels' ? VP_COLORS.barrels : VP_COLORS.hidespots;
          return `<div class="type-legend-row${hidden.has(type) ? ' hidden-zone' : ''}" ` +
                 `data-type="${encodeURIComponent(type)}" title="点击切换显示该类点位">` +
                 `<span class="type-legend-dot" style="background:${color}"></span>` +
                 `<span style="flex:1">${escapeHtml(type.replace(/_BP_C$/, ''))}</span>` +
                 `<span>${n}</span></div>`;
        }).join('');
      el.querySelectorAll('.type-legend-row').forEach(row => {
        row.addEventListener('click', () => {
          const type = decodeURIComponent(row.dataset.type);
          if (hidden.has(type)) hidden.delete(type);
          else hidden.add(type);
          buildVariatorTypeLegend();
          requestRender();
        });
      });
    });
  }

  function syncVariatorPills() {
    document.getElementById('pillBarrels').classList.toggle('active-layer', state.showBarrels);
    document.getElementById('pillHidespots').classList.toggle('active-layer', state.showHidespots);
  }

  /* 本局变数命中火桶/隐藏点图层时自动打开一次；用户手动关掉后不再抢 */
  function syncVariatorLayers() {
    const key = `${state.level}|${state.seedLine}|${state.variators.map(v => v.id).join(',')}`;
    if (state.autoVariatorLayersFor === key) return;
    const layers = new Set(state.variators.map(v => v.layer).filter(Boolean));
    if (!layers.size) return;
    state.autoVariatorLayersFor = key;
    if (layers.has('barrels') && (state.db?.barrels || []).length) {
      state.showBarrels = true;
      document.getElementById('chkBarrels').checked = true;
    }
    if (layers.has('hidespots') && (state.db?.hidespots || []).length) {
      state.showHidespots = true;
      document.getElementById('chkHidespots').checked = true;
    }
    syncVariatorPills();
    requestRender();
  }

  function renderSeedText(text, ok) {
    const pre = document.getElementById('seedText');
    if (!text) {
      pre.textContent = '暂无内容';
      return;
    }
    const html = text.split('\n').map(line => {
      const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      if (!ok) return `<span class="seed-line-err">${escaped}</span>`;
      if (line.startsWith('!')) return `<span class="seed-line-warn">${escaped}</span>`;
      if (line.includes('密码') || line.includes('答案')) return `<span class="seed-line-ans">${escaped}</span>`;
      return escaped;
    }).join('\n');
    pre.innerHTML = html;
  }

  /* 有分析点位时：默认关掉普通任务点位（每个分析批次只自动关一次，用户手动打开后不再抢） */
  function syncAnalysisToggle() {
    const an = state.analysis;
    const hasAnalysis = Boolean(an && an.points && an.points.length && an.hide_points !== false);
    const chkPoints = document.getElementById('chkPoints');
    if (hasAnalysis) {
      const key = `${an.level || ''}|${state.seedLine || ''}`;
      if (state.autoHiddenPointsFor !== key) {
        state.autoHiddenPointsFor = key;
        state.showPoints = false;
        chkPoints.checked = false;
        state.showSeed = true;
        document.getElementById('chkSeed').checked = true;
      }
    } else if (state.autoHiddenPointsFor !== null) {
      state.autoHiddenPointsFor = null;
      state.showPoints = true;
      chkPoints.checked = true;
    }
  }

  async function pollState(force = false) {
    try {
      const res = await fetch('/api/state');
      const data = await res.json();

      const hkInfo = data.hotkey ? `快捷键 ${data.hotkey}${data.is_admin ? ' (管理员)' : ''}` : '快捷键已关';
      document.getElementById('seedFootInfo').textContent = hkInfo;
      state.seedLine = data.seed_line || '';
      document.getElementById('btnCopySeedLine').disabled = !state.seedLine;

      if (data.follow_game !== undefined) {
        state.followGame = !!data.follow_game;
        document.getElementById('chkFollow').checked = state.followGame;
      }

      if (data.active_level && data.active_level !== state.level) {
        await loadMap(data.active_level, true);
      }

      /* 日志已经换了关卡、但地图没跟着换（跟随关掉或加载失败）→ 给一个一键切过去的按钮 */
      const hint = document.getElementById('mapHint');
      if (data.trial_level && data.trial_level !== state.level) {
        hint.textContent = `本局是 ${data.trial_level} · 点此切图`;
        hint.dataset.level = data.trial_level;
        hint.classList.remove('hidden');
      } else {
        hint.classList.add('hidden');
      }

      const sig = JSON.stringify([data.gamelog, data.seed?.seed, data.active_level]);
      if (!force && sig === state.lastSeedSig) return;
      state.lastSeedSig = sig;

      if (data.active_level) levelSelect.value = data.active_level;

      const info = data.gamelog;
      const badge = document.getElementById('seedStatusBadge');
      const meta = document.getElementById('seedMeta');

      const statusMap = { loading: '加载中', ready: '准备中', started: '进行中', ended: '已结束' };
      if (info) {
        badge.textContent = statusMap[info.status] || info.status;
        meta.textContent = `${info.trial} · seed ${info.seed} · ${info.players}P · ${info.difficulty} (${info.time})`;
        if (data.trial_has_map === false) {
          meta.textContent += ' · 该关卡暂无地图数据';
        }
      } else {
        badge.textContent = '无对局';
        meta.textContent = '尚未在 OPP.log 中读到对局信息';
      }

      renderSeedText(data.seed?.text || '', data.seed?.ok);

      state.seedMarkers = data.seed_markers || [];
      state.analysis = data.analysis || null;
      document.getElementById('lblSeedCount').textContent =
        `分析点位 (${state.seedMarkers.length})`;

      /* 房间高亮：seed 里的房间名格式和地图 raw 名不一定一致（Room-8-3 vs RBRoom8_3），
         所以优先用坐标反查所在房间，查不到再退回原始房间名 */
      state.analysisRoomColor = new Map();
      state.seedMarkers.forEach(m => {
        if (!m.color) return;
        let room = m.room || '';
        if (m.p && m.p.length > 1) {
          const hit = roomAtWorld(m.p[0], m.p[1]);
          if (hit && hit.raw) room = hit.raw;
        }
        if (room && !state.analysisRoomColor.has(room)) {
          state.analysisRoomColor.set(room, m.color);
        }
      });
      syncAnalysisToggle();

      state.variators = data.variators || [];
      renderVariators();
      syncVariatorLayers();

      const markersBar = document.getElementById('seedMarkersBar');
      const chips = document.getElementById('markerChips');
      const legendBox = document.getElementById('analysisLegend');
      chips.innerHTML = '';
      legendBox.innerHTML = '';
      if (state.seedMarkers.length) {
        markersBar.classList.remove('hidden');
        (state.analysis?.legend || []).forEach(item => {
          const span = document.createElement('span');
          span.className = 'legend-dot';
          span.innerHTML = `<i style="background:${item.color}"></i>${item.label}`;
          legendBox.appendChild(span);
        });
        state.seedMarkers.forEach((m, i) => {
          const chip = document.createElement('button');
          chip.className = 'marker-chip';
          if (m.color) chip.style.borderColor = m.color;
          const name = m.label || m.badge || '点位';
          chip.textContent = m.badge && m.label
            ? `${name} ${m.badge}`
            : `${i + 1} ${name}`;
          chip.title = `${m.section || m.kind} · ${m.room || ''} (${m.p.join(', ')})`;
          chip.addEventListener('click', () => {
            state.selected = { kind: 'seed', id: i };
            view.centerOnWorld(m.p[0], m.p[1]);
            updateInspector(true);
            requestRender();
          });
          chips.appendChild(chip);
        });
      } else {
        markersBar.classList.add('hidden');
      }

      requestRender();
    } catch (e) {
      // 网络抖动忽略，但别的异常要能看见（否则地图/面板会静默不更新）
      console.error('pollState failed', e);
    }
  }

  async function init() {
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const lvRes = await fetch('/api/levels');
    const lvData = await lvRes.json();
    levelSelect.innerHTML = '';
    (lvData.levels || []).forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.level;
      opt.textContent = `${item.level} · ${item.name}`;
      levelSelect.appendChild(opt);
    });

    await pollState(true);
    if (!state.db && levelSelect.options.length) {
      await loadMap(levelSelect.options[0].value, true);
    }
    // ?mode=3d 可直接以 3D 打开（也方便无头浏览器截图自检）
    if (new URLSearchParams(location.search).get('mode') === '3d' && window.Map3D?.available) {
      state.prev2dMode = state.mode;
      state.mode = '3d';
      syncModeUI();
      requestRender();
      const v = new URLSearchParams(location.search).get('view');
      if (v) window.Map3D.setView(v);
    }
    setInterval(() => pollState(false), 900);
  }

  /* 3D 渲染器（3d.js）通过这层桥接复用 2D 的状态 / 检视面板 / 复制能力 */
  window.MapApp = {
    state, view,
    describe: describeTarget,
    showToast,
    requestRender,
    setMode(mode) { state.mode = mode; syncModeUI(); requestRender(); },
    select(target, autoCopy = true) {
      state.selected = target;
      updateInspector(autoCopy);
      requestRender();
    },
  };
  if (window.Map3D?.init) window.Map3D.init(window.MapApp);

  init();
})();
