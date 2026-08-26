// Value scatter, drawn in the browser.
//
// Server-side SVG was fine while the axes were fixed, but switching a measure
// rescales the domain, the ticks and every point together - so the data is
// emitted once and laid out here. Roughly a hundred lines against generating
// every possible axis pairing up front.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var W = 760, H = 400, ML = 62, MR = 18, MT = 18, MB = 48;

  document.querySelectorAll('.card').forEach(function (card) {
    var holder = card.querySelector('.scatter-data');
    if (!holder) return;

    var svg = card.querySelector('svg.scatter');
    var out = card.querySelector('.readout');
    var data = JSON.parse(holder.textContent);
    var pos = 'ALL';
    var selGroup = null;

    function axisLabel(key) {
      var o = card.querySelector('.axis[data-axis="y"] option[value="' + key + '"]');
      return o ? o.textContent : key;
    }

    function node(tag, attrs, text) {
      var n = document.createElementNS(NS, tag);
      for (var k in attrs) { n.setAttribute(k, attrs[k]); }
      if (text !== undefined) { n.textContent = text; }
      return n;
    }

    // Decimals follow the span of the axis, not the size of the number: two
    // decimals suit a 0-to-2 xGI scale and look wrong on a points axis, where
    // "-2.00" reads as a measurement rather than a whole number of points.
    function fmt(v, span) {
      if (span >= 20) { return v.toFixed(0); }
      if (span >= 4) { return v.toFixed(1); }
      return v.toFixed(2);
    }

    function draw() {
      var xk = card.querySelector('.axis[data-axis="x"]').value;
      var yk = card.querySelector('.axis[data-axis="y"]').value;
      var rows = data.filter(function (d) { return pos === 'ALL' || d.p === pos; });

      while (svg.firstChild) { svg.removeChild(svg.firstChild); }
      if (!rows.length) { return; }

      var xs = rows.map(function (d) { return d[xk]; });
      var ys = rows.map(function (d) { return d[yk]; });
      var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
      var y0 = Math.min(0, Math.min.apply(null, ys)), y1 = Math.max.apply(null, ys);
      var xpad = (x1 - x0) * 0.06 || 1;
      var ypad = (y1 - y0) * 0.08 || 1;
      x0 -= xpad; x1 += xpad; y1 += ypad;
      if (x1 === x0) { x1 = x0 + 1; }
      if (y1 === y0) { y1 = y0 + 1; }

      function sx(v) { return ML + (v - x0) / (x1 - x0) * (W - ML - MR); }
      function sy(v) { return H - MB - (v - y0) / (y1 - y0) * (H - MT - MB); }

      var grid = node('g', { 'class': 'grid' });
      var labels = node('g', { 'class': 'axlab' });
      var i;
      for (i = 0; i <= 4; i++) {
        var yv = y0 + (y1 - y0) * i / 4, gy = sy(yv);
        grid.appendChild(node('line', { x1: ML, y1: gy, x2: W - MR, y2: gy }));
        labels.appendChild(node('text',
          { x: ML - 8, y: gy + 4, 'text-anchor': 'end' }, fmt(yv, y1 - y0)));
      }
      for (i = 0; i <= 5; i++) {
        var xv = x0 + (x1 - x0) * i / 5, gx = sx(xv);
        grid.appendChild(node('line', { x1: gx, y1: MT, x2: gx, y2: H - MB }));
        labels.appendChild(node('text',
          { x: gx, y: H - MB + 18, 'text-anchor': 'middle' }, fmt(xv, x1 - x0)));
      }
      svg.appendChild(grid);
      svg.appendChild(labels);
      svg.appendChild(node('text',
        { 'class': 'axtitle', x: (ML + W - MR) / 2, y: H - 8, 'text-anchor': 'middle' },
        axisLabel(xk)));
      svg.appendChild(node('text',
        {
          'class': 'axtitle', 'text-anchor': 'middle',
          transform: 'translate(16,' + ((MT + H - MB) / 2) + ') rotate(-90)'
        },
        axisLabel(yk)));

      var mine = [];
      rows.forEach(function (d) {
        var cx = sx(d[xk]), cy = sy(d[yk]);
        var detail = d.n + ' (' + d.t + ', ' + d.p + ') - ' + d.price.toFixed(1) +
          'm, ' + d.points + ' pts, ' + d.xgi90.toFixed(2) + ' xGI per 90, ' +
          d.minutes + ' min, ' + d.owned + '% owned';
        var g = node('g', {
          'class': 'pt ' + (d.mine ? 'mine' : 'mkt'),
          tabindex: '0', role: 'button', 'aria-label': detail
        });
        g.appendChild(node('circle', { cx: cx, cy: cy, r: d.mine ? 6.5 : 3.5 }));
        // Hit target deliberately larger than the mark.
        g.appendChild(node('circle', { 'class': 'hit', cx: cx, cy: cy, r: 11 }));
        g.appendChild(node('title', {}, detail));
        g._d = d; g._cx = cx; g._cy = cy; g._detail = detail;
        g.addEventListener('click', function () { pick(this); });
        g.addEventListener('focus', function () { pick(this); });
        svg.appendChild(g);
        if (d.mine) { mine.push({ d: d, cx: cx, cy: cy }); }
      });

      // Greedy de-collision: try slots above the dot, then further off, and
      // take the first that does not overlap a label already placed.
      var placed = [];
      mine.forEach(function (m) {
        var halfw = m.d.n.length * 3.2 + 4;
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
        if (ly === null) { lx = m.cx; ly = m.cy - 11; }
        svg.appendChild(node('text',
          { 'class': 'ptlabel', x: lx, y: ly, 'text-anchor': 'middle' }, m.d.n));
      });

      selGroup = node('g', { 'class': 'sel' });
      selGroup.setAttribute('hidden', '');
      selGroup.appendChild(node('circle', { 'class': 'selring', r: 10 }));
      selGroup.appendChild(node('text', { 'class': 'selname', 'text-anchor': 'middle' }));
      svg.appendChild(selGroup);
    }

    function pick(g) {
      if (!selGroup) { return; }
      var ring = selGroup.querySelector('.selring');
      var nm = selGroup.querySelector('.selname');
      ring.setAttribute('cx', g._cx);
      ring.setAttribute('cy', g._cy);
      nm.setAttribute('x', g._cx);
      nm.setAttribute('y', (g._cy - 16).toFixed(1));
      nm.textContent = g._d.n;
      selGroup.removeAttribute('hidden');
      if (out) {
        out.innerHTML = '<b>' + g._d.n + '</b>' +
          g._detail.slice(g._d.n.length);
      }
    }

    card.querySelectorAll('.axis').forEach(function (a) {
      a.addEventListener('change', draw);
    });
    card.querySelectorAll('.chip[data-pos]').forEach(function (c) {
      c.addEventListener('click', function () {
        pos = c.dataset.pos;
        card.querySelectorAll('.chip[data-pos]').forEach(function (o) {
          o.setAttribute('aria-pressed', String(o === c));
        });
        draw();
      });
    });

    draw();
  });
})();
