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
(function () {
  var panel = document.getElementById('p-scout');
  if (!panel) { return; }

  var pools = {};
  panel.querySelectorAll('.scout-data').forEach(function (holder) {
    var pos = holder.dataset.pos;
    try { pools[pos] = JSON.parse(holder.textContent); }
    catch (e) { /* malformed island - that position's lab stays empty */ }
  });

  var drawn = false;

  function draw() {
    if (drawn) { return; }
    drawn = true;
    // Level 1/2/3 rendering lands in later phases of the plan; this phase
    // only proves the data reaches the browser intact.
  }

  panel.addEventListener('panel:shown', draw);
  if (!panel.hidden) { draw(); }
})();
