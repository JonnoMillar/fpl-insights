// Scout section - position comparison labs for defenders, midfielders and
// forwards, one on screen at a time behind a position switch.
//
// Position-agnostic on purpose: one data island per position, one renderer.
// Everything that differs between labs - scatter axes, bubble channel,
// archetypes, card tiles, match-strip markers, fixture lists - arrives in
// the island from scout.py's POSITIONS entry, so a position is config, not
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
    xg90: { label: 'xG per 90', invert: false, field: 'xg90' },
    xa90: { label: 'xA per 90', invert: false, field: 'xa90' },
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

  var HERO_X_DEFCON = 'defcon';                   // scout.HERO_X_DEFCON

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

  // The page's own purple ramp, matching scout.py's PERCENTILE_SCALE. A
  // percentile is sequential data with no midpoint to diverge around, so
  // a single hue with real luminance variation is both the correct shape
  // and the one that keeps this section inside the palette the rest of
  // the dashboard already uses.
  var PERCENTILE_SCALE = [
    [20.0, '#faf9fa', '#37003c'],
    [40.0, '#ebe5eb', '#37003c'],
    [60.0, '#d7ccd8', '#37003c'],
    [80.0, '#af99b1', '#37003c'],
    [100.1, '#7d5980', '#ffffff'],
  ];

  function percentileTone(pct) {
    for (var i = 0; i < PERCENTILE_SCALE.length; i++) {
      if (pct < PERCENTILE_SCALE[i][0]) { return PERCENTILE_SCALE[i]; }
    }
    return PERCENTILE_SCALE[PERCENTILE_SCALE.length - 1];
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
      // Kinder of the two rates - see scout._apply_filters for why.
      if (filters.minStartRate != null &&
          Math.max(r.startRate, r.startRateSinceFirst || 0) < filters.minStartRate) { return false; }
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

  function heroXKey(rows, heroX) {
    if (heroX && heroX !== HERO_X_DEFCON) { return heroX; }
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

  // {id: {row, data}} - the row and the position payload it came from, so
  // the card knows which tiles, sparklines and markers its position uses.
  // Updated by every lab's draw() - see initLab.
  var cardRowsById = {};

  // One number format per metric, shared by the table, the compare bars
  // and the card, so a figure never reads 27.6 in one place and 27.60 in
  // the next.
  function fmtValue(key, val) {
    if (key === 'defcon_hit_rate' || key === 'start_rate') { return Math.round(val * 100) + '%'; }
    if (key === 'minutes_per_start') { return String(Math.round(val)); }
    if (key === 'xp' || key === 'defcon90' || key === 'bps90') { return val.toFixed(1); }
    return val.toFixed(2);
  }

  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }

  // The small print under a card tile: the count a rate was made from.
  function tileNote(key, row) {
    if (key === 'defcon_hit_rate') { return row.defconHits + ' of ' + plural(row.defconHitN, 'start'); }
    if (key === 'start_rate') { return row.starts + ' of ' + row.teamMatches + ' matches'; }
    if (key === 'xg90') { return plural(row.goals, 'goal'); }
    if (key === 'xa90') { return plural(row.assists, 'assist'); }
    if (key === 'bonus90') { return row.bonus + ' bonus'; }
    return '';
  }

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

  // Goals and assists as one short tag: "G", "2G", "GA", "G2A".
  function gaTag(m) {
    var s = '';
    if (m.goals) { s += (m.goals > 1 ? m.goals : '') + 'G'; }
    if (m.assists) { s += (m.assists > 1 ? m.assists : '') + 'A'; }
    return s;
  }

  // `marks` is the position's stripMarks: which rows of markers sit under
  // the status marker - 'ga' (goals and assists) and/or 'defcon' (hit or
  // miss). `csOutline` draws the clean-sheet box round the bar.
  function renderMatchStrip(matches, marks, csOutline) {
    var n = matches.length;
    if (!n) { return '<p class="scpv-note">No matches played yet this season.</p>'; }
    var colW = 22, barTop = 12, barH = 60, markY = barTop + barH + 12;
    var w = n * colW, h = markY + 8 + marks.length * 13;
    var maxPts = Math.max(3, Math.max.apply(null, matches.map(function (m) { return m.points; })));
    var cols = matches.map(function (m, i) {
      var cx = i * colW + colW / 2;
      var bh = Math.max(1, (Math.max(0, m.points) / maxPts) * barH);
      var by = barTop + (barH - bh);
      var title = 'GW' + m.gw + (m.opp ? (m.home ? ' v ' : ' @ ') + m.opp : '') +
        ' - ' + m.minutes + ' min, ' + m.points + ' pts' +
        (m.goals ? ', ' + plural(m.goals, 'goal') : '') +
        (m.assists ? ', ' + plural(m.assists, 'assist') : '') +
        (marks.indexOf('defcon') >= 0 ? ', ' + m.defcon + ' contributions' : '');
      var markers = '<g transform="translate(' + cx + ',' + markY + ')">' + statusMarker(m.status) + '</g>';
      if (m.status !== 'unplayed') {
        marks.forEach(function (mark, k) {
          var y = markY + 14 + k * 13;
          if (mark === 'defcon') {
            markers += '<text class="mk-defcon' + (m.defconHit ? ' hit' : ' miss') + '" x="' + cx +
              '" y="' + y + '" text-anchor="middle">' + (m.defconHit ? '+' : '–') + '</text>';
          } else if (mark === 'ga' && gaTag(m)) {
            markers += '<text class="mk-ga" x="' + cx + '" y="' + y + '" text-anchor="middle">' +
              gaTag(m) + '</text>';
          }
        });
      }
      if (csOutline && m.cleanSheet) {
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
    // Drawn at a fixed 1.5x rather than stretched to the card's width: five
    // matches in September scaled to fill 640px made every bar a slab and
    // the whole strip taller than the dialog. It grows sideways as the
    // season does, and max-width keeps it inside the card once it fills.
    return '<svg class="scpv-strip" viewBox="0 0 ' + w + ' ' + h + '" width="' + (w * 1.5) +
      '" height="' + (h * 1.5) + '" preserveAspectRatio="xMinYMid meet">' + cols + '</svg>';
  }

  function stripKey(marks, csOutline) {
    var parts = ['<span class="mk-key-dot"></span> started', '<span class="mk-key-tri"></span> off the bench'];
    if (marks.indexOf('ga') >= 0) { parts.push('<span class="mk-ga">G</span>/<span class="mk-ga">A</span> goal, assist'); }
    if (marks.indexOf('defcon') >= 0) {
      parts.push('<span class="mk-defcon hit">+</span>/<span class="mk-defcon miss">–</span> DefCon hit, miss');
    }
    if (csOutline) { parts.push('outline = clean sheet'); }
    return '<span class="scpv-key">' + parts.join(' &middot; ') + '</span>';
  }

  function renderCard(entry) {
    var dlg = document.querySelector('dialog.scoutpv');
    if (!dlg || !entry) { return; }
    var row = entry.row, cfg = entry.data;
    var body = dlg.querySelector('.scpv-body');
    var pct = row.percentiles || {};
    var labels = cfg.archetypeLabels || {};

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
      return '<span class="archbadge archbadge-' + esc(a) + '">' + esc(labels[a] || a) + '</span>';
    }).join('');

    // Percentile against whichever pool is filtered in right now, the same
    // pool the table beside it is shaded against.
    var tiles = (cfg.cardTiles || []).map(function (key) {
      return bulletBar(pct[key] || 0, METRICS[key].label,
        fmtValue(key, row[METRICS[key].field]), tileNote(key, row));
    }).join('');

    var last10 = row.matches.slice(-10);
    var sparks = (cfg.sparks || []).map(function (s) {
      return '<div class="scpv-sparkwrap"><div class="scpv-spark-label">' + esc(s[1]) + '</div>' +
        sparkline(last10.map(function (m) { return m[s[0]] || 0; }), 100, 24) + '</div>';
    }).join('');

    var marks = cfg.stripMarks || [];
    body.innerHTML =
      '<div class="scpv-head"><h2>' + esc(row.webName) +
      ' <span class="scpv-team">' + esc(row.teamShort) + '</span></h2>' +
      '<p class="scpv-sub"><span class="tnum">£' + row.price.toFixed(1) + 'm</span> &middot; ' +
      esc(cfg.pos) + (archBadges ? ' &middot; ' + archBadges : '') + '</p></div>' +
      '<p class="scpv-flags">' + flags.map(function (f) { return '<span class="scpv-flag">' + esc(f) + '</span>'; }).join('') + '</p>' +
      '<div class="scpv-block"><h3>This season</h3><div class="scpv-grid">' + tiles + '</div></div>' +
      '<div class="scpv-block"><h3>Match by match ' + stripKey(marks, cfg.csOutline) + '</h3>' +
      renderMatchStrip(row.matches, marks, cfg.csOutline) + '</div>' +
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
    // Ranked on the one column that answers "who should I buy", not left
    // in the server's club-alphabetical order - a 97-row pool opening on
    // five Arsenal names is a directory, not a shortlist.
    var sortState = { key: 'xp', dir: -1 };
    var pinnedG = null, selGroup = null;

    var W = 1040, H = 520, ML = 62, MR = 18, MT = 18, MB = 48;
    // Marks sit this far inside the axes. Without it a player on zero sat
    // on the axis line itself: his bubble was half-clipped by the edge of
    // the plot and printed over the "0.0" tick label beside it.
    var PAD = 24;
    var archLabels = data.archetypeLabels || {};
    var sizeKey = data.sizeMetric || 'solidity_pct';
    var sizeName = sizeKey === 'solidity_pct' ? 'solidity'
      : (METRICS[sizeKey] ? METRICS[sizeKey].label : sizeKey);

    function fmtAxis(key, val) {
      return key === 'defcon_hit_rate' ? Math.round(val * 100) + '%' : val.toFixed(key === 'defcon90' ? 1 : 2);
    }

    function ordinal(n) {
      var s = ['th', 'st', 'nd', 'rd'], v = n % 100;
      return n + (s[(v - 20) % 10] || s[v] || s[0]);
    }

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

      function sx(v) { return ML + PAD + (v - x0) / (x1 - x0) * (W - ML - MR - 2 * PAD); }
      function sy(v) { return H - MB - PAD - (v - y0) / (y1 - y0) * (H - MT - MB - 2 * PAD); }

      var grid = node('g', { 'class': 'grid' });
      var labels = node('g', { 'class': 'axlab' });
      var yDigits = (y1 - y0) < 1.5 ? 2 : 1;
      yTicks.ticks.forEach(function (yv) {
        var gy = sy(yv);
        grid.appendChild(node('line', { x1: ML, y1: gy, x2: W - MR, y2: gy }));
        labels.appendChild(node('text', { x: ML - 8, y: gy + 4, 'text-anchor': 'end' }, yv.toFixed(yDigits)));
      });
      var xDigits = (x1 - x0) < 1.5 ? 2 : 1;
      xTicks.ticks.forEach(function (xv) {
        var gx = sx(xv);
        grid.appendChild(node('line', { x1: gx, y1: MT, x2: gx, y2: H - MB }));
        labels.appendChild(node('text', {
          x: gx, y: H - MB + 18, 'text-anchor': 'middle',
        }, heroX === 'defcon_hit_rate' ? Math.round(xv * 100) + '%' : xv.toFixed(xDigits)));
      });
      svg.appendChild(grid);
      svg.appendChild(labels);

      // On the xG x xA plane, faint diagonals of equal xGI: every point on
      // one line is involved in goals at the same rate, however the split
      // falls. It turns "finisher or creator" into "and how much of both"
      // without another word on the chart.
      if (xField === 'xg90' && yField === 'xa90') {
        var iso = node('g', { 'class': 'isoxgi' });
        var step = niceStep((x1 + y1) / 4);
        for (var c = step; c < x1 + y1 - step / 2; c += step) {
          // The x + y = c segment, clipped to the plotted box.
          var ax = c - y0, ay = y0, bx = x0, by = c - x0;
          if (ax > x1) { ax = x1; ay = c - x1; }
          if (by > y1) { by = y1; bx = c - y1; }
          if (ax - bx < (x1 - x0) * 0.08) { continue; }
          iso.appendChild(node('line', { x1: sx(ax), y1: sy(ay), x2: sx(bx), y2: sy(by) }));
          iso.appendChild(node('text', { x: sx(bx) + 5, y: sy(by) + 12 },
            (Math.round(c * 100) / 100) + ' xGI'));
        }
        svg.appendChild(iso);
      }
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
      var yLabel = (METRICS[yKey] ? METRICS[yKey].label : yKey).toLowerCase();
      // One corner tag, not four. The top-right quadrant is the only one
      // anyone is shopping in; labelling the other three restated the axis
      // titles in smaller type and turned the plot into a wall of words.
      svg.appendChild(node('text', {
        'class': 'quadlabel', x: W - MR - 6, y: MT + 13, 'text-anchor': 'end',
      }, 'better on both, this corner'));

      var pts = [];
      rows.forEach(function (r) {
        var cx = sx(r[xField]), cy = sy(r[yField]);
        var sizePct = r.percentiles[sizeKey] || 0;
        var radius = radiusForPercentile(sizePct);
        var thin = r.minutes < RATE_MIN_MINUTES;
        var detail = r.webName + ' (' + r.teamShort + ') - ' + r.price.toFixed(1) +
          'm, ' + fmtAxis(heroX, r[xField]) + ' ' + METRICS[heroX].label.toLowerCase() +
          ', ' + r[yField].toFixed(2) + ' ' + yLabel + ', ' + ordinal(Math.round(sizePct)) +
          ' percentile ' + sizeName.toLowerCase() + ', ' + r.minutes + ' min' +
          (r.archetypes.length
            ? ' - ' + r.archetypes.map(function (a) { return archLabels[a] || a; }).join(', ')
            : '');
        var g = node('g', {
          'class': 'scoutpt ' + (thin ? 'thin' : 'solid'),
          'data-pid': r.id, 'data-scout-open': r.id,
          tabindex: '0', role: 'button', 'aria-label': detail,
        });
        g.appendChild(node('circle', { cx: cx, cy: cy, r: radius }));
        // Hit target never smaller than the mark, never so much larger
        // that it swallows its neighbours in the dense middle of the plot.
        g.appendChild(node('circle', { 'class': 'hit', cx: cx, cy: cy, r: Math.max(radius, 8) }));
        g.appendChild(node('title', {}, detail));
        g._r = r; g._cx = cx; g._cy = cy; g._detail = detail;
        g.addEventListener('mouseenter', function () { pick(this); });
        g.addEventListener('focus', function () { pick(this); });
        svg.appendChild(g);
        pts.push({ r: r, cx: cx, cy: cy, g: g });
      });

      // Labels go to the handful of players furthest into the top-right
      // quadrant, not to everyone in it. Labelling the whole quadrant put
      // forty names on the plot, most of them overlapping, which is how
      // the chart ended up unreadable: a label nobody can read is worse
      // than no label, because it also hides the dot underneath it.
      var LABEL_MAX = 8;
      var topQuadrant = pts
        .filter(function (p) { return p.r[xField] >= medX && p.r[yField] >= medY; })
        .sort(function (a, b) {
          return Math.hypot(b.cx - mx, my - b.cy) - Math.hypot(a.cx - mx, my - a.cy);
        })
        .slice(0, LABEL_MAX);
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
      selGroup.setAttribute('display', 'none');  // 'hidden' does not hide SVG
      selGroup.appendChild(node('circle', { 'class': 'selring', r: 10 }));
      svg.appendChild(selGroup);

    }

    function pick(g) {
      if (!selGroup) { return; }
      var ring = selGroup.querySelector('.selring');
      ring.setAttribute('cx', g._cx); ring.setAttribute('cy', g._cy);
      selGroup.removeAttribute('display');
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
      if (selGroup) { selGroup.setAttribute('display', 'none'); }
      if (readout) { readout.innerHTML = defaultReadout; }
    }

    function archetypeBadges(archs) {
      return archs.map(function (a) {
        return '<span class="archbadge archbadge-' + esc(a) + '">' +
          esc(archLabels[a] || a) + '</span>';
      }).join('');
    }

    function renderHeatmap(rows) {
      if (!tbody) { return; }
      var visible = rows;
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
        // Under the minutes floor every per-90 and every rate on this row is
        // arithmetic rather than evidence (one start makes a 100% hit rate).
        // The leaderboards drop these; the pool keeps them and says so.
        if (r.thin) { tr.className = 'scout-thin'; }
        var thinMark = r.thin
          ? ' <abbr class="thinmark" title="' + r.minutes + ' minutes - too few for' +
            ' a reliable rate. Every per-90 and percentage on this row is off a' +
            ' small sample.">low sample</abbr>'
          : '';
        var cells = '<td><input type="checkbox" class="scoutpick" data-pid="' + r.id + '"' +
          (checked ? ' checked' : '') + (disabled ? ' disabled' : '') +
          ' aria-label="Add ' + esc(r.webName) + ' to shortlist"></td>' +
          '<td><button type="button" class="rowlink" data-scout-open="' + r.id + '">' +
          esc(r.webName) + '</button> <span class="teamtag">' +
          esc(r.teamShort) + '</span>' + flag + thinMark + '</td>' +
          '<td class="num tnum">£' + r.price.toFixed(1) + 'm</td>';
        data.metrics.forEach(function (key) {
          var pct = r.percentiles[key];
          var tone = percentileTone(pct);
          // A percentage with no denominator is the whole problem: 100% off
          // one start and 100% off ten render identically otherwise.
          var title = key === 'defcon_hit_rate'
            ? r.defconHits + ' of ' + r.defconHitN + ' starts'
            : key === 'start_rate'
              ? r.starts + ' of ' + r.teamMatches + " of his club's matches"
              : '';
          cells += '<td class="num tnum"' + (title ? ' title="' + esc(title) + '"' : '') +
            ' style="background:' + tone[1] + ';color:' + tone[2] + '">' +
            fmtValue(key, r[METRICS[key].field]) + '</td>';
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
        countEl.textContent = visible.length + ' of ' + data.rows.length + ' shown';
      }
    }

    function clampZ(z) { return Math.max(-Z_CLAMP, Math.min(Z_CLAMP, z)); }

    function fmtRaw(key, val) {
      return fmtValue(key, val) + (key === 'minutes_per_start' ? ' min' : '');
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
        // Gameweek only: the opponent differs by player, so it lives in
        // each cell. Heading the column with the first player's opponent
        // mislabelled every other row on the shortlist.
        ? rows[0].fixtures.slice(0, horizon).map(function (fx) {
            return '<th>GW' + fx.gw + '</th>';
          }).join('')
        : '';
      var body = rows.map(function (r) {
        var fx = r.fixtures.slice(0, horizon);
        function cells(field) {
          return fx.map(function (f) {
            if (f.blank) { return '<td class="tick-blank">-</td>'; }
            var tone = FIXTURE_TONES[f[field] - 1] || FIXTURE_TONES[2];
            // Same grammar as the fixture-run pills: capitals at home.
            var opp = f.home ? f.opp.toUpperCase() : f.opp.toLowerCase();
            return '<td style="background:' + tone[0] + ';color:' + tone[1] + '" title="GW' + f.gw +
              (f.home ? ', at home to ' : ', away to ') + esc(f.opp) + '">' +
              '<span class="tick-opp">' + esc(opp) + '</span> <b>' + f[field] + '</b></td>';
          }).join('');
        }
        return '<tr class="tick-name"><td colspan="' + (horizon + 1) + '"><b>' + esc(r.webName) + '</b>' +
          ' <span class="teamtag">' + esc(r.teamShort) + '</span></td></tr>' +
          (data.tickerRows || []).map(function (tr) {
            return '<tr><td class="tick-label">' + esc(tr[1]) + '</td>' + cells(tr[0]) + '</tr>';
          }).join('');
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
      currentRows = applyFilters(data.rows, filters);
      applyDerivations(currentRows, data.archetypes);
      currentRows.forEach(function (r) { cardRowsById[r.id] = { row: r, data: data }; });
      var heroX = heroXKey(currentRows, data.heroX);
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
    // The horizon control lives on the fixture-runs card, not here, but
    // the shortlist's own fixture strip has to follow it - one horizon per
    // position, whichever card the reader changed it on.
    var view = lab.closest('.scoutview') || panel;
    view.addEventListener('scout:horizon', function (ev) {
      filters.fixtureHorizon = ev.detail;
      if (compareCard && !compareCard.hidden) { renderCompare(); }
    });
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

  // -- fixture runs ----------------------------------------------------
  //
  // Two ranked club lists over a horizon the reader picks. Ranked here
  // rather than server-side because changing the horizon changes the
  // ranking, and a control that reorders nothing is the reason the old
  // horizon selector felt broken.

  // Each list reads one difficulty field (data-fx) and ranks kindest
  // first, or hardest first where the list is marked data-hardest.
  function initFixtureRuns(view, runs) {
    var card = view.querySelector('.scoutfx');
    if (!card || !runs) { return; }
    var sel = card.querySelector('.sf-horizon');
    if (!sel) { return; }

    var DEPTH = 6;

    function chips(cells, field, horizon) {
      return cells.slice(0, horizon).map(function (c) {
        if (c.blank) { return '<span class="rpill fxr-blank">&mdash;</span>'; }
        var tone = FIXTURE_TONES[c[field] - 1] || FIXTURE_TONES[2];
        var label = c.home ? c.opp.toUpperCase() : c.opp.toLowerCase();
        return '<span class="rpill" style="background:' + tone[0] + ';color:' + tone[1] +
          '" title="GW' + c.gw + ', ' + (c.home ? 'at home to ' : 'away to ') + esc(c.opp) +
          ' - difficulty ' + c[field] + ' of 5">' + esc(label) + '<b>' + c[field] + '</b></span>';
      }).join('');
    }

    function meanOver(run, field, horizon) {
      var real = run.cells.slice(0, horizon).filter(function (c) { return !c.blank; });
      if (!real.length) { return 99; }
      return real.reduce(function (s, c) { return s + c[field]; }, 0) / real.length;
    }

    function render() {
      var horizon = parseInt(sel.value, 10) || 6;
      card.querySelectorAll('.fxrun-list[data-fx]').forEach(function (list) {
        var field = list.dataset.fx;
        var dir = list.dataset.hardest ? -1 : 1;
        var ranked = runs.slice().sort(function (a, b) {
          return dir * (meanOver(a, field, horizon) - meanOver(b, field, horizon));
        }).slice(0, DEPTH);
        list.innerHTML = ranked.map(function (run, i) {
          return '<li><span class="slrank">' + (i + 1) + '</span>' +
            '<span class="fxrun-club">' + esc(run.club) + '</span>' +
            '<span class="fxrun-avg tnum" title="Average difficulty over the run">' +
            meanOver(run, field, horizon).toFixed(1) + '</span>' +
            '<span class="fxrun-chips">' + chips(run.cells, field, horizon) + '</span></li>';
        }).join('');
      });
      // One horizon per position: the shortlist's fixture strip listens for
      // this rather than keeping its own copy.
      view.dispatchEvent(new CustomEvent('scout:horizon', { detail: horizon }));
    }

    sel.addEventListener('change', render);
    render();
  }

  // -- position switch --------------------------------------------------
  //
  // One lab on screen at a time. Each is initialised the first time it is
  // shown rather than all three up front: nobody pays for laying out 200
  // midfielders to look at the defenders.

  var fixtureRuns = null;

  function initView(view) {
    if (!view || view._scoutReady) { return; }
    view._scoutReady = true;
    initFixtureRuns(view, fixtureRuns);
    view.querySelectorAll('.scoutlab').forEach(initLab);
  }

  function showPosition(pos) {
    var switcher = panel.querySelector('.scoutpos');
    if (switcher) {
      switcher.querySelectorAll('button[data-pos]').forEach(function (b) {
        b.setAttribute('aria-selected', String(b.dataset.pos === pos));
      });
    }
    var shown = null;
    panel.querySelectorAll('.scoutview').forEach(function (v) {
      v.hidden = v.dataset.pos !== pos;
      if (!v.hidden) { shown = v; }
    });
    initView(shown);
    document.dispatchEvent(new Event('rail:rebuild'));
    // Switching from deep in one lab lands at the top of the next, not at
    // the same pixel offset of a page that is now a different length.
    if (switcher && switcher.getBoundingClientRect().top < 0) {
      var bar = document.querySelector('.topbar');
      var off = (bar ? bar.getBoundingClientRect().height : 0) + 8;
      window.scrollTo(0, switcher.getBoundingClientRect().top + window.scrollY - off);
    }
  }

  function draw() {
    if (drawn) { return; }
    drawn = true;
    var holder = panel.querySelector('.scout-fixtures');
    if (holder) {
      try { fixtureRuns = JSON.parse(holder.textContent); }
      catch (e) { fixtureRuns = null; }
    }
    var switcher = panel.querySelector('.scoutpos');
    if (switcher) {
      switcher.addEventListener('click', function (ev) {
        var b = ev.target.closest('button[data-pos]');
        if (b) { showPosition(b.dataset.pos); }
      });
      // Arrow keys move along the control, as a tablist should.
      switcher.addEventListener('keydown', function (ev) {
        if (ev.key !== 'ArrowRight' && ev.key !== 'ArrowLeft') { return; }
        var btns = Array.from(switcher.querySelectorAll('button[data-pos]'));
        var i = btns.indexOf(document.activeElement);
        if (i < 0) { return; }
        var next = btns[(i + (ev.key === 'ArrowRight' ? 1 : btns.length - 1)) % btns.length];
        next.focus();
        showPosition(next.dataset.pos);
      });
    }
    initView(panel.querySelector('.scoutview:not([hidden])'));
  }

  panel.addEventListener('panel:shown', draw);
  if (!panel.hidden) { draw(); }
})();
