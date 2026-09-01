// League position over time, drawn in the browser.
//
// One straight-segment line per manager (no curve fitting - a gameweek is
// a gameweek, there is nothing to smooth between two of them), toggled
// between rank-in-this-league and total points on the Y axis. Position
// runs 1-at-the-top, since rank 1 is the thing worth reading as "up".
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var W = 720, H = 360, ML = 40, MR = 16, MT = 16, MB = 34;

  function node(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) { n.setAttribute(k, attrs[k]); }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  // A fixed hue rotation rather than a hand-picked palette - a league can
  // have anywhere from a handful of managers to the full standings limit,
  // and a palette sized for one league would run out or repeat on another.
  function colourFor(i, n, mine) {
    if (mine) { return 'var(--accent-ink)'; }
    var hue = Math.round((360 / Math.max(1, n)) * i);
    return 'hsl(' + hue + ', 55%, 48%)';
  }

  document.querySelectorAll('.card').forEach(function (card) {
    var holder = card.querySelector('.lpchart-data');
    if (!holder) { return; }
    var svg = card.querySelector('svg.lpchart');
    var data = JSON.parse(holder.textContent);
    var gws = data.gws;
    var series = data.series;
    var n = series.length;
    var yMode = 'position';

    card.querySelectorAll('.lpswatch').forEach(function (sw) {
      var i = Number(sw.getAttribute('data-i'));
      sw.style.background = colourFor(i, n, series[i].mine);
    });

    function draw() {
      while (svg.firstChild) { svg.removeChild(svg.firstChild); }
      if (!gws.length) { return; }

      var yVals = [];
      series.forEach(function (s) {
        s[yMode].forEach(function (v) { if (v !== null && v !== undefined) { yVals.push(v); } });
      });
      var y0, y1;
      if (yMode === 'position') {
        y0 = 1; y1 = Math.max.apply(null, yVals.concat([n]));
      } else {
        y0 = 0; y1 = Math.max.apply(null, yVals) * 1.05 || 1;
      }
      var x0 = gws[0], x1 = gws[gws.length - 1] || x0 + 1;
      if (x1 === x0) { x1 = x0 + 1; }

      function sx(gw) { return ML + (gw - x0) / (x1 - x0) * (W - ML - MR); }
      function sy(v) {
        if (yMode === 'position') {
          return MT + (v - y0) / (y1 - y0 || 1) * (H - MT - MB);
        }
        return H - MB - (v - y0) / (y1 - y0 || 1) * (H - MT - MB);
      }

      var grid = node('g', { 'class': 'lpgrid' });
      var yticks = yMode === 'position' ? Math.min(n, 6) : 5;
      for (var i = 0; i <= yticks; i++) {
        var yv = y0 + (y1 - y0) * i / yticks;
        var gy = sy(yv);
        grid.appendChild(node('line', { x1: ML, y1: gy, x2: W - MR, y2: gy }));
        grid.appendChild(node('text', { x: ML - 8, y: gy + 4, 'text-anchor': 'end' },
          yMode === 'position' ? Math.round(yv) : Math.round(yv)));
      }
      gws.forEach(function (gw) {
        grid.appendChild(node('text', { x: sx(gw), y: H - MB + 18, 'text-anchor': 'middle' },
          'GW' + gw));
      });
      svg.appendChild(grid);

      var lines = node('g', { 'class': 'lplines' });
      series.forEach(function (s, i) {
        var pts = [];
        gws.forEach(function (gw, gi) {
          var v = s[yMode][gi];
          if (v === null || v === undefined) { return; }
          pts.push(sx(gw) + ',' + sy(v));
        });
        if (pts.length < 2) { return; }
        var g = node('g', { 'class': 'lpline lpline-' + i + (s.mine ? ' lp-mine' : ''), 'data-i': i });
        g.appendChild(node('polyline', {
          points: pts.join(' '), fill: 'none',
          stroke: colourFor(i, n, s.mine), 'stroke-width': s.mine ? 3 : 1.6,
        }));
        gws.forEach(function (gw, gi) {
          var v = s[yMode][gi];
          if (v === null || v === undefined) { return; }
          var dot = node('circle', {
            cx: sx(gw), cy: sy(v), r: s.mine ? 3.6 : 2.4,
            fill: colourFor(i, n, s.mine),
          });
          dot.appendChild(node('title', {}, s.name + ' - GW' + gw + ': ' +
            (yMode === 'position' ? ('#' + v) : (v + ' pts'))));
          g.appendChild(dot);
        });
        lines.appendChild(g);
      });
      svg.appendChild(lines);
    }

    function setActive(i) {
      card.querySelectorAll('.lpline').forEach(function (g) {
        var isActive = i === null || Number(g.getAttribute('data-i')) === i;
        g.classList.toggle('dim', !isActive);
      });
      card.querySelectorAll('.lpleg').forEach(function (li) {
        var isActive = i === null || Number(li.getAttribute('data-i')) === i;
        li.classList.toggle('dim', !isActive);
      });
    }

    card.querySelectorAll('.lpleg').forEach(function (li) {
      var i = Number(li.getAttribute('data-i'));
      li.addEventListener('mouseenter', function () { setActive(i); });
      li.addEventListener('mouseleave', function () { setActive(null); });
      li.addEventListener('focus', function () { setActive(i); });
      li.addEventListener('blur', function () { setActive(null); });
    });

    card.querySelectorAll('.lpbtn').forEach(function (b) {
      b.addEventListener('click', function () {
        yMode = b.dataset.y;
        card.querySelectorAll('.lpbtn').forEach(function (o) {
          o.setAttribute('aria-pressed', String(o === b));
        });
        draw();
      });
    });

    draw();
  });
})();
