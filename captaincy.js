// Captaincy Decision Matrix radar, drawn in the browser.
//
// Values arrive already normalised 0-100 (captaincy.py, against each
// metric's own fixed real-world range - not the candidates shown) for the
// shape, plus each metric's raw value and unit for the hover readout and
// the pinned callouts. Hovering a shape (from the chart or the legend)
// highlights it and dims the rest; hovering a single dot also swaps the
// readout line to that exact metric's value. Clicking a name pins all five
// as short arrows sprouting from that shape's own vertices out to a label
// and value at each axis - a mind-map read of the one shape, in place
// rather than a separate detail panel elsewhere on the card.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  // R bumped from 115 and CX/CY re-centred for it - both the plain axis
  // labels and the pinned callout numbers were reported too small, and the
  // fix is a bigger chart to draw them at, not just bigger font-size on a
  // cramped one. LEADER_R (where a pinned callout's arrow actually stops)
  // and TEXT_R (where its two lines of text sit) are now different radii,
  // not the same one label position doing both jobs - the top axis (Form,
  // pointing straight up) used to have its arrowhead landing right in the
  // gap between its own label and value line, since both text lines
  // straddled the exact point the arrow ended on.
  var CX = 210, CY = 195, R = 130;
  var LEADER_R = R + 16;
  var TEXT_R = R + 44;

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

  // Responsibilities is a blind 0-100 weighting under the hood (see
  // captaincy.py), but "65%" on its own answers a question nobody asked -
  // what matters for a captaincy call is which duties he's actually on.
  // Show that instead, everywhere the other four axes show a number.
  function displayValue(c, m) {
    if (m.key === 'responsibility') { return c.responsibility_label; }
    return fmtValue(c[m.key], m.unit);
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

    // One marker per candidate colour, not one shared marker - an SVG
    // <marker>'s content takes its style from where it sits in the
    // document (inside <defs>), not from whichever line references it via
    // marker-end, so a single currentColor marker would not follow each
    // candidate's own line colour the way the line itself does.
    var defs = node('defs', {});
    candidates.forEach(function (_c, i) {
      var arrow = node('marker', {
        id: 'radar-arrow-' + i, viewBox: '0 0 8 8', refX: '7', refY: '4',
        markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse',
      });
      arrow.appendChild(node('path', {
        d: 'M0,0 L8,4 L0,8 Z', class: 'radar-arrow-head radar-c' + i,
      }));
      defs.appendChild(arrow);
    });
    svg.appendChild(defs);

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
      var noteKey = m.key + '_note';
      // Responsibilities' display value already *is* the note ("Penalties,
      // free kicks") - appending c.responsibility_note again would just
      // repeat it in parentheses.
      var note = (m.key !== 'responsibility' && c[noteKey]) ? ' (' + c[noteKey] + ')' : '';
      return c.player + ' — ' + m.label + ': ' + displayValue(c, m) + note;
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

    function labelAnchor(i) {
      var a = angleFor(i, n);
      var cos = Math.cos(a);
      return {
        x: CX + TEXT_R * Math.cos(a), y: CY + TEXT_R * Math.sin(a),
        anchor: Math.abs(cos) < 0.2 ? 'middle' : (cos > 0 ? 'start' : 'end'),
      };
    }

    function leaderPoint(i) {
      var a = angleFor(i, n);
      return [CX + LEADER_R * Math.cos(a), CY + LEADER_R * Math.sin(a)];
    }

    // Labels drawn last so they sit above every polygon.
    var labels = node('g', { class: 'radar-labels' });
    metrics.forEach(function (m, i) {
      var p = labelAnchor(i);
      labels.appendChild(node('text', {
        x: p.x, y: p.y, class: 'radar-label', 'text-anchor': p.anchor,
        'dominant-baseline': 'middle',
      }, m.label));
    });
    svg.appendChild(labels);

    var callouts = node('g', { class: 'radar-callouts' });
    svg.appendChild(callouts);

    // Hovering shows one line at a time - useful for a quick pass down the
    // chart, but "how does he actually break down" needs all five numbers
    // together. A click used to pin those five in a boxed panel elsewhere
    // on the card; that panel read as a second, unrelated block bolted on
    // beside the chart it was describing. Pinning now draws instead: five
    // short arrows sprouting straight from that shape's own vertices out
    // to a label and value at each axis, in the same spot the plain axis
    // name sat a moment ago - a mind-map reading of the one shape, not a
    // separate card, and nothing else on the page changes size to fit it.
    var pinned = null;

    function renderDetail(i) {
      while (callouts.firstChild) { callouts.removeChild(callouts.firstChild); }
      if (i === null) { labels.style.display = ''; return; }
      labels.style.display = 'none';
      var c = candidates[i];
      metrics.forEach(function (m, mi) {
        var v = c.values[m.key] || 0;
        var dot = point(mi, n, v);
        var lead = leaderPoint(mi);
        var lab = labelAnchor(mi);
        var g = node('g', {
          class: 'radar-callout radar-c' + i, tabindex: '0', role: 'img',
          'aria-label': detailText(c, m),
        });
        g.appendChild(node('title', {}, detailText(c, m)));
        // The arrow stops at LEADER_R, short of where the text sits at
        // TEXT_R - the two used to be the same point, so the arrowhead
        // landed inside the gap between the label and value lines.
        g.appendChild(node('line', {
          x1: dot[0], y1: dot[1], x2: lead[0], y2: lead[1],
          class: 'radar-callout-line', 'marker-end': 'url(#radar-arrow-' + i + ')',
        }));
        g.appendChild(node('text', {
          x: lab.x, y: lab.y - 8, class: 'radar-callout-label',
          'text-anchor': lab.anchor,
        }, m.label));
        // Value only, no note - the note is still one hover away on the dot
        // itself (or the readout line), and a bullet is meant to be read in
        // one glance, not carry every caveat with it.
        //
        // Responsibilities can hold up to three duty names at once
        // ("Penalties, free kicks, corners") - wider than the room this
        // axis has before the chart's own edge clips it (it sits fixed in
        // the narrow upper-left of the pentagon). One duty per stacked
        // line, rather than one long comma-joined string, keeps every
        // combination inside the available width regardless of angle.
        if (m.key === 'responsibility') {
          var valText = node('text', {
            x: lab.x, y: lab.y + 12, class: 'radar-callout-value',
            'text-anchor': lab.anchor,
          });
          // dy 13 (less than the 17px value font-size itself) read as
          // cramped with more than one line - bumped past the font-size
          // for real breathing room between duties.
          c.responsibility_lines.forEach(function (line, li) {
            valText.appendChild(node('tspan', { x: lab.x, dy: li === 0 ? 0 : 19 }, line));
          });
          g.appendChild(valText);
        } else {
          g.appendChild(node('text', {
            x: lab.x, y: lab.y + 12, class: 'radar-callout-value',
            'text-anchor': lab.anchor,
          }, displayValue(c, m)));
        }
        g.addEventListener('mouseover', function () { setReadout(detailText(c, m)); });
        g.addEventListener('mouseout', function () { setReadout(pinned === null ? null : summaryText(candidates[pinned])); });
        g.addEventListener('focus', function () { setReadout(detailText(c, m)); });
        callouts.appendChild(g);
      });
    }

    legendItems.forEach(function (li) {
      var i = Number(li.getAttribute('data-i'));
      var c = candidates[i];
      li.addEventListener('mouseenter', function () { setActive(i); setReadout(summaryText(c)); });
      li.addEventListener('mouseleave', function () {
        setActive(pinned); setReadout(pinned === null ? null : summaryText(candidates[pinned]));
      });
      li.addEventListener('focus', function () { setActive(i); setReadout(summaryText(c)); });
      li.addEventListener('blur', function () {
        setActive(pinned); setReadout(pinned === null ? null : summaryText(candidates[pinned]));
      });
      function toggle() {
        pinned = pinned === i ? null : i;
        legendItems.forEach(function (o) {
          o.setAttribute('aria-pressed', String(Number(o.getAttribute('data-i')) === pinned));
        });
        setActive(pinned);
        renderDetail(pinned);
      }
      li.addEventListener('click', toggle);
      li.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggle(); }
      });
    });
  });
})();
