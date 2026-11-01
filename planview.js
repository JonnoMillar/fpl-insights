(function(){
  // The plan's week tiles: one stage panel per gameweek, revealed on click
  // rather than scrolled to. Keyboard movement between tiles comes from the
  // shared tablist handler in dashboard.js, which clicks the next tile.
  document.querySelectorAll('.plan-card').forEach(function(card){
    var tiles = Array.from(card.querySelectorAll('.wk'));
    function show(tile){
      tiles.forEach(function(t){
        var on = t === tile;
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.dataset.panel);
        if (!panel) return;
        panel.hidden = !on;
        // Restart the rise-in each time a week is opened.
        panel.classList.remove('enter');
        if (on) { void panel.offsetWidth; panel.classList.add('enter'); }
      });
    }
    tiles.forEach(function(t){
      t.addEventListener('click', function(){ show(t); });
    });
  });

  // Other transfer options: a deck of cards fanned behind the current one.
  // Drag past 70px (60px on a phone), use the arrows, the arrow keys, or
  // pick from the ranked list. Reduced motion keeps the jumps, drops the travel.
  document.querySelectorAll('.deck-panel').forEach(function(panel){
    var deck = panel.querySelector('.deck');
    var cards = Array.from(panel.querySelectorAll('.deck-card'));
    var idx = Array.from(panel.querySelectorAll('.deck-idx'));
    var pos = panel.querySelector('.deck-pos b');
    var prev = panel.querySelector('[data-step="-1"]');
    var next = panel.querySelector('[data-step="1"]');
    var n = cards.length, i = 0, dx = 0, sx = 0, dragging = false;
    function lay(){
      cards.forEach(function(c, k){
        var rel = k - i, tf, op = 1;
        if (rel < 0) { tf = 'translateX(-125%) rotate(-12deg)'; op = 0; }
        else if (rel === 0) { tf = 'translateX(' + dx + 'px) rotate(' + (dx * 0.05).toFixed(2) + 'deg)'; }
        else {
          var r = Math.min(rel, 3);
          tf = 'translate(' + (r * 22) + 'px,' + (r * -8) + 'px) rotate(' + (r * 4) + 'deg) scale(' + (1 - r * 0.04).toFixed(2) + ')';
          if (rel > 3) op = 0;
        }
        c.style.transform = tf;
        c.style.opacity = op;
        c.style.zIndex = 50 - Math.abs(rel);
        c.style.transition = dragging && rel === 0 ? 'none' : '';
        c.setAttribute('aria-hidden', String(rel !== 0));
        // A dismissed card is invisible but flung over the buttons; it must
        // not catch their clicks. Only the top card takes the pointer.
        c.style.pointerEvents = rel === 0 ? '' : 'none';
      });
      idx.forEach(function(b, k){ b.setAttribute('aria-current', String(k === i)); });
      if (pos) pos.textContent = i + 1;
      if (prev) prev.disabled = i === 0;
      if (next) next.disabled = i === n - 1;
    }
    function go(k){ i = Math.max(0, Math.min(n - 1, k)); dx = 0; dragging = false; lay(); }
    if (prev) prev.addEventListener('click', function(){ go(i - 1); });
    if (next) next.addEventListener('click', function(){ go(i + 1); });
    idx.forEach(function(b, k){ b.addEventListener('click', function(){ go(k); }); });
    deck.addEventListener('keydown', function(ev){
      if (ev.key === 'ArrowRight') { ev.preventDefault(); go(i + 1); }
      if (ev.key === 'ArrowLeft') { ev.preventDefault(); go(i - 1); }
    });
    deck.addEventListener('pointerdown', function(ev){
      if (ev.button !== 0) return;
      sx = ev.clientX; dragging = true; dx = 0;
      deck.classList.add('dragging');
      deck.setPointerCapture(ev.pointerId);
    });
    deck.addEventListener('pointermove', function(ev){
      if (!dragging) return;
      dx = ev.clientX - sx; lay();
    });
    function end(){
      if (!dragging) return;
      deck.classList.remove('dragging');
      var limit = window.matchMedia('(max-width:700px)').matches ? 60 : 70;
      if (dx < -limit) go(i + 1); else if (dx > limit) go(i - 1); else go(i);
    }
    deck.addEventListener('pointerup', end);
    deck.addEventListener('pointercancel', end);
    lay();
  });
})();
