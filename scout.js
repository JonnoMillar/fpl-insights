// Scout section - position comparison labs (defenders first).
//
// Position-agnostic on purpose: one data island per position, one renderer.
// Adding midfielders later is a POSITIONS entry in scout.py plus a second
// <script type="application/json" class="scout-data" data-pos="MID">, not
// a second copy of this file. See docs/superpowers/plans/
// 2026-09-08-scout-section-plan.md for the design this implements.
//
// Charts draw lazily, on the tab's first 'panel:shown' event rather than at
// load - the pool is season-long per-match data for every player at the
// position, and there is no reason to pay that layout cost before the
// Scout tab is ever opened (plan §2.10).
//
// percentileRank/zscore/applyFilters/applyDerivations/heroXKey below are
// deliberate 1:1 ports of the same-named Python functions in scout.py -
// that module is the reference; if the two ever disagree, scout.py is
// right and this file has drifted.
(function () {
  var NS = 'http://www.w3.org/2000/svg';

  // -- metric config, mirroring scout.py's METRICS / _METRIC_FIELD -------

  var METRICS = {
    defcon_hit_rate: { label: 'DefCon hit rate', invert: false, field: 'defconHitRate' },
    defcon90: { label: 'DefCon per 90', invert: false, field: 'defcon90' },
    xgi90: { label: 'xGI per 90', invert: false, field: 'xgi90' },
    xgc90: { label: 'xGC per 90', invert: true, field: 'xgc90' },
    start_rate: { label: 'Start rate', invert: false, field: 'startRate' },
    minutes_per_start: { label: 'Minutes per start', invert: false, field: 'minutesPerStart' },
    bps90: { label: 'BPS per 90', invert: false, field: 'bps90' },
    bonus90: { label: 'Bonus per 90', invert: false, field: 'bonus90' },
    cards90: { label: 'Cards per 90', invert: true, field: 'cards90' },
    xp: { label: 'xP', invert: false, field: 'xp' },
  };

  var RATE_MIN_MINUTES = 180;          // scout.RATE_MIN_MINUTES
  var HERO_GATE_MINUTES = RATE_MIN_MINUTES * 2;  // scout.HERO_GATE_MINUTES
  var ARCHETYPE_PERCENTILE_FLOOR = 200.0 / 3.0;  // scout.ARCHETYPE_PERCENTILE_FLOOR

  var OKABE_ITO = {
    blue: '#0072B2', orange: '#E69F00', sky: '#56B4E9', yellow: '#F0E442',
    green: '#009E73', vermillion: '#D55E00', purple: '#CC79A7',
  };
  // Widest subset of OKABE_ITO that is also pairwise distinguishable in
  // greyscale - see scout.py's CATEGORICAL_ORDER for why the full set
  // cannot be used straight for an n-way categorical toggle.
  var CATEGORICAL_ORDER = ['blue', 'green', 'sky', 'yellow'];

  var ARCHETYPE_LABELS = { volume: 'Volume', cleanSheet: 'Clean sheet', attacking: 'Attacking' };

  var MAX_SHORTLIST = 6;   // spec §5: "Max six players"
  var Z_CLAMP = 3;         // plan §2.7: bars clamp at +/-3, outliers labelled

  // Fixture difficulty reuses the page's own rose-teal ramp (ticker.py's
  // SCALE) rather than a second diverging scale (plan §2.5) - a fixture
  // must read the same number and colour wherever it appears. Difficulty
  // here is 1..5 with higher meaning harder, the reverse of ticker.py's
  // 0..10 "higher is better" rating, so the five steps are ticker.SCALE's
  // own five (bg, fg) pairs in reverse: 1 (easiest) is teal, 5 (hardest)
  // is rose. If ticker.SCALE ever changes, update this to match.
  var FIXTURE_TONES = [
    ['#17876a', '#ffffff'],
    ['#7ac9a0', '#0d3b26'],
    ['#eae7ec', '#37003c'],
    ['#f4845f', '#40190e'],
    ['#a4133c', '#ffffff'],
  ];

  // White->blue (good) / white->orange (bad), matching scout.py's
  // DIVERGING_SCALE - never used for fixture difficulty, which keeps the
  // ticker's own rose-teal ramp (plan §2.5).
  var DIVERGING_SCALE = [
    [20.0, '#08306b', '#ffffff'],
    [40.0, '#6baed6', '#0b3053'],
    [60.0, '#f4f2ee', '#37003c'],
    [80.0, '#fdae6b', '#5c2c00'],
    [100.1, '#e6550d', '#ffffff'],
  ];

  function divergingTone(pct) {
    for (var i = 0; i < DIVERGING_SCALE.length; i++) {
      if (pct < DIVERGING_SCALE[i][0]) { return DIVERGING_SCALE[i]; }
    }
    return DIVERGING_SCALE[DIVERGING_SCALE.length - 1];
  }

  function radiusForPercentile(pct, rMin, rMax) {
    rMin = rMin === undefined ? 5.0 : rMin;
    rMax = rMax === undefined ? 22.0 : rMax;
    pct = Math.max(0.0, Math.min(100.0, pct));
    return rMin + (rMax - rMin) * (pct / 100.0);
  }

  // -- pure data functions - ports of scout.py --------------------------

  function percentileRank(values, v) {
    var n = values.length;
    if (n <= 1) { return n ? 100.0 : 0.0; }
    var below = 0, equal = 0;
    for (var i = 0; i < n; i++) {
      if (values[i] < v) { below++; }
      else if (values[i] === v) { equal++; }
    }
    return 100.0 * (below + 0.5 * equal) / n;
  }

  function mean(values) {
    var s = 0; for (var i = 0; i < values.length; i++) { s += values[i]; }
    return s / values.length;
  }

  function pstdev(values) {
    var m = mean(values), s = 0;
    for (var i = 0; i < values.length; i++) { s += (values[i] - m) * (values[i] - m); }
    return Math.sqrt(s / values.length);
  }

  function zscore(values, v) {
    if (values.length < 2) { return 0.0; }
    var sd = pstdev(values);
    return sd ? (v - mean(values)) / sd : 0.0;
  }

  function median(values) {
    var sorted = values.slice().sort(function (a, b) { return a - b; });
    var n = sorted.length;
    if (!n) { return 0; }
    var mid = Math.floor(n / 2);
    return n % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  }

  function applyFilters(rows, filters) {
    return rows.filter(function (r) {
      if (filters.priceMin != null && r.price < filters.priceMin) { return false; }
      if (filters.priceMax != null && r.price > filters.priceMax) { return false; }
      if (filters.minStartRate != null && r.startRate < filters.minStartRate) { return false; }
      if (filters.minMinutesPerStart != null && r.minutesPerStart < filters.minMinutesPerStart) { return false; }
      if (filters.team != null && filters.team !== '' && r.teamId !== filters.team) { return false; }
      return true;
    });
  }

  function applyDerivations(rows, archetypes) {
    if (!rows.length) { return rows; }
    var xgcValues = rows.map(function (r) { return r.xgc90; });
    rows.forEach(function (r) {
      r.solidityPct = round1(100.0 - percentileRank(xgcValues, r.xgc90));
    });

    var metricKeys = Object.keys(METRICS);
    var poolValues = {};
    metricKeys.forEach(function (key) {
      poolValues[key] = rows.map(function (r) { return r[METRICS[key].field]; });
    });

    rows.forEach(function (r) {
      var pct = {}, z = {};
      metricKeys.forEach(function (key) {
        var invert = METRICS[key].invert;
        var val = r[METRICS[key].field];
        var vals = poolValues[key];
        var p = percentileRank(vals, val);
        pct[key] = round1(invert ? (100.0 - p) : p);
        var zz = zscore(vals, val);
        z[key] = round2(invert ? -zz : zz);
      });
      pct.solidity_pct = r.solidityPct;
      r.percentiles = pct;
      r.z = z;
    });

    rows.forEach(function (r) {
      var eligible = r.minutes >= RATE_MIN_MINUTES;
      r.archetypes = [];
      if (eligible) {
        Object.keys(archetypes).forEach(function (name) {
          var metric = archetypes[name];
          var val = r.percentiles[metric] || 0.0;
          if (val >= ARCHETYPE_PERCENTILE_FLOOR) { r.archetypes.push(name); }
        });
      }
    });
    return rows;
  }

  function heroXKey(rows) {
    if (!rows.length) { return 'defcon90'; }
    var med = median(rows.map(function (r) { return r.minutes; }));
    return med >= HERO_GATE_MINUTES ? 'defcon_hit_rate' : 'defcon90';
  }

  function round1(v) { return Math.round(v * 10) / 10; }
  function round2(v) { return Math.round(v * 100) / 100; }

  // -- shell wiring --------------------------------------------------------

  var panel = document.getElementById('p-scout');
  if (!panel) { return; }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function node(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) { n.setAttribute(k, attrs[k]); }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function niceStep(rawStep) {
    var exponent = Math.floor(Math.log(rawStep) / Math.LN10);
    var base = Math.pow(10, exponent);
    var frac = rawStep / base;
    var niceFrac = frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 2.5 ? 2.5 : frac <= 5 ? 5 : 10;
    return niceFrac * base;
  }

  function niceTicks(min, max, maxTicks) {
    if (min === max) { min -= 1; max += 1; }
    var step = niceStep((max - min) / Math.max(1, maxTicks));
    var niceMin = Math.floor(min / step) * step;
    var niceMax = Math.ceil(max / step) * step;
    var ticks = [];
    for (var v = niceMin; v <= niceMax + step / 1e6; v += step) {
      ticks.push(Math.round(v / step) * step);
    }
    return { ticks: ticks, min: niceMin, max: niceMax };
  }

  var drawn = false;

  // -- Level 3: player card -------------------------------------------
  //
  // Its own dialog rather than an extension of the existing player
  // dialog (playerview.js's dialog.pv): that dialog's payload assumes a
  // full match history from fplapi.element_summary, fetched per player -
  // fine for the owned fifteen, but this pool is 130+ defenders and
  // fetching each one's history individually is exactly the N+1 request
  // problem scout.py's season_live was built to avoid (plan §1). This
  // card is built entirely from what is already sitting on the row.

  var cardRowsById = {};   // updated by every lab's draw() - see initLab

  var AVAILABILITY_LABEL = {
    injured: 'Injured', suspended: 'Suspended', doubtful: 'Doubtful', available: 'Available',
  };

  function bulletBar(pct, label, value, note) {
    return '<div class="scpv-tile"><div class="scpv-tile-label">' + esc(label) + '</div>' +
      '<div class="scpv-tile-num tnum">' + esc(value) + '</div>' +
      '<div class="scpv-bullet"><span class="scpv-bullet-fill" style="width:' +
      Math.max(0, Math.min(100, pct)).toFixed(0) + '%"></span>' +
      '<span class="scpv-bullet-tick"></span></div>' +
      (note ? '<div class="scpv-tile-note">' + esc(note) + '</div>' : '') +
      '</div>';
  }

  function sparkline(values, w, h) {
    if (!values.length) { return ''; }
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    if (min === max) { min -= 1; max += 1; }
    var pts = values.map(function (v, i) {
      var x = (i / Math.max(1, values.length - 1)) * w;
      var y = h - ((v - min) / (max - min)) * h;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" class="scpv-spark" preserveAspectRatio="none">' +
      '<polyline points="' + pts + '" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
  }

  // Shape and vertical position carry the status marker; colour is
  // supplementary only (spec §6.3). FPL's public API has no "benched"
  // concept outside one manager's own picks, so a player who did not
  // feature reads as one 'unplayed' state rather than the spec's
  // separate benched/unavailable (see scout.py season_live docstring).
  function statusMarker(status) {
    if (status === 'started') { return '<circle class="mk-started" r="3"/>'; }
    if (status === 'subbedOn') { return '<path class="mk-sub" d="M-3,3 L0,-3 L3,3 Z"/>'; }
    return '<circle class="mk-unplayed" r="3" fill="none" stroke-width="1.2"/>';
  }

  function renderMatchStrip(matches, hasThreshold) {
    var n = matches.length;
    if (!n) { return '<p class="scpv-note">No matches played yet this season.</p>'; }
    var colW = 22, barTop = 6, barH = 60, markY = barH + 18, w = n * colW, h = markY + 10;
    var maxPts = Math.max(3, Math.max.apply(null, matches.map(function (m) { return m.points; })));
    var cols = matches.map(function (m, i) {
      var cx = i * colW + colW / 2;
      var bh = Math.max(1, (Math.max(0, m.points) / maxPts) * barH);
      var by = barTop + (barH - bh);
      var title = 'GW' + m.gw + (m.opp ? (m.home ? ' v ' : ' @ ') + m.opp : '') +
        ' - ' + m.minutes + ' min, ' + m.points + ' pts' +
        (hasThreshold ? ', ' + m.defcon + ' contributions' : '');
      var markers = '<g transform="translate(' + cx + ',' + markY + ')">' + statusMarker(m.status) + '</g>';
      if (hasThreshold && m.status !== 'unplayed') {
        markers += '<text class="mk-defcon' + (m.defconHit ? ' hit' : ' miss') + '" x="' + cx +
          '" y="' + (markY + 13) + '" text-anchor="middle">' + (m.defconHit ? '+' : '–') + '</text>';
      }
      if (m.cleanSheet) {
        markers += '<rect class="mk-cs" x="' + (cx - colW / 2 + 2) + '" y="' + (by - 2) +
          '" width="' + (colW - 4) + '" height="' + (bh + 4) + '" rx="2"/>';
      }
      if (m.card !== 'none') {
        markers += '<path class="mk-card mk-card-' + m.card + '" d="M' + (cx - 3) + ',' + (by - 5) +
          ' L' + (cx + 3) + ',' + (by - 5) + ' L' + cx + ',' + (by - 10) + ' Z"/>';
      }
      return '<g class="scpv-col"><title>' + esc(title) + '</title>' +
        '<rect class="scpv-bar" x="' + (cx - colW / 2 + 3) + '" y="' + by +
        '" width="' + (colW - 6) + '" height="' + bh + '"/>' + markers + '</g>';
    }).join('');
    return '<svg class="scpv-strip" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMinYMid meet">' +
      cols + '</svg>';
  }

  function renderCard(row) {
    var dlg = document.querySelector('dialog.scoutpv');
    if (!dlg || !row) { return; }
    var body = dlg.querySelector('.scpv-body');
    var pct = row.percentiles || {};
    var hasThreshold = true;   // every position in scout has a DefCon threshold today

    var flags = [];
    if (row.onCorners) { flags.push('Corners'); }
    if (row.onFreeKicks) { flags.push('Free kicks'); }
    if (row.onPens) { flags.push('Pens'); }
    if (row.availability !== 'available') {
      flags.push((AVAILABILITY_LABEL[row.availability] || row.availability) +
        (row.news ? ': ' + row.news : ''));
    }
    flags.push((row.priceChangeMomentum >= 0 ? '+' : '') + row.priceChangeMomentum + ' transfers this GW');
    flags.push(row.ownership.toFixed(1) + '% owned');

    var archBadges = (row.archetypes || []).map(function (a) {
      return '<span class="archbadge archbadge-' + esc(a) + '">' + esc(ARCHETYPE_LABELS[a] || a) + '</span>';
    }).join('');

    var tiles = [
      bulletBar(pct.defcon_hit_rate || 0, 'DefCon hit rate',
        Math.round(row.defconHitRate * 100) + '%', row.defconHitN + ' starts'),
      bulletBar(pct.xgi90 || 0, 'xGI per 90', row.xgi90.toFixed(2)),
      bulletBar(pct.xgc90 || 0, 'xGC per 90', row.xgc90.toFixed(2)),
      bulletBar(pct.start_rate || 0, 'Start rate', Math.round(row.startRate * 100) + '%'),
      bulletBar(pct.bonus90 || 0, 'Bonus per 90', row.bonus90.toFixed(2)),
    ].join('');

    var last10 = row.matches.slice(-10);
    var sparks = [
      ['DefCon count', last10.map(function (m) { return m.defcon; })],
      ['xGI', last10.map(function (m) { return m.xgi; })],
      ['xGC', last10.map(function (m) { return m.xgc; })],
    ].map(function (s) {
      return '<div class="scpv-sparkwrap"><div class="scpv-spark-label">' + esc(s[0]) + '</div>' +
        sparkline(s[1], 100, 24) + '</div>';
    }).join('');

    body.innerHTML =
      '<div class="scpv-head"><h2>' + esc(row.webName) +
      ' <span class="scpv-team">' + esc(row.teamShort) + '</span></h2>' +
      '<p class="scpv-sub">£' + row.price.toFixed(1) + 'm' + (archBadges ? ' &middot; ' + archBadges : '') + '</p></div>' +
      '<p class="scpv-flags">' + flags.map(function (f) { return '<span class="scpv-flag">' + esc(f) + '</span>'; }).join('') + '</p>' +
      '<div class="scpv-block"><h3>This season, per 90</h3><div class="scpv-grid">' + tiles + '</div></div>' +
      '<div class="scpv-block"><h3>Match by match' +
      (hasThreshold ? ' <span class="scpv-key"><span class="mk-defcon hit">+</span> hit &middot; ' +
        '<span class="mk-defcon miss">–</span> miss &middot; outline = clean sheet</span>' : '') +
      '</h3>' + renderMatchStrip(row.matches, hasThreshold) + '</div>' +
      '<div class="scpv-block"><h3>Last 10 gameweeks</h3><div class="scpv-sparks">' + sparks + '</div></div>';

    if (typeof dlg.showModal === 'function') { dlg.showModal(); }
    else { dlg.setAttribute('open', ''); }
    body.scrollTop = 0;
  }

  document.addEventListener('click', function (ev) {
    var trigger = ev.target.closest && ev.target.closest('[data-scout-open]');
    if (trigger) {
      ev.preventDefault();
      renderCard(cardRowsById[parseInt(trigger.dataset.scoutOpen, 10)]);
      return;
    }
    var dlg = document.querySelector('dialog.scoutpv');
    if (dlg && ev.target === dlg) { dlg.close(); }
    if (ev.target.closest && ev.target.closest('.scpv-close')) { dlg.close(); }
  });

  function initLab(lab) {
    var pos = lab.dataset.pos;
    var holder = lab.querySelector('.scout-data[data-pos="' + pos + '"]');
    if (!holder) { return; }
    var data;
    try { data = JSON.parse(holder.textContent); }
    catch (e) { return; }

    var filters = Object.assign({}, data.defaultFilters);
    var brush = null;   // Set of player ids, or null when no brush is active
    var selected = new Set();  // Level 2 shortlist, insertion order = display order

    var compareBar = lab.querySelector('.scoutcomparebar');
    var compareCard = lab.querySelector('.scoutcompare');
    var zbarsEl = lab.querySelector('.scoutzbars');
    var tickerEl = lab.querySelector('.scoutticker');
    var clearShortlistBtn = lab.querySelector('.scb-clear');

    var svg = lab.querySelector('svg.scoutscatter');
    var readout = lab.querySelector('.scoutreadout');
    var defaultReadout = readout ? readout.innerHTML : '';
    var tbody = lab.querySelector('.scoutheat tbody');
    var countEl = lab.querySelector('.sf-count');
    var sortState = { key: null, dir: 1 };
    var pinnedG = null, selGroup = null;

    var W = 1040, H = 520, ML = 62, MR = 18, MT = 18, MB = 48;

    function fmtMetric(key, val) {
      if (key === 'defcon_hit_rate' || key === 'start_rate') { return Math.round(val * 100) + '%'; }
      if (key === 'minutes_per_start') { return Math.round(val); }
      if (key === 'xp') { return val.toFixed(1); }
      return val.toFixed(2);
    }

    function fmtHeroX(key, val) {
      return key === 'defcon_hit_rate' ? Math.round(val * 100) + '%' : val.toFixed(1);
    }

    function shapeNode(bucket, cx, cy, r) {
      // Shape backs the categorical colour toggle (spec §1: never colour
      // alone) - circle/square/triangle/diamond for the four
      // CATEGORICAL_ORDER buckets.
      if (bucket === 1) {
        return node('rect', { x: cx - r * 0.85, y: cy - r * 0.85, width: r * 1.7, height: r * 1.7 });
      }
      if (bucket === 2) {
        var h = r * 1.15;
        return node('polygon', {
          points: [cx, cy - h, cx - h, cy + h * 0.85, cx + h, cy + h * 0.85].join(' '),
        });
      }
      if (bucket === 3) {
        return node('polygon', {
          points: [cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy].join(' '),
        });
      }
      return node('circle', { cx: cx, cy: cy, r: r });
    }

    function priceBucket(rows, price) {
      var sorted = rows.map(function (r) { return r.price; }).sort(function (a, b) { return a - b; });
      var n = sorted.length;
      var q = [sorted[Math.floor(n * 0.25)], sorted[Math.floor(n * 0.5)], sorted[Math.floor(n * 0.75)]];
      if (price <= q[0]) { return 0; }
      if (price <= q[1]) { return 1; }
      if (price <= q[2]) { return 2; }
      return 3;
    }

    var categorical = false;
    var toggleBtn = lab.querySelector('.sf-categorical');

    function drawScatter(rows, heroX) {
      while (svg.firstChild) { svg.removeChild(svg.firstChild); }
      pinnedG = null;
      if (readout) { readout.innerHTML = defaultReadout; }
      if (!rows.length) { return; }

      var xField = METRICS[heroX].field;
      var yKey = data.heroY;
      var yField = METRICS[yKey] ? METRICS[yKey].field : yKey;

      var xs = rows.map(function (r) { return r[xField]; });
      var ys = rows.map(function (r) { return r[yField]; });
      var rawX0 = heroX === 'defcon_hit_rate' ? 0 : Math.min(0, Math.min.apply(null, xs));
      var rawX1 = heroX === 'defcon_hit_rate' ? 1 : Math.max.apply(null, xs);
      var rawY0 = Math.min(0, Math.min.apply(null, ys));
      var rawY1 = Math.max.apply(null, ys);
      var xTicks = heroX === 'defcon_hit_rate'
        ? { ticks: [0, 0.25, 0.5, 0.75, 1], min: 0, max: 1 }
        : niceTicks(rawX0, rawX1, 5);
      var yTicks = niceTicks(rawY0, rawY1, 4);
      var x0 = xTicks.min, x1 = xTicks.max, y0 = yTicks.min, y1 = yTicks.max;
      if (x1 === x0) { x1 = x0 + 1; }
      if (y1 === y0) { y1 = y0 + 1; }

      function sx(v) { return ML + (v - x0) / (x1 - x0) * (W - ML - MR); }
      function sy(v) { return H - MB - (v - y0) / (y1 - y0) * (H - MT - MB); }

      var grid = node('g', { 'class': 'grid' });
      var labels = node('g', { 'class': 'axlab' });
      yTicks.ticks.forEach(function (yv) {
        var gy = sy(yv);
        grid.appendChild(node('line', { x1: ML, y1: gy, x2: W - MR, y2: gy }));
        labels.appendChild(node('text', { x: ML - 8, y: gy + 4, 'text-anchor': 'end' }, yv.toFixed(1)));
      });
      xTicks.ticks.forEach(function (xv) {
        var gx = sx(xv);
        grid.appendChild(node('line', { x1: gx, y1: MT, x2: gx, y2: H - MB }));
        labels.appendChild(node('text', {
          x: gx, y: H - MB + 18, 'text-anchor': 'middle',
        }, heroX === 'defcon_hit_rate' ? Math.round(xv * 100) + '%' : xv.toFixed(1)));
      });
      svg.appendChild(grid);
      svg.appendChild(labels);
      svg.appendChild(node('text', {
        'class': 'axtitle', x: (ML + W - MR) / 2, y: H - 8, 'text-anchor': 'middle',
      }, METRICS[heroX].label));
      svg.appendChild(node('text', {
        'class': 'axtitle', 'text-anchor': 'middle',
        transform: 'translate(16,' + ((MT + H - MB) / 2) + ') rotate(-90)',
      }, METRICS[yKey] ? METRICS[yKey].label : yKey));

      // Spec §3.1: wherever defconPer90 is plotted, a hard reference line
      // at the threshold - the FPL contribution point is binary, and this
      // is the only honest way to show "clears it" on a continuous axis.
      if (heroX === 'defcon90' && data.defconThreshold && x0 <= data.defconThreshold && data.defconThreshold <= x1) {
        var tx = sx(data.defconThreshold);
        svg.appendChild(node('line', {
          'class': 'threshline', x1: tx, y1: MT, x2: tx, y2: H - MB,
        }));
        svg.appendChild(node('text', {
          'class': 'threshlabel', x: tx + 4, y: MT + 12,
        }, 'threshold'));
      }

      // Faint median crosshairs (spec §4.2) - text describes the two axes
      // only, never an archetype name: solidity is a third channel (bubble
      // size) with no region of this plane that means "clean sheet
      // archetype" (plan §2.2).
      var medX = median(xs), medY = median(ys);
      var mx = sx(medX), my = sy(medY);
      svg.appendChild(node('line', { 'class': 'crosshair', x1: mx, y1: MT, x2: mx, y2: H - MB }));
      svg.appendChild(node('line', { 'class': 'crosshair', x1: ML, y1: my, x2: W - MR, y2: my }));
      var xLabel = METRICS[heroX].label.toLowerCase();
      var yLabel = (METRICS[yKey] ? METRICS[yKey].label : yKey).toLowerCase();
      [
        [W - MR - 6, MT + 12, 'end', 'high ' + xLabel + ', high ' + yLabel],
        [ML + 6, MT + 12, 'start', 'low ' + xLabel + ', high ' + yLabel],
        [W - MR - 6, H - MB - 6, 'end', 'high ' + xLabel + ', low ' + yLabel],
        [ML + 6, H - MB - 6, 'start', 'low ' + xLabel + ', low ' + yLabel],
      ].forEach(function (q) {
        svg.appendChild(node('text', {
          'class': 'quadlabel', x: q[0], y: q[1], 'text-anchor': q[2],
        }, q[3]));
      });

      var pts = [];
      rows.forEach(function (r) {
        var cx = sx(r[xField]), cy = sy(r[yField]);
        var radius = radiusForPercentile(r.solidityPct);
        var thin = r.minutes < RATE_MIN_MINUTES;
        var detail = r.webName + ' (' + r.teamShort + ') - ' + r.price.toFixed(1) +
          'm, ' + fmtHeroX(heroX, r[xField]) + ' ' + METRICS[heroX].label.toLowerCase() +
          ', ' + r[yField].toFixed(2) + ' ' + yLabel + ', solidity ' + r.solidityPct.toFixed(0) +
          'th pct, ' + r.minutes + ' min' +
          (r.archetypes.length
            ? ' - ' + r.archetypes.map(function (a) { return ARCHETYPE_LABELS[a] || a; }).join(', ')
            : '');
        var g = node('g', {
          'class': 'scoutpt ' + (thin ? 'thin' : 'solid'),
          'data-pid': r.id, tabindex: '0', role: 'button', 'aria-label': detail,
        });
        var mark;
        if (categorical) {
          var bucket = priceBucket(rows, r.price);
          mark = shapeNode(bucket, cx, cy, radius);
          mark.setAttribute('fill', thin ? 'none' : OKABE_ITO[CATEGORICAL_ORDER[bucket]]);
          mark.setAttribute('stroke', OKABE_ITO[CATEGORICAL_ORDER[bucket]]);
        } else {
          mark = node('circle', { cx: cx, cy: cy, r: radius });
        }
        g.appendChild(mark);
        g.appendChild(node('circle', { 'class': 'hit', cx: cx, cy: cy, r: Math.max(radius, 11) }));
        g.appendChild(node('title', {}, detail));
        g._r = r; g._cx = cx; g._cy = cy; g._detail = detail;
        g.addEventListener('click', function () { pinnedG = this; pick(this); });
        g.addEventListener('focus', function () { pinnedG = this; pick(this); });
        g.addEventListener('mouseenter', function () { pick(this); });
        g.addEventListener('mouseleave', unpick);
        svg.appendChild(g);
        pts.push({ r: r, cx: cx, cy: cy, g: g });
      });

      // Top-quadrant players (better than the pool median on both axes)
      // get a permanent label with collision avoidance; everyone else is
      // read on hover (spec §4.2).
      var topQuadrant = pts.filter(function (p) { return p.r[xField] >= medX && p.r[yField] >= medY; });
      var placed = [];
      topQuadrant.forEach(function (m) {
        var halfw = m.r.webName.length * 3.2 + 4;
        var ly = null, lx = null;
        [-11, -23, 16, -35, 28, -47].some(function (dy) {
          var y = m.cy + dy;
          if (y < MT + 10 || y > H - MB - 4) { return false; }
          var x = Math.min(Math.max(m.cx, ML + halfw), W - MR - halfw);
          var clash = placed.some(function (q) {
            return Math.abs(x - q.x) < (halfw + q.w) && Math.abs(y - q.y) < 12;
          });
          if (clash) { return false; }
          placed.push({ x: x, y: y, w: halfw });
          ly = y; lx = x;
          return true;
        });
        if (ly === null) { return; }
        svg.appendChild(node('text', {
          'class': 'ptlabel', x: lx, y: ly, 'text-anchor': 'middle',
        }, m.r.webName));
      });

      selGroup = node('g', { 'class': 'sel' });
      selGroup.setAttribute('hidden', '');
      selGroup.appendChild(node('circle', { 'class': 'selring', r: 10 }));
      svg.appendChild(selGroup);

      // Brush rectangle (drag to select). A click with no drag clears it.
      var brushRect = null, dragStart = null;
      var overlay = node('rect', {
        'class': 'brushcatch', x: ML, y: MT, width: W - ML - MR, height: H - MT - MB,
      });
      overlay.addEventListener('mousedown', function (ev) {
        var box = svg.getBoundingClientRect();
        var scale = W / box.width;
        dragStart = { x: (ev.clientX - box.left) * scale, y: (ev.clientY - box.top) * scale };
        brushRect = node('rect', { 'class': 'brushrect', x: dragStart.x, y: dragStart.y, width: 0, height: 0 });
        svg.appendChild(brushRect);
      });
      svg.addEventListener('mousemove', function (ev) {
        if (!dragStart) { return; }
        var box = svg.getBoundingClientRect();
        var scale = W / box.width;
        var cx2 = (ev.clientX - box.left) * scale, cy2 = (ev.clientY - box.top) * scale;
        var x = Math.min(dragStart.x, cx2), y = Math.min(dragStart.y, cy2);
        brushRect.setAttribute('x', x); brushRect.setAttribute('y', y);
        brushRect.setAttribute('width', Math.abs(cx2 - dragStart.x));
        brushRect.setAttribute('height', Math.abs(cy2 - dragStart.y));
      });
      window.addEventListener('mouseup', function (ev) {
        if (!dragStart) { return; }
        var x = parseFloat(brushRect.getAttribute('x')), y = parseFloat(brushRect.getAttribute('y'));
        var w = parseFloat(brushRect.getAttribute('width')), h = parseFloat(brushRect.getAttribute('height'));
        dragStart = null;
        if (w < 4 && h < 4) {
          // A click, not a drag - clears any existing brush.
          if (brushRect && brushRect.parentNode) { brushRect.parentNode.removeChild(brushRect); }
          if (brush) { brush = null; renderHeatmap(currentRows); updateBrushDimming(); }
          return;
        }
        var picked = pts.filter(function (p) {
          return p.cx >= x && p.cx <= x + w && p.cy >= y && p.cy <= y + h;
        });
        brush = new Set(picked.map(function (p) { return p.r.id; }));
        renderHeatmap(currentRows);
        updateBrushDimming();
      });
      svg.appendChild(overlay);
      updateBrushDimming();

      function updateBrushDimming() {
        pts.forEach(function (p) {
          p.g.classList.toggle('dimmed', !!(brush && !brush.has(p.r.id)));
        });
      }
    }

    function pick(g) {
      if (!selGroup) { return; }
      var ring = selGroup.querySelector('.selring');
      ring.setAttribute('cx', g._cx); ring.setAttribute('cy', g._cy);
      selGroup.removeAttribute('hidden');
      if (readout) {
        readout.innerHTML = '<b>' + esc(g._r.webName) + '</b>' + esc(g._detail.slice(g._r.webName.length));
      }
      var row = tbody && tbody.querySelector('tr[data-pid="' + g._r.id + '"]');
      if (row) {
        tbody.querySelectorAll('tr.scout-highlight').forEach(function (o) { o.classList.remove('scout-highlight'); });
        row.classList.add('scout-highlight');
      }
    }

    function unpick() {
      if (pinnedG) { pick(pinnedG); return; }
      if (selGroup) { selGroup.setAttribute('hidden', ''); }
      if (readout) { readout.innerHTML = defaultReadout; }
    }

    function archetypeBadges(archs) {
      return archs.map(function (a) {
        return '<span class="archbadge archbadge-' + esc(a) + '">' +
          esc(ARCHETYPE_LABELS[a] || a) + '</span>';
      }).join('');
    }

    function renderHeatmap(rows) {
      if (!tbody) { return; }
      var visible = brush ? rows.filter(function (r) { return brush.has(r.id); }) : rows;
      if (sortState.key) {
        var key = sortState.key, dir = sortState.dir;
        visible = visible.slice().sort(function (a, b) {
          var av = key === 'webName' ? a.webName : key === 'price' ? a.price : a[METRICS[key].field];
          var bv = key === 'webName' ? b.webName : key === 'price' ? b.price : b[METRICS[key].field];
          if (av < bv) { return -1 * dir; }
          if (av > bv) { return 1 * dir; }
          return 0;
        });
      }
      tbody.textContent = '';
      visible.forEach(function (r) {
        var tr = document.createElement('tr');
        tr.dataset.pid = r.id;
        var flag = r.availability !== 'available'
          ? ' <span class="flag" title="' + esc(r.news || r.availability) + '">' +
            esc(r.availability.slice(0, 3).toUpperCase()) + '</span>'
          : '';
        var checked = selected.has(r.id);
        var disabled = !checked && selected.size >= MAX_SHORTLIST;
        var cells = '<td><input type="checkbox" class="scoutpick" data-pid="' + r.id + '"' +
          (checked ? ' checked' : '') + (disabled ? ' disabled' : '') +
          ' aria-label="Add ' + esc(r.webName) + ' to shortlist"></td>' +
          '<td><button type="button" class="rowlink" data-scout-open="' + r.id + '">' +
          esc(r.webName) + '</button> <span class="teamtag">' +
          esc(r.teamShort) + '</span>' + flag + '</td>' +
          '<td class="num tnum">£' + r.price.toFixed(1) + 'm</td>';
        data.metrics.forEach(function (key) {
          var pct = r.percentiles[key];
          var tone = divergingTone(pct);
          cells += '<td class="num tnum" style="background:' + tone[1] + ';color:' + tone[2] + '">' +
            fmtMetric(key, r[METRICS[key].field]) + '</td>';
        });
        cells += '<td>' + archetypeBadges(r.archetypes) + '</td>';
        tr.innerHTML = cells;
        tr.addEventListener('mouseenter', function () {
          var g = svg.querySelector('.scoutpt[data-pid="' + r.id + '"]');
          if (g) { pick(g); }
        });
        var pick2 = tr.querySelector('.scoutpick');
        if (pick2) {
          pick2.addEventListener('change', function () {
            if (this.checked) { selected.add(r.id); } else { selected.delete(r.id); }
            updateCompareUI();
            renderHeatmap(currentRows);
          });
        }
        tbody.appendChild(tr);
      });
      if (countEl) {
        countEl.textContent = visible.length + ' of ' + rows.length + ' shown' +
          (brush ? ' (brushed - click empty space to clear)' : '');
      }
    }

    function clampZ(z) { return Math.max(-Z_CLAMP, Math.min(Z_CLAMP, z)); }

    function fmtRaw(key, val) {
      if (key === 'defcon_hit_rate' || key === 'start_rate') { return Math.round(val * 100) + '%'; }
      if (key === 'minutes_per_start') { return Math.round(val) + ' min'; }
      return val.toFixed(2);
    }

    function renderZBars(rows) {
      if (!zbarsEl) { return; }
      zbarsEl.textContent = '';
      data.zbars.forEach(function (key) {
        var m = METRICS[key];
        var band = document.createElement('div');
        band.className = 'zband';
        var title = m.label + (m.invert ? ' (inverted - right is better)' : '');
        var rowsHtml = rows.map(function (r) {
          var z = clampZ(r.z[key] || 0);
          var pct = (z / Z_CLAMP) * 50;   // percent of the half-track width
          var barStyle = z >= 0
            ? 'left:50%;width:' + pct.toFixed(1) + '%'
            : 'left:' + (50 + pct).toFixed(1) + '%;width:' + (-pct).toFixed(1) + '%';
          var raw = r[m.field];
          var outlier = Math.abs(r.z[key] || 0) > Z_CLAMP;
          return '<div class="zrow">' +
            '<span class="zrow-name">' + esc(r.webName) + '</span>' +
            '<span class="zrow-track"><span class="zrow-center"></span>' +
            '<span class="zrow-bar' + (z >= 0 ? ' zrow-bar-pos' : ' zrow-bar-neg') + '" style="' + barStyle + '"></span>' +
            '</span>' +
            '<span class="zrow-val tnum">' + fmtRaw(key, raw) + (outlier ? '*' : '') + '</span>' +
            '</div>';
        }).join('');
        band.innerHTML = '<div class="zband-title">' + esc(title) + '</div>' +
          '<div class="zband-rows">' + rowsHtml + '</div>';
        zbarsEl.appendChild(band);
      });
    }

    function renderTicker(rows) {
      if (!tickerEl) { return; }
      var horizon = filters.fixtureHorizon || 6;
      var gwHeaders = rows.length
        ? rows[0].fixtures.slice(0, horizon).map(function (fx) {
            return '<th>GW' + fx.gw + (fx.blank ? '' : '<br>' + (fx.home ? 'v' : '@') + esc(fx.opp)) + '</th>';
          }).join('')
        : '';
      var body = rows.map(function (r) {
        var fx = r.fixtures.slice(0, horizon);
        function cells(field) {
          return fx.map(function (f) {
            if (f.blank) { return '<td class="tick-blank">-</td>'; }
            var tone = FIXTURE_TONES[f[field] - 1] || FIXTURE_TONES[2];
            return '<td style="background:' + tone[0] + ';color:' + tone[1] + '">' + f[field] + '</td>';
          }).join('');
        }
        return '<tr class="tick-name"><td colspan="' + (horizon + 1) + '"><b>' + esc(r.webName) + '</b></td></tr>' +
          '<tr><td class="tick-label">Clean sheet</td>' + cells('cleanSheetDifficulty') + '</tr>' +
          '<tr><td class="tick-label">DefCon</td>' + cells('defconDifficulty') + '</tr>';
      }).join('');
      tickerEl.innerHTML = '<div class="scroll"><table class="scouttickertable">' +
        '<thead><tr><th></th>' + gwHeaders + '</tr></thead>' +
        '<tbody>' + body + '</tbody></table></div>';
    }

    function renderCompare() {
      var rows = Array.from(selected).map(function (id) {
        return currentRows.find(function (r) { return r.id === id; });
      }).filter(Boolean);
      renderZBars(rows);
      renderTicker(rows);
    }

    function updateCompareUI() {
      // A player dropped by a filter change no longer has a valid z-score
      // against the current pool (spec §2.1 - percentiles are always
      // relative to whichever pool is filtered in), so the shortlist is
      // pruned to whoever actually survives the current filter.
      var survivors = new Set(currentRows.map(function (r) { return r.id; }));
      Array.from(selected).forEach(function (id) { if (!survivors.has(id)) { selected.delete(id); } });
      var n = selected.size;
      if (compareBar) {
        compareBar.hidden = n === 0;
        var countSpan = compareBar.querySelector('.scb-count');
        if (countSpan) { countSpan.textContent = n + ' of ' + MAX_SHORTLIST + ' selected'; }
      }
      if (compareCard) { compareCard.hidden = n < 2; }
      if (n >= 2) { renderCompare(); }
    }

    if (clearShortlistBtn) {
      clearShortlistBtn.addEventListener('click', function () {
        selected.clear();
        updateCompareUI();
        renderHeatmap(currentRows);
      });
    }

    var currentRows = [];

    function draw() {
      // A brush is a selection of specific player ids drawn against the
      // last scatter render - a filter change redraws that scatter from
      // scratch, so an old brush would otherwise silently read as "0 of 0
      // shown" the moment none of its ids survive the new filter.
      brush = null;
      currentRows = applyFilters(data.rows, filters);
      applyDerivations(currentRows, data.archetypes);
      currentRows.forEach(function (r) { cardRowsById[r.id] = r; });
      var heroX = heroXKey(currentRows);
      drawScatter(currentRows, heroX);
      renderHeatmap(currentRows);
      updateCompareUI();
    }

    // -- filter bar wiring --------------------------------------------

    var priceMin = lab.querySelector('.sf-price-min');
    var priceMax = lab.querySelector('.sf-price-max');
    var startRate = lab.querySelector('.sf-start-rate');
    var startRateVal = lab.querySelector('.sf-start-rate-val');
    var minsPerStart = lab.querySelector('.sf-mins-per-start');
    var teamSel = lab.querySelector('.sf-team');
    var horizonSel = lab.querySelector('.sf-horizon');

    if (priceMin) { priceMin.addEventListener('change', function () { filters.priceMin = this.value ? parseFloat(this.value) : null; draw(); }); }
    if (priceMax) { priceMax.addEventListener('change', function () { filters.priceMax = this.value ? parseFloat(this.value) : null; draw(); }); }
    if (startRate) {
      startRate.value = filters.minStartRate;
      if (startRateVal) { startRateVal.textContent = Math.round(filters.minStartRate * 100) + '%'; }
      startRate.addEventListener('input', function () {
        filters.minStartRate = parseFloat(this.value);
        if (startRateVal) { startRateVal.textContent = Math.round(filters.minStartRate * 100) + '%'; }
        draw();
      });
    }
    if (minsPerStart) { minsPerStart.addEventListener('change', function () { filters.minMinutesPerStart = this.value ? parseFloat(this.value) : null; draw(); }); }
    if (teamSel) { teamSel.addEventListener('change', function () { filters.team = this.value ? parseInt(this.value, 10) : null; draw(); }); }
    if (horizonSel) {
      horizonSel.addEventListener('change', function () {
        filters.fixtureHorizon = parseInt(this.value, 10);
        if (!compareCard || !compareCard.hidden) { renderCompare(); }
      });
    }
    if (toggleBtn) {
      toggleBtn.addEventListener('click', function () {
        categorical = !categorical;
        this.setAttribute('aria-pressed', String(categorical));
        drawScatter(currentRows, heroXKey(currentRows));
      });
    }
    lab.querySelectorAll('.scoutheat th[data-sort]').forEach(function (th) {
      function doSort() {
        var key = th.dataset.sort;
        sortState.dir = (sortState.key === key) ? -sortState.dir : -1;
        sortState.key = key;
        renderHeatmap(currentRows);
      }
      th.addEventListener('click', doSort);
      th.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); doSort(); }
      });
    });

    draw();
  }

  function draw() {
    if (drawn) { return; }
    drawn = true;
    panel.querySelectorAll('.scoutlab').forEach(initLab);
  }

  panel.addEventListener('panel:shown', draw);
  if (!panel.hidden) { draw(); }
})();
