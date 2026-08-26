// Expanded player view.
//
// One dialog, filled from the JSON payload rather than fifteen copies of the
// same markup. Opened from a pitch card or a squad-table row; the match log
// lives in here now rather than in a tab of its own, because a log only means
// anything next to the player it belongs to.
(function () {
  var holder = document.getElementById('player-data');
  var dlg = document.querySelector('dialog.pv');
  if (!holder || !dlg) { return; }

  var store = JSON.parse(holder.textContent);
  var players = {};
  store.players.forEach(function (p) { players[p.id] = p; });
  var optaLabels = store.optaLabels || {};
  var body = dlg.querySelector('.pv-body');

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function stat(label, value, note) {
    return '<div class="pvs"><span class="pvs-k">' + esc(label) + '</span>' +
      '<span class="pvs-v">' + esc(value) + '</span>' +
      (note ? '<span class="pvs-n">' + esc(note) + '</span>' : '') + '</div>';
  }

  // Same five-step scale the fixture ticker uses, so a fixture reads the same
  // wherever it appears on the page.
  function csTone(cs) {
    if (cs >= 45) { return ['#1e0021', '#fff']; }
    if (cs >= 36) { return ['#41054b', '#fff']; }
    if (cs >= 28) { return ['#7d5980', '#fff']; }
    if (cs >= 20) { return ['#af99b1', '#37003c']; }
    return ['#ebe5eb', '#37003c'];
  }

  function sparkline(values, tone) {
    if (!values || values.length < 2) { return ''; }
    var w = 120, h = 30, lo = Math.min.apply(null, values),
        hi = Math.max.apply(null, values), span = (hi - lo) || 1,
        step = w / (values.length - 1), d = '';
    var last = [0, 0];
    values.forEach(function (v, i) {
      var x = i * step, y = h - 3 - (v - lo) / span * (h - 8);
      d += (i ? 'L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
      last = [x, y];
    });
    return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" width="' + w +
      '" height="' + h + '" aria-hidden="true"><path d="' + d +
      '" fill="none" stroke="' + tone + '" stroke-width="2" ' +
      'stroke-linejoin="round" stroke-linecap="round"/><circle cx="' +
      last[0].toFixed(1) + '" cy="' + last[1].toFixed(1) +
      '" r="3" fill="' + tone + '"/></svg>';
  }

  function render(p) {
    var h = [];
    h.push('<header class="pv-head">' +
      (p.photo ? '<img class="pv-photo" src="' + p.photo + '" alt="" width="66" height="84">' : '') +
      '<div>' +
      '<h2>' + esc(p.name) + '</h2>' +
      '<p class="pv-sub">' + esc(p.pos) + ' &middot; ' + esc(p.team) +
      ' &middot; ' + p.price.toFixed(1) + 'm &middot; ' + p.owned +
      '% owned</p></div>');
    if (p.predicted === true) {
      h.push('<span class="lu lu-in">Predicted XI</span>');
    } else if (p.predicted === false) {
      h.push('<span class="lu lu-out">Not predicted</span>');
    }
    h.push('</header>');

    if (p.flag) {
      h.push('<p class="pv-alert"><b>' + esc(p.flag) + '</b> ' +
        esc(p.news || '') + '</p>');
    }

    if (p.ep) {
      var parts = [
        ['Goals', p.ep.goals, '#953bff'],
        ['Assists', p.ep.assists, '#00b3d6'],
        ['Clean sheet', p.ep.defence, '#00a35c'],
        ['Appearance', p.ep.appearance, '#87668a'],
        ['DefCon', p.ep.defcon, '#e07b00'],
        ['Bonus', p.ep.bonus, '#d81b8c']
      ];
      var segs = parts.map(function (q) {
        if (!q[1] || q[1] <= 0.01) { return ''; }
        return '<span class="seg" style="width:' +
          (q[1] / p.ep.total * 100).toFixed(1) + '%;background:' + q[2] +
          '" title="' + q[0] + ' ' + q[1].toFixed(2) + '"></span>';
      }).join('');
      // Every component printed as a number too: several segment colours sit
      // under 3:1 against the surface, so the bar is never the only way to
      // read this.
      var rows = parts.filter(function (q) { return q[1] && q[1] > 0.01; })
        .map(function (q) {
          return '<li><i style="background:' + q[2] + '"></i>' +
            '<span>' + q[0] + '</span><b>' + q[1].toFixed(2) + '</b></li>';
        }).join('');
      var src = p.ep.cs_source === 'market'
        ? 'Clean-sheet odds and the goals line are priced by the betting market.'
        : 'Clean-sheet odds and the goals line come from a model; the market has ' +
          'not priced this fixture yet.';
      h.push('<section class="pv-block"><h3>Expected points, next match</h3>' +
        '<p class="pv-big">' + p.ep.total.toFixed(2) +
        '<span class="pv-big-n"> vs ' + esc(p.ep.opponent) + ' (' +
        (p.ep.home ? 'H' : 'A') + '), ' + Math.round(p.ep.cs) +
        '% clean sheet</span></p>' +
        '<span class="epbar wide">' + segs + '</span>' +
        '<ul class="eprows">' + rows + '</ul>' +
        '<p class="pv-note">' + esc(p.ep.exp_goals.toFixed(2)) +
        ' expected goals and ' + esc(p.ep.exp_assists.toFixed(2)) +
        ' expected assists from a side priced at ' + p.ep.team_xg.toFixed(2) +
        ' goals, against their season norm of ' + p.ep.baseline.toFixed(2) +
        '. ' + src + '</p></section>');
    }

    // FPL's numbers and the Premier League's Opta numbers are all just "what
    // he has done this season", so they sit in one grid rather than being
    // split by which API happened to supply them.
    var tiles = [
      stat('Points', p.points, p.bonus + ' bonus'),
      stat('Minutes', p.minutes, p.starts + ' of ' + p.apps + ' started'),
      stat('Goals', p.goals, p.xg.toFixed(2) + ' expected'),
      stat('Assists', p.assists, p.xa.toFixed(2) + ' expected'),
      stat('xGI per 90', p.xgi90.toFixed(2), p.xgi.toFixed(2) + ' total')
    ];
    if (p.threshold) {
      tiles.push(stat('DefCon per 90', p.defcon90.toFixed(1),
        'threshold ' + p.threshold + ', hit ' + p.defconHits + 'x'));
    }
    var opta = p.opta || {};
    Object.keys(opta).forEach(function (k) {
      if (opta[k]) { tiles.push(stat(optaLabels[k] || k, opta[k], 'Opta')); }
    });
    h.push('<section class="pv-block"><h3>This season</h3>' +
      '<div class="pv-grid">' + tiles.join('') + '</div>' +
      '<p class="pv-note">Tiles marked Opta come from the Premier League API; ' +
      'the rest from FPL.</p></section>');

    if (p.setpieces && p.setpieces.length) {
      h.push('<section class="pv-block"><h3>Set pieces</h3><p class="pv-chips">' +
        p.setpieces.map(function (s) {
          return '<span class="chiptag">' + esc(s) + '</span>';
        }).join('') + '</p></section>');
    }

    if (p.fixtures && p.fixtures.length) {
      h.push('<section class="pv-block"><h3>Next fixtures</h3><div class="pv-fx">' +
        p.fixtures.map(function (fx) {
          var t = csTone(fx.cs);
          return '<span class="fxcell" style="background:' + t[0] + ';color:' +
            t[1] + '" title="GW' + fx.gw + ', ' + fx.xg +
            ' expected goals"><b>' +
            esc(fx.home ? fx.opp.toUpperCase() : fx.opp.toLowerCase()) +
            '</b><i>' + fx.cs + '%</i></span>';
        }).join('') + '</div>' +
        '<p class="pv-note">Shaded by clean-sheet probability.</p></section>');
    }

    if (p.log && p.log.length) {
      var pts = p.log.map(function (r) { return r.pts; });
      h.push('<section class="pv-block"><h3>Match log' +
        (pts.length > 1 ? '<span class="pv-spark">' +
          sparkline(pts, 'var(--lilac)') + '</span>' : '') +
        '</h3><div class="scroll"><table><thead><tr>' +
        '<th>GW</th><th>Opponent</th><th class="num">Min</th>' +
        '<th class="num">G</th><th class="num">A</th><th class="num">xG</th>' +
        '<th class="num">xA</th><th class="num">DefCon</th>' +
        '<th class="num">BPS</th><th class="num">Pts</th></tr></thead><tbody>' +
        p.log.slice().reverse().map(function (r) {
          return '<tr><td>GW' + r.gw + '</td><td>' + esc(r.opp) + ' (' +
            (r.home ? 'H' : 'A') + ')</td><td class="num">' + r.min +
            '</td><td class="num">' + r.g + '</td><td class="num">' + r.a +
            '</td><td class="num">' + r.xg.toFixed(2) + '</td><td class="num">' +
            r.xa.toFixed(2) + '</td><td class="num">' + r.dc +
            '</td><td class="num">' + r.bps + '</td><td class="num"><b>' +
            r.pts + '</b></td></tr>';
        }).join('') + '</tbody></table></div></section>');
    }

    if (p.last) {
      h.push('<section class="pv-block"><h3>Last season</h3><p class="pv-note">' +
        p.last.points + ' points from ' + p.last.minutes.toLocaleString() +
        ' minutes. ' + (p.last.goals + p.last.assists) +
        ' goals and assists from ' + p.last.xgi.toFixed(1) +
        ' expected.</p></section>');
    }

    body.innerHTML = h.join('');
  }

  function open(id) {
    var p = players[id];
    if (!p) { return; }
    render(p);
    if (typeof dlg.showModal === 'function') { dlg.showModal(); }
    else { dlg.setAttribute('open', ''); }
    body.scrollTop = 0;
  }

  document.addEventListener('click', function (ev) {
    var trigger = ev.target.closest('[data-player]');
    if (trigger) {
      ev.preventDefault();
      open(parseInt(trigger.dataset.player, 10));
    }
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
    var trigger = ev.target.closest && ev.target.closest('[data-player]');
    if (trigger) { ev.preventDefault(); open(parseInt(trigger.dataset.player, 10)); }
  });
  dlg.querySelector('.pv-close').addEventListener('click', function () {
    dlg.close();
  });
  dlg.addEventListener('click', function (ev) {
    if (ev.target === dlg) { dlg.close(); }
  });
})();
