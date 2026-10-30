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
    floor: 0,
    showDoors: true,
    showPoints: true,
    showAllNames: false,
    showSeed: true,
    showLegend: false,
    followGame: true,
    lightTheme: false,
    searchQuery: '',
    hiddenZones: new Set(),
    seedMarkers: [],
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

  async function copyText(text) {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      showToast(`已复制: ${text}`);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      showToast(`已复制: ${text}`);
    }
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
    if (fitView) view.fit();
    updateInspector();
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
        state.mode = 'floor';
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
      btn.classList.toggle('active', state.mode === 'floor' && state.floor === idx);
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
  function requestRender() {
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
    requestRender();
  }

  function render() {
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
    const q = state.searchQuery.trim().toLowerCase();

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
      const isMatched = q && (
        r.raw.toLowerCase().includes(q) ||
        (r.name || '').toLowerCase().includes(q) ||
        (r.name_zh || '').toLowerCase().includes(q) ||
        noteOf('rooms', r.raw).toLowerCase().includes(q)
      );

      let fillAlpha = r.kind === 'corridor' ? 0.14 : 0.26;
      if (state.lightTheme) fillAlpha = r.kind === 'corridor' ? 0.16 : 0.28;

      let fill = r.zone ? hexToRgba(zColor, fillAlpha) : (state.lightTheme ? '#e2e8f0' : '#1e293b');
      let stroke = r.zone ? hexToRgba(zColor, 0.85) : (state.lightTheme ? '#94a3b8' : '#475569');
      let lw = 1.5;

      if (isMatched) {
        fill = hexToRgba('#14b8a6', 0.42);
        stroke = '#14b8a6';
        lw = 2.6;
      }
      if (isHovered) {
        lw = 2.4;
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

    const pointRooms = new Set(points.map(p => p.room).filter(r => r != null));
    const seedRoomNames = new Set(state.seedMarkers.map(m => m.room).filter(Boolean));
    const placedBoxes = [];

    const labelCandidates = visibleRooms.filter(r =>
      state.showAllNames ||
      pointRooms.has(r.id) ||
      seedRoomNames.has(r.raw) ||
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
        const isSel = state.selected?.kind === 'point' && state.selected?.id === p.id;
        const r = isSel ? 12 : 9.5;

        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fillStyle = isGoal ? '#e11d48' : (state.lightTheme ? '#ffffff' : '#0f172a');
        ctx.fill();
        ctx.lineWidth = isSel ? 3 : 2;
        ctx.strokeStyle = isSel ? '#f59e0b' : zColor;
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
        const isGoal = m.kind === 'goal';
        const color = isGoal ? '#f43f5e' : '#14b8a6';
        const r = isSel ? 13 : 10.5;

        ctx.beginPath();
        ctx.arc(sx, sy, r + 4, 0, Math.PI * 2);
        ctx.fillStyle = hexToRgba(color, 0.25);
        ctx.fill();

        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = isSel ? 3 : 2;
        ctx.strokeStyle = isSel ? '#f59e0b' : '#ffffff';
        ctx.stroke();

        ctx.font = 'bold 10.5px Consolas, sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(String(i + 1), sx, sy + 0.5);

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

    const parts = [
      state.mode === 'overlay'
        ? `叠加 (${(db.floors || []).length}层)`
        : `分层 · ${floorLabel(state.floor)}`
    ];
    if (view.turns % 4) parts.push(`旋转 ${(view.turns % 4) * 90}°`);
    if (view.flipx) parts.push('镜像 X');
    viewBadge.textContent = parts.join(' · ');
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
      if (t.kind === 'seed' || t.kind === 'point') {
        if (Math.hypot(sx - t.cx, sy - t.cy) <= t.r) return { kind: t.kind, id: t.id };
      } else if (t.kind === 'door') {
        if (distToSegment(sx, sy, t.p1, t.p2) <= 6) return { kind: 'door', id: t.id };
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
    if (target.kind === 'seed') {
      const m = state.seedMarkers[target.id];
      if (!m) return null;
      const coordStr = m.p.join(', ');
      return {
        title: `本局标记 #${target.id + 1} · ${m.label}${m.exact ? '' : ' (≈房间中心)'}`,
        sub: `分组: ${m.section || '-'}  |  房间: ${m.room || '-'}  |  坐标: (${coordStr})`,
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
      state.mode = btn.dataset.mode;
      syncModeUI();
      requestRender();
    });
  });

  levelSelect.addEventListener('change', async () => {
    const lv = levelSelect.value;
    state.followGame = false;
    document.getElementById('chkFollow').checked = false;
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ follow_game: false, level: lv }),
    });
    loadMap(lv, true);
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

  document.getElementById('btnShowAllZones').addEventListener('click', () => {
    state.hiddenZones.clear();
    buildLegend();
    requestRender();
  });

  document.getElementById('searchInput').addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    requestRender();
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
  document.getElementById('btnCopySeed').addEventListener('click', () => {
    const txt = document.getElementById('seedText').innerText;
    copyText(txt);
  });

  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (!noteModal.classList.contains('hidden')) return;

    const k = e.key.toLowerCase();
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
    else if (k === 'l') {
      const chk = document.getElementById('chkFollow');
      chk.checked = true;
      chk.dispatchEvent(new Event('change'));
    }
    else if (k === 'r') { pollState(true); }
    else if (k === 'n') { if (!btnEditNote.disabled) btnEditNote.click(); }
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

  async function pollState(force = false) {
    try {
      const res = await fetch('/api/state');
      const data = await res.json();

      const hkInfo = data.hotkey ? `快捷键 ${data.hotkey}${data.is_admin ? ' (管理员)' : ''}` : '快捷键已关';
      document.getElementById('seedFootInfo').textContent = hkInfo;

      if (data.active_level && data.active_level !== state.level) {
        await loadMap(data.active_level, true);
      }

      const sig = JSON.stringify([data.gamelog, data.seed?.seed, data.active_level]);
      if (!force && sig === state.lastSeedSig) return;
      state.lastSeedSig = sig;

      const info = data.gamelog;
      const badge = document.getElementById('seedStatusBadge');
      const meta = document.getElementById('seedMeta');

      const statusMap = { loading: '加载中', ready: '准备中', started: '进行中', ended: '已结束' };
      if (info) {
        badge.textContent = statusMap[info.status] || info.status;
        meta.textContent = `${info.trial} · seed ${info.seed} · ${info.players}P · ${info.difficulty} (${info.time})`;
      } else {
        badge.textContent = '无对局';
        meta.textContent = '尚未在 OPP.log 中读到对局信息';
      }

      renderSeedText(data.seed?.text || '', data.seed?.ok);

      state.seedMarkers = data.seed_markers || [];
      document.getElementById('lblSeedCount').textContent = `本局标记 (${state.seedMarkers.length})`;

      const markersBar = document.getElementById('seedMarkersBar');
      const chips = document.getElementById('markerChips');
      chips.innerHTML = '';
      if (state.seedMarkers.length) {
        markersBar.classList.remove('hidden');
        state.seedMarkers.forEach((m, i) => {
          const chip = document.createElement('button');
          chip.className = 'marker-chip' + (m.kind === 'goal' ? ' goal' : '');
          chip.textContent = `#${i + 1} ${m.label}`;
          chip.title = `${m.section} · ${m.room || ''} (${m.p.join(', ')})`;
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
      // ignore transient network errors
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
    setInterval(() => pollState(false), 900);
  }

  init();
})();
