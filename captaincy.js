// Captaincy Decision Matrix radar, drawn in the browser.
//
// Values arrive already normalised 0-100 (captaincy.py, relative to the
// candidates shown) for the shape, plus each metric's raw value and unit for
// the hover readout. Hovering a shape (from the chart or the legend)
// highlights it and dims the rest; hovering a single dot also swaps the
// readout line to that exact metric's value.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var CX = 200, CY = 175, R = 115;

  function node(tag, attrs, text) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) { n.setAttribute(k, attrs[k]); }
    if (text !== undefined) { n.textContent = text; }
    return n;
  }

  function angleFor(i, n) {
    return -Math.PI / 2 + i * (2 * Math.PI / n);
  }

  function point(i, n, value) {
    var a = angleFor(i, n);
    var r = (value / 100) * R;
    return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
  }

  function fmtValue(raw, unit) {
    if (unit === 'pts') { return raw.toFixed(0) + ' pts'; }
    if (unit === '%') { return raw.toFixed(0) + '%'; }
    if (unit === 'x') { return raw.toFixed(2) + 'x'; }
    if (unit === 'xG') { return raw.toFixed(2) + ' xG'; }
    return String(raw);
  }

  document.querySelectorAll('.card').forEach(function (card) {
    var holder = card.querySelector('.captaincy-data');
    if (!holder) return;

    var svg = card.querySelector('svg.radar');
    var readout = card.querySelector('.radar-readout');
    var defaultReadout = readout ? readout.textContent : '';
    var data = JSON.parse(holder.textContent);
    var metrics = data.metrics;
    var candidates = data.candidates;
    var n = metrics.length;

    while (svg.firstChild) { svg.removeChild(svg.firstChild); }

    var grid = node('g', { class: 'radar-grid' });
    [0.25, 0.5, 0.75, 1].forEach(function (frac) {
      var pts = metrics.map(function (_m, i) {
        var a = angleFor(i, n);
        var r = frac * R;
        return (CX + r * Math.cos(a)) + ',' + (CY + r * Math.sin(a));
      }).join(' ');
      grid.appendChild(node('polygon', { points: pts, class: 'radar-ring' }));
    });
    svg.appendChild(grid);

    var axes = node('g', { class: 'radar-axes' });
    metrics.forEach(function (_m, i) {
      var a = angleFor(i, n);
      var x = CX + R * Math.cos(a), y = CY + R * Math.sin(a);
      axes.appendChild(node('line', {
        x1: CX, y1: CY, x2: x, y2: y, class: 'radar-axis-line',
      }));
    });
    svg.appendChild(axes);

    function summaryText(c) {
      return c.player + ' — vs ' + c.opponent + (c.home ? ' (H)' : ' (A)') +
        ', ' + c.ep_total.toFixed(1) + ' pts projected';
    }

    function detailText(c, m) {
      var raw = c[m.key];
      var noteKey = m.key + '_note';
      var note = c[noteKey] ? ' (' + c[noteKey] + ')' : '';
      return c.player + ' — ' + m.label + ': ' + fmtValue(raw, m.unit) + note;
    }

    var areas = node('g', { class: 'radar-areas' });
    var legendItems = card.querySelectorAll('.radar-leg');

    function setActive(i) {
      areas.querySelectorAll('.radar-area').forEach(function (g) {
        var isActive = i === null || Number(g.getAttribute('data-i')) === i;
        g.classList.toggle('dim', !isActive);
        g.classList.toggle('active', i !== null && Number(g.getAttribute('data-i')) === i);
      });
      legendItems.forEach(function (li) {
        var isActive = i === null || Number(li.getAttribute('data-i')) === i;
        li.classList.toggle('dim', !isActive);
        li.classList.toggle('active', i !== null && Number(li.getAttribute('data-i')) === i);
      });
    }

    function setReadout(text) {
      if (readout) { readout.textContent = text || defaultReadout; }
    }

    candidates.forEach(function (c, ci) {
      var pts = metrics.map(function (m, i) {
        var v = c.values[m.key] || 0;
        var p = point(i, n, v);
        return p[0] + ',' + p[1];
      }).join(' ');
      var g = node('g', { class: 'radar-area radar-c' + ci, 'data-i': ci });
      g.appendChild(node('polygon', { points: pts, class: 'radar-fill' }));
      metrics.forEach(function (m, i) {
        var v = c.values[m.key] || 0;
        var p = point(i, n, v);
        var dot = node('circle', {
          cx: p[0], cy: p[1], r: 4, class: 'radar-dot', 'data-m': i,
          tabindex: '0', role: 'img',
          'aria-label': detailText(c, m),
        });
        dot.appendChild(node('title', {}, detailText(c, m)));
        dot.addEventListener('focus', function () {
          setActive(ci);
          setReadout(detailText(c, m));
        });
        g.appendChild(dot);
      });
      // mouseover/mouseout (both bubble) rather than mouseenter/mouseleave on
      // the group plus separate listeners per dot - mouseenter fires on every
      // ancestor a pointer newly lands inside, so entering directly on a dot
      // raced the group's own handler and the summary text could clobber the
      // more specific one. Delegating to a single pair of listeners and
      // reading event.target avoids the race entirely.
      g.addEventListener('mouseover', function (e) {
        setActive(ci);
        if (e.target.classList.contains('radar-dot')) {
          var mi = Number(e.target.getAttribute('data-m'));
          setReadout(detailText(c, metrics[mi]));
        } else {
          setReadout(summaryText(c));
        }
      });
      g.addEventListener('mouseout', function (e) {
        if (!g.contains(e.relatedTarget)) {
          setActive(null);
          setReadout(null);
        }
      });
      areas.appendChild(g);
    });
    svg.appendChild(areas);

    // Labels drawn last so they sit above every polygon.
    var labels = node('g', { class: 'radar-labels' });
    metrics.forEach(function (m, i) {
      var a = angleFor(i, n);
      var lx = CX + (R + 26) * Math.cos(a);
      var ly = CY + (R + 26) * Math.sin(a);
      var cos = Math.cos(a);
      var anchor = Math.abs(cos) < 0.2 ? 'middle' : (cos > 0 ? 'start' : 'end');
      labels.appendChild(node('text', {
        x: lx, y: ly, class: 'radar-label', 'text-anchor': anchor,
        'dominant-baseline': 'middle',
      }, m.label));
    });
    svg.appendChild(labels);

    legendItems.forEach(function (li) {
      var i = Number(li.getAttribute('data-i'));
      var c = candidates[i];
      li.addEventListener('mouseenter', function () { setActive(i); setReadout(summaryText(c)); });
      li.addEventListener('mouseleave', function () { setActive(null); setReadout(null); });
      li.addEventListener('focus', function () { setActive(i); setReadout(summaryText(c)); });
      li.addEventListener('blur', function () { setActive(null); setReadout(null); });
    });
  });
})();
