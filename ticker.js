// Fixture outlook pagination, drawn in the browser.
//
// Twenty clubs is too many to show at once without either a scrollbar or a
// wall of a table, so this pages through FIXTURE_PAGE_SIZE rows at a time
// instead - hiding/showing <tr> elements already in the DOM, not fetching
// or re-rendering anything. Sorting (the generic click-a-header behaviour
// in the page's main script) reorders those same rows in place, so a sort
// always resets the page back to the first one afterward - otherwise the
// visible eight would be whatever rows happened to land in the old page
// slot, which no longer matches what the header claims it just sorted.
(function () {
  var PAGE_SIZE = 8;

  document.querySelectorAll('table.fxtable[data-paged]').forEach(function (tbl) {
    var card = tbl.closest('.card');
    var nav = card ? card.querySelector('.fxnav') : null;
    var body = tbl.tBodies[0];
    if (!body) { return; }
    var prevBtn = nav ? nav.querySelector('[data-dir="-1"]') : null;
    var nextBtn = nav ? nav.querySelector('[data-dir="1"]') : null;
    var indicator = nav ? nav.querySelector('.fxnav-pos') : null;
    var page = 0;

    function pageCount() {
      return Math.max(1, Math.ceil(body.rows.length / PAGE_SIZE));
    }

    function render() {
      var rows = Array.prototype.slice.call(body.rows);
      var count = pageCount();
      page = Math.max(0, Math.min(page, count - 1));
      rows.forEach(function (r, i) {
        var onPage = i >= page * PAGE_SIZE && i < (page + 1) * PAGE_SIZE;
        if (onPage) { r.removeAttribute('hidden'); } else { r.setAttribute('hidden', ''); }
      });
      if (indicator) { indicator.textContent = (page + 1) + ' of ' + count; }
      if (prevBtn) { prevBtn.disabled = page === 0; }
      if (nextBtn) { nextBtn.disabled = page >= count - 1; }
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', function () { page -= 1; render(); });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () { page += 1; render(); });
    }

    // Attached after the generic sort listener (this script loads later in
    // the page), so by the time this fires the rows are already reordered
    // and resetting to page one shows the true new top of the list.
    tbl.querySelectorAll('th.sortable').forEach(function (th) {
      th.addEventListener('click', function () { page = 0; render(); });
      th.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') { page = 0; render(); }
      });
    });

    render();
  });
})();

// Fixture outlook controls: the Games selector and the Target fixtures
// toggle. Both act on cells already in the DOM (see ticker.py's
// data-score/fxc-target) rather than fetching or re-rendering anything, the
// same "hide/relabel what's already there" approach pagination above uses.
(function () {
  // Mirrors ticker.py's SCALE/PREMIUM_RATING exactly, so a recomputed
  // average never reads a different colour than the same value would have
  // been given at build time.
  var SCALE = [
    [2.0, '#a4133c', '#ffffff'],
    [4.0, '#f4845f', '#40190e'],
    [6.0, '#eae7ec', '#37003c'],
    [8.0, '#7ac9a0', '#0d3b26'],
    [10.1, '#17876a', '#ffffff']
  ];
  var PREMIUM_RATING = 9.0;

  function toneFor(score) {
    for (var i = 0; i < SCALE.length; i++) {
      if (score < SCALE[i][0]) { return SCALE[i]; }
    }
    return SCALE[SCALE.length - 1];
  }

  function paintAvg(span, score) {
    if (score > PREMIUM_RATING) {
      span.className = 'fxavg fx-premium';
      span.style.background = '';
      span.style.color = '';
    } else {
      var t = toneFor(score);
      span.className = 'fxavg';
      span.style.background = t[1];
      span.style.color = t[2];
    }
  }

  function recomputeGames(tbl, n) {
    tbl.dataset.games = n;
    Array.prototype.forEach.call(tbl.tBodies[0].rows, function (row) {
      var cells = Array.prototype.slice.call(row.querySelectorAll('.fxc'), 0, n);
      if (!cells.length) { return; }
      var sum = cells.reduce(function (s, c) {
        return s + (parseFloat(c.dataset.score) || 0);
      }, 0);
      var avg = sum / cells.length;
      var avgCell = row.querySelector('.fxavg-cell');
      var avgSpan = row.querySelector('.fxavg');
      if (avgCell) { avgCell.dataset.v = avg.toFixed(2); }
      if (avgSpan) {
        avgSpan.textContent = avg.toFixed(1);
        paintAvg(avgSpan, avg);
      }
    });
  }

  document.querySelectorAll('table.fxtable').forEach(function (tbl) {
    var card = tbl.closest('.card');
    if (!card) { return; }

    var select = card.querySelector('.fx-games');
    if (select) {
      select.value = tbl.dataset.games;
      select.addEventListener('change', function () {
        recomputeGames(tbl, parseInt(select.value, 10) || 1);
      });
    }

    var toggle = card.querySelector('.fx-target');
    if (toggle) {
      toggle.addEventListener('click', function () {
        var on = toggle.getAttribute('aria-pressed') !== 'true';
        toggle.setAttribute('aria-pressed', String(on));
        tbl.classList.toggle('target-on', on);
      });
    }
  });
})();
