// Capability-map dependency graph for Cento Console.
// Exposes window.CodebaseIntelligenceGraph = { init(containerEl) }.
(function () {
  'use strict';

  var NODE_W = 162;
  var NODE_H = 44;
  var GRAPH_W = 1020;
  var GRAPH_H = 660;
  var MINIMAP_W = 190;
  var MINIMAP_H = 124;

  var TECH_COLORS = {
    shell:  '#ffb02e',
    python: '#4dd7d1',
    go:     '#61afef',
    html:   '#ff5a00',
    css:    '#c084fc',
    js:     '#e5c07b',
    json:   '#a89c91',
    sqlite: '#10b66a',
    swift:  '#ff6b9d',
  };

  var NODES = [
    { id: 'cli',        label: 'Cento CLI',          tech: 'shell',  x: 100,  y: 80  },
    { id: 'mobile',     label: 'Mobile / Watch Apps', tech: 'swift',  x: 510,  y: 80  },
    { id: 'tui',        label: 'Bubble Tea TUIs',     tech: 'go',     x: 870,  y: 80  },
    { id: 'mcp',        label: 'MCP Server',          tech: 'python', x: 200,  y: 210 },
    { id: 'bridge',     label: 'Cluster Bridge',      tech: 'go',     x: 480,  y: 210 },
    { id: 'console',    label: 'Cento Console',       tech: 'js',     x: 780,  y: 210 },
    { id: 'taskstream', label: 'Taskstream',          tech: 'python', x: 130,  y: 340 },
    { id: 'factory',    label: 'Factory',             tech: 'python', x: 400,  y: 340 },
    { id: 'templates',  label: 'Templates',           tech: 'html',   x: 660,  y: 340 },
    { id: 'docs',       label: 'Docs',                tech: 'html',   x: 910,  y: 340 },
    { id: 'crm',        label: 'CRM / Consulting',    tech: 'python', x: 120,  y: 470 },
    { id: 'storage',    label: 'Storage Catalog',     tech: 'sqlite', x: 370,  y: 470 },
    { id: 'tests',      label: 'Tests / E2E',         tech: 'python', x: 630,  y: 470 },
    { id: 'workspace',  label: 'Workspace / Runs',    tech: 'json',   x: 880,  y: 470 },
    { id: 'redmine',    label: 'Redmine DB',          tech: 'sqlite', x: 250,  y: 590 },
  ];

  var EDGES = [
    { from: 'cli',        to: 'mcp',        label: 'loads'      },
    { from: 'cli',        to: 'bridge',     label: 'registers'  },
    { from: 'cli',        to: 'taskstream', label: 'dispatches' },
    { from: 'cli',        to: 'factory',    label: 'dispatches' },
    { from: 'mobile',     to: 'mcp',        label: 'registers'  },
    { from: 'tui',        to: 'taskstream', label: 'enables'    },
    { from: 'mcp',        to: 'taskstream', label: 'enables'    },
    { from: 'mcp',        to: 'factory',    label: 'enables'    },
    { from: 'bridge',     to: 'factory',    label: 'dispatches' },
    { from: 'console',    to: 'taskstream', label: 'serves UI'  },
    { from: 'console',    to: 'templates',  label: 'loads'      },
    { from: 'console',    to: 'docs',       label: 'serves UI'  },
    { from: 'taskstream', to: 'storage',    label: 'persists'   },
    { from: 'factory',    to: 'workspace',  label: 'writes'     },
    { from: 'factory',    to: 'tests',      label: 'enables'    },
    { from: 'crm',        to: 'taskstream', label: 'creates'    },
    { from: 'storage',    to: 'redmine',    label: 'indexes'    },
    { from: 'tests',      to: 'factory',    label: 'enables'    },
    { from: 'docs',       to: 'templates',  label: 'documents'  },
  ];

  // Build node lookup once.
  var nodeMap = {};
  NODES.forEach(function (n) { nodeMap[n.id] = n; });

  function boxExitPoint(cx, cy, hw, hh, tx, ty) {
    var dx = tx - cx;
    var dy = ty - cy;
    if (dx === 0 && dy === 0) return { x: cx + hw, y: cy };
    var tx1 = dx !== 0 ? hw / Math.abs(dx) : Infinity;
    var ty1 = dy !== 0 ? hh / Math.abs(dy) : Infinity;
    var t = Math.min(tx1, ty1);
    return { x: cx + t * dx, y: cy + t * dy };
  }

  function edgeEndpoints(fn, tn) {
    var hw = NODE_W / 2;
    var hh = NODE_H / 2;
    var src = boxExitPoint(fn.x, fn.y, hw, hh, tn.x, tn.y);
    var dst = boxExitPoint(tn.x, tn.y, hw, hh, fn.x, fn.y);
    return { sx: src.x, sy: src.y, ex: dst.x, ey: dst.y };
  }

  function injectStyles() {
    if (document.getElementById('cig-styles')) return;
    var s = document.createElement('style');
    s.id = 'cig-styles';
    s.textContent = [
      '.cig-wrapper{display:flex;flex-direction:column;gap:.6rem;height:100%}',
      '.cig-filters{display:flex;flex-wrap:wrap;gap:.35rem;padding:.4rem 0;border-bottom:1px solid #2d211a}',
      '.cig-filter-btn{padding:.28rem .6rem;font-size:.77rem;font-weight:700;',
        'font-family:"IBM Plex Mono",ui-monospace,monospace;',
        'border:1px solid #2d211a;background:#0b0b0a;color:#a89c91;border-radius:2px;',
        'cursor:pointer;transition:border-color .12s,color .12s}',
      '.cig-filter-btn:hover{border-color:var(--cig-tc,#c74700);color:var(--cig-tc,#ff5a00)}',
      '.cig-filter-btn.active{border-color:var(--cig-tc,#ff5a00);color:var(--cig-tc,#ff5a00);',
        'background:rgba(255,90,0,.08)}',
      '.cig-canvas-wrap{position:relative;flex:1;min-height:480px;height:520px;',
        'border:1px solid #2d211a;background:#050403;overflow:hidden}',
      '.cig-canvas{display:block;cursor:grab;outline:none}',
      '.cig-canvas:focus-visible{outline:1px solid #c74700;outline-offset:-1px}',
      '.cig-minimap{position:absolute;bottom:.6rem;right:.6rem;border:1px solid #2d211a;',
        'pointer-events:none;opacity:.88;border-radius:2px}',
      '.cig-zoom{position:absolute;top:.6rem;right:.6rem;display:flex;flex-direction:column;gap:2px}',
      '.cig-zoom button{width:2rem;height:2rem;padding:0;font-size:1.05rem;line-height:1;',
        'display:flex;align-items:center;justify-content:center;',
        'border:1px solid #2d211a;background:rgba(11,11,10,.9);color:#a89c91;',
        'border-radius:2px;cursor:pointer}',
      '.cig-zoom button:hover{border-color:#c74700;color:#ff5a00}',
    ].join('');
    document.head.appendChild(s);
  }

  function init(containerEl) {
    injectStyles();

    // --- DOM ---
    var wrapper = document.createElement('div');
    wrapper.className = 'cig-wrapper';

    var filterBar = document.createElement('div');
    filterBar.className = 'cig-filters';
    filterBar.setAttribute('role', 'toolbar');
    filterBar.setAttribute('aria-label', 'Filter by technology');

    var TECH_FILTERS = ['All', 'Python', 'Shell', 'Go', 'HTML', 'CSS', 'JS', 'JSON', 'SQLite'];
    var activeFilter = 'All';

    TECH_FILTERS.forEach(function (f) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cig-filter-btn' + (f === 'All' ? ' active' : '');
      btn.textContent = f;
      btn.setAttribute('aria-pressed', f === 'All' ? 'true' : 'false');
      var tc = TECH_COLORS[f.toLowerCase()];
      if (tc) btn.style.setProperty('--cig-tc', tc);
      btn.addEventListener('click', function () {
        activeFilter = f;
        filterBar.querySelectorAll('.cig-filter-btn').forEach(function (b) {
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        render();
      });
      filterBar.appendChild(btn);
    });

    var canvasWrap = document.createElement('div');
    canvasWrap.className = 'cig-canvas-wrap';

    var canvas = document.createElement('canvas');
    canvas.className = 'cig-canvas';
    canvas.setAttribute('tabindex', '0');
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Codebase dependency graph. Drag to pan, scroll to zoom.');
    canvasWrap.appendChild(canvas);

    var minimap = document.createElement('canvas');
    minimap.className = 'cig-minimap';
    minimap.width = MINIMAP_W;
    minimap.height = MINIMAP_H;
    minimap.setAttribute('aria-hidden', 'true');
    canvasWrap.appendChild(minimap);

    var zoomCtrl = document.createElement('div');
    zoomCtrl.className = 'cig-zoom';
    zoomCtrl.setAttribute('role', 'group');
    zoomCtrl.setAttribute('aria-label', 'Zoom controls');
    var btnIn = mkBtn('+', 'Zoom in');
    var btnOut = mkBtn('−', 'Zoom out');
    var btnReset = mkBtn('⊙', 'Reset zoom');
    zoomCtrl.appendChild(btnIn);
    zoomCtrl.appendChild(btnOut);
    zoomCtrl.appendChild(btnReset);
    canvasWrap.appendChild(zoomCtrl);

    wrapper.appendChild(filterBar);
    wrapper.appendChild(canvasWrap);
    containerEl.appendChild(wrapper);

    // --- State ---
    var zoom = 1;
    var panX = 0;
    var panY = 0;
    var dragging = false;
    var dragOrigin = null;
    var hoverId = null;

    // --- Helpers ---
    function screenToWorld(sx, sy) {
      return { x: (sx - panX) / zoom, y: (sy - panY) / zoom };
    }

    function nodeAt(sx, sy) {
      var w = screenToWorld(sx, sy);
      return NODES.find(function (n) {
        return w.x >= n.x - NODE_W / 2 && w.x <= n.x + NODE_W / 2 &&
               w.y >= n.y - NODE_H / 2 && w.y <= n.y + NODE_H / 2;
      }) || null;
    }

    function visible(node) {
      return activeFilter === 'All' || node.tech === activeFilter.toLowerCase();
    }

    // --- Render ---
    function render() {
      var ctx = canvas.getContext('2d');
      var W = canvas.width;
      var H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = '#050403';
      ctx.fillRect(0, 0, W, H);

      ctx.save();
      ctx.translate(panX, panY);
      ctx.scale(zoom, zoom);

      // Grid dots
      ctx.fillStyle = 'rgba(255,90,0,0.05)';
      var gs = 50;
      for (var gx = 0; gx <= GRAPH_W + gs; gx += gs) {
        for (var gy = 0; gy <= GRAPH_H + gs; gy += gs) {
          ctx.beginPath();
          ctx.arc(gx, gy, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Edges
      EDGES.forEach(function (e) {
        var fn = nodeMap[e.from];
        var tn = nodeMap[e.to];
        if (!fn || !tn) return;
        var fv = visible(fn);
        var tv = visible(tn);
        var both = fv && tv;
        var neither = !fv && !tv;
        var alpha = neither ? 0.08 : both ? 0.55 : 0.22;

        var ep = edgeEndpoints(fn, tn);
        var sx = ep.sx, sy = ep.sy, ex = ep.ex, ey = ep.ey;

        var angle = Math.atan2(ey - sy, ex - sx);
        var hl = 9;

        ctx.globalAlpha = alpha;
        ctx.strokeStyle = '#c74700';
        ctx.fillStyle = '#c74700';
        ctx.lineWidth = 1.4;

        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(ex, ey);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - hl * Math.cos(angle - Math.PI / 6), ey - hl * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(ex - hl * Math.cos(angle + Math.PI / 6), ey - hl * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();

        // Label
        var mx = (sx + ex) / 2;
        var my = (sy + ey) / 2;
        ctx.font = '9px "IBM Plex Mono",ui-monospace,monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        var tw = ctx.measureText(e.label).width;
        ctx.fillStyle = 'rgba(5,4,3,0.9)';
        ctx.fillRect(mx - tw / 2 - 3, my - 7, tw + 6, 14);
        ctx.fillStyle = neither ? '#612000' : '#a89c91';
        ctx.fillText(e.label, mx, my);
        ctx.globalAlpha = 1;
      });

      // Nodes
      NODES.forEach(function (n) {
        var vis = visible(n);
        var hov = hoverId === n.id;
        var nx = n.x - NODE_W / 2;
        var ny = n.y - NODE_H / 2;
        var color = TECH_COLORS[n.tech] || '#a89c91';
        var r = 3;

        ctx.globalAlpha = vis ? 1 : 0.18;

        // Fill
        ctx.fillStyle = hov ? 'rgba(255,90,0,0.16)' : 'rgba(11,11,10,0.95)';
        ctx.strokeStyle = hov ? '#ff5a00' : color;
        ctx.lineWidth = hov ? 2 : 1.5;
        roundRect(ctx, nx, ny, NODE_W, NODE_H, r);
        ctx.fill();
        ctx.stroke();

        // Left accent bar
        ctx.fillStyle = color;
        roundRect(ctx, nx, ny + 4, 3, NODE_H - 8, 1.5);
        ctx.fill();

        // Label
        ctx.fillStyle = hov ? '#ff5a00' : (vis ? '#ece3d8' : '#4a3c30');
        ctx.font = '600 11.5px "Inter","IBM Plex Sans",system-ui,sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.label, nx + 11, ny + NODE_H / 2, NODE_W - 50);

        // Tech badge
        var bx = nx + NODE_W - 37;
        var by = ny + NODE_H / 2 - 7;
        ctx.fillStyle = color + '20';
        ctx.strokeStyle = color + '50';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.rect(bx, by, 31, 14);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.font = '700 8.5px "IBM Plex Mono",ui-monospace,monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(n.tech.toUpperCase().slice(0, 5), bx + 15.5, by + 7);

        ctx.globalAlpha = 1;
      });

      ctx.restore();
      renderMinimap();
    }

    function renderMinimap() {
      var mc = minimap.getContext('2d');
      var mw = MINIMAP_W;
      var mh = MINIMAP_H;
      var pad = 14;

      mc.clearRect(0, 0, mw, mh);
      mc.fillStyle = 'rgba(11,11,10,0.93)';
      mc.strokeStyle = '#2d211a';
      mc.lineWidth = 1;
      mc.fillRect(0, 0, mw, mh);
      mc.strokeRect(0, 0, mw, mh);

      var sx = (mw - pad) / GRAPH_W;
      var sy = (mh - pad) / GRAPH_H;
      var sc = Math.min(sx, sy);
      var ox = pad / 2;
      var oy = pad / 2;

      // Edges
      mc.strokeStyle = 'rgba(199,71,0,0.35)';
      mc.lineWidth = 0.6;
      EDGES.forEach(function (e) {
        var fn = nodeMap[e.from];
        var tn = nodeMap[e.to];
        if (!fn || !tn) return;
        mc.beginPath();
        mc.moveTo(fn.x * sc + ox, fn.y * sc + oy);
        mc.lineTo(tn.x * sc + ox, tn.y * sc + oy);
        mc.stroke();
      });

      // Nodes
      NODES.forEach(function (n) {
        var color = TECH_COLORS[n.tech] || '#a89c91';
        mc.fillStyle = visible(n) ? color : 'rgba(45,33,26,0.55)';
        mc.beginPath();
        mc.arc(n.x * sc + ox, n.y * sc + oy, 3.2, 0, Math.PI * 2);
        mc.fill();
      });

      // Viewport rect
      var vx = (-panX / zoom) * sc + ox;
      var vy = (-panY / zoom) * sc + oy;
      var vw = (canvas.width / zoom) * sc;
      var vh = (canvas.height / zoom) * sc;
      mc.strokeStyle = 'rgba(255,90,0,0.65)';
      mc.lineWidth = 1;
      mc.strokeRect(vx, vy, vw, vh);
    }

    // --- Fit ---
    function fitToCanvas() {
      var pad = 32;
      zoom = Math.min((canvas.width - pad * 2) / GRAPH_W, (canvas.height - pad * 2) / GRAPH_H);
      panX = pad;
      panY = pad;
    }

    function resizeCanvas() {
      var w = canvasWrap.clientWidth || 800;
      var h = canvasWrap.clientHeight || 520;
      canvas.width = w;
      canvas.height = h;
    }

    // --- Zoom helpers ---
    function zoomAt(cx, cy, factor) {
      var oldZoom = zoom;
      zoom = Math.min(Math.max(zoom * factor, 0.2), 5);
      panX = cx - (cx - panX) * zoom / oldZoom;
      panY = cy - (cy - panY) * zoom / oldZoom;
    }

    // --- Event handlers ---
    btnIn.addEventListener('click', function () {
      zoomAt(canvas.width / 2, canvas.height / 2, 1.25);
      render();
    });
    btnOut.addEventListener('click', function () {
      zoomAt(canvas.width / 2, canvas.height / 2, 0.8);
      render();
    });
    btnReset.addEventListener('click', function () {
      fitToCanvas();
      render();
    });

    canvas.addEventListener('wheel', function (e) {
      e.preventDefault();
      var rect = canvas.getBoundingClientRect();
      zoomAt(e.clientX - rect.left, e.clientY - rect.top, e.deltaY > 0 ? 0.9 : 1.1);
      render();
    }, { passive: false });

    canvas.addEventListener('mousedown', function (e) {
      dragging = true;
      dragOrigin = { x: e.clientX - panX, y: e.clientY - panY };
      canvas.style.cursor = 'grabbing';
    });

    canvas.addEventListener('mousemove', function (e) {
      if (dragging) {
        panX = e.clientX - dragOrigin.x;
        panY = e.clientY - dragOrigin.y;
        render();
      } else {
        var rect = canvas.getBoundingClientRect();
        var n = nodeAt(e.clientX - rect.left, e.clientY - rect.top);
        var nid = n ? n.id : null;
        if (nid !== hoverId) {
          hoverId = nid;
          canvas.style.cursor = hoverId ? 'pointer' : 'grab';
          render();
        }
      }
    });

    canvas.addEventListener('mouseup', function () {
      dragging = false;
      canvas.style.cursor = hoverId ? 'pointer' : 'grab';
    });

    canvas.addEventListener('mouseleave', function () {
      dragging = false;
      canvas.style.cursor = 'default';
    });

    canvas.addEventListener('keydown', function (e) {
      if (e.key === '+' || e.key === '=') {
        zoomAt(canvas.width / 2, canvas.height / 2, 1.25); render();
      } else if (e.key === '-') {
        zoomAt(canvas.width / 2, canvas.height / 2, 0.8); render();
      } else if (e.key === '0') {
        fitToCanvas(); render();
      }
    });

    // Touch
    var lastPinchDist = null;
    canvas.addEventListener('touchstart', function (e) {
      if (e.touches.length === 1) {
        dragging = true;
        dragOrigin = { x: e.touches[0].clientX - panX, y: e.touches[0].clientY - panY };
      } else if (e.touches.length === 2) {
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        lastPinchDist = Math.hypot(dx, dy);
      }
    }, { passive: true });

    canvas.addEventListener('touchmove', function (e) {
      e.preventDefault();
      if (e.touches.length === 1 && dragging) {
        panX = e.touches[0].clientX - dragOrigin.x;
        panY = e.touches[0].clientY - dragOrigin.y;
        render();
      } else if (e.touches.length === 2) {
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        var dist = Math.hypot(dx, dy);
        if (lastPinchDist) {
          var rect = canvas.getBoundingClientRect();
          var cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left;
          var cy = (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top;
          zoomAt(cx, cy, dist / lastPinchDist);
          render();
        }
        lastPinchDist = dist;
      }
    }, { passive: false });

    canvas.addEventListener('touchend', function () {
      dragging = false;
      lastPinchDist = null;
    });

    var ro = new ResizeObserver(function () {
      resizeCanvas();
      fitToCanvas();
      render();
    });
    ro.observe(canvasWrap);

    // Initial draw
    resizeCanvas();
    fitToCanvas();
    render();

    return {
      refresh: render,
      setFilter: function (tech) { activeFilter = tech; render(); },
      destroy: function () { ro.disconnect(); containerEl.removeChild(wrapper); },
    };
  }

  // --- Utility ---
  function mkBtn(text, label) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = text;
    b.setAttribute('aria-label', label);
    return b;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  window.CodebaseIntelligenceGraph = { init: init };
})();
