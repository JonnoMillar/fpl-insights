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
