
(function(){
  var snapshot = document.querySelector('[data-generated]');
  function markFreshness() {
    if (!snapshot) return;
    var generated = Date.parse(snapshot.dataset.generated);
    if (!Number.isFinite(generated)) return;
    var age = Math.max(0, Math.floor((Date.now() - generated) / 60000));
    var stale = age >= 360;
    snapshot.classList.toggle('data-warning', stale);
    var ageLabel = snapshot.querySelector('.data-age') || snapshot;
    ageLabel.textContent = (stale ? 'Update overdue. ' : 'Snapshot: ') +
      (age < 60 ? age + ' minutes' : Math.floor(age / 60) + ' hours') +
      ' old.';
  }
  markFreshness();
  window.setInterval(markFreshness, 60000);

  // Reuse the Scout tab's automatic keyboard activation for the other views.
  document.querySelectorAll('[role="tablist"]:not(.scoutpos)').forEach(function(group, gi) {
    var buttons = Array.from(group.querySelectorAll(':scope > [role="tab"]'));
    if (!buttons.length) return;
    buttons.forEach(function(b, bi) {
      b.id = b.id || 'view-tab-' + gi + '-' + bi;
      var target = b.dataset.panel ? document.getElementById(b.dataset.panel) : null;
      var card = b.closest('.card');
      if (!target && card && b.dataset.view) {
        target = card.querySelector('.pkpanel[data-view="' + (b.dataset.view === 'pk' ? 'pk' : 'ov') + '"]');
      }
      if (!target && card && b.dataset.lcview) target = card.querySelector('.lcpanel[data-lcview="' + b.dataset.lcview + '"]');
      if (!target && card && b.dataset.rv) target = card.querySelector('.rvpanel[data-rv="' + b.dataset.rv + '"]');
      if (target) {
        target.id = target.id || 'view-panel-' + gi + '-' + bi;
        target.setAttribute('role', 'tabpanel');
        b.setAttribute('aria-controls', target.id);
      }
    });
    function sync() {
      buttons.forEach(function(b) {
        var selected = b.getAttribute('aria-selected') === 'true';
        b.tabIndex = selected ? 0 : -1;
        var target = document.getElementById(b.getAttribute('aria-controls'));
        if (target && selected) target.setAttribute('aria-labelledby', b.id);
      });
    }
    group.addEventListener('click', sync);
    group.addEventListener('keydown', function(ev) {
      if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(ev.key)) return;
      var i = buttons.indexOf(ev.target);
      if (i < 0) return;
      ev.preventDefault();
      i = ev.key === 'Home' ? 0 : ev.key === 'End' ? buttons.length - 1 :
        (i + (ev.key === 'ArrowRight' || ev.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
      buttons[i].focus();
      buttons[i].click();
    });
    sync();
  });
  // The "i" beside a title reveals that card's explanation. Delegated once
  // rather than wired per-card, since the same markup shape (title, button,
  // then the text it reveals as the next sibling in a .card-head or .find)
  // repeats everywhere on the page.
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.infobtn');
    if (!btn) return;
    var scope = btn.closest('.card-head, .subhead, .find');
    if (!scope) return;
    var show = btn.getAttribute('aria-expanded') !== 'true';
    scope.querySelectorAll(':scope > .sub, :scope > .note').forEach(function(t){
      t.hidden = !show;
    });
    btn.setAttribute('aria-expanded', String(show));
    // Some of these buttons live inside a <summary> - without this, opening
    // the explanation also springs the whole collapsible card open.
    if (btn.closest('summary')) { ev.preventDefault(); ev.stopPropagation(); }
  });

  // --- the tab bar indicator ---------------------------------------------
  // One rule per bar, positioned from the selected button's own geometry, so
  // the bars do not each need their own script and a bar added later is
  // picked up for free. Measured rather than assumed: the labels are words,
  // and their widths are whatever the font makes them.
  function markTabbar(bar){
    // Direct children only, and never the predicted-points toggle: .pkview
    // holds the three view tabs but also a nested group of figure buttons
    // and that toggle, all of which carry aria-pressed. A descendant query
    // would let the rule latch onto one of those.
    var sel = bar.querySelector(
      ':scope > button:not(.epbtn)[aria-selected="true"],' +
      ':scope > button:not(.epbtn)[aria-pressed="true"]');
    if (!sel) { bar.style.setProperty('--tab-w', '0'); return; }
    var b = bar.getBoundingClientRect(), r = sel.getBoundingClientRect();
    // A bar inside a hidden panel measures zero. Leave its last good
    // position alone rather than collapsing the rule to nothing, so it does
    // not visibly snap back when the panel is shown again.
    if (!r.width) return;
    bar.style.setProperty('--tab-x', (r.left - b.left + bar.scrollLeft) + 'px');
    bar.style.setProperty('--tab-w', String(r.width));
  }
  function markTabbars(){ document.querySelectorAll('.tabbar').forEach(markTabbar); }

  // Delegated, and synchronous: this runs in the bubble phase, after the
  // button's own handler has moved aria-selected, so the geometry it reads
  // is already the new one. No frame is requested - a deferred callback does
  // not run at all where frames are paused.
  document.addEventListener('click', function(ev){
    if (ev.target.closest('.tabbar > button')) markTabbars();
  });
  window.addEventListener('resize', markTabbars);
  markTabbars();
  // Web fonts land after first paint and change every label's width.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(markTabbars);
  }

  // Predicted line-ups: full squad, XI or bench answer different questions
  // about the same fifteen, so one figure switches between them rather than
  // showing three at once.
  document.querySelectorAll('.lcnav').forEach(function(nav){
    var card = nav.closest('.lccard');
    var panels = Array.from(card.querySelectorAll('.lcpanel'));
    var buttons = Array.from(nav.querySelectorAll('.lcbtn'));
    buttons.forEach(function(b){
      b.addEventListener('click', function(){
        buttons.forEach(function(o){
          o.setAttribute('aria-selected', String(o === b));
        });
        panels.forEach(function(p){
          p.hidden = p.dataset.lcview !== b.dataset.lcview;
        });
      });
    });
  });

  // Scoring against you: this week vs the last few weeks summed.
  document.querySelectorAll('.rvtabs').forEach(function(tabs){
    var card = tabs.closest('.card');
    var buttons = tabs.querySelectorAll('.rvtab');
    var panels = card.querySelectorAll('.rvpanel');
    buttons.forEach(function(b){
      b.addEventListener('click', function(){
        buttons.forEach(function(o){ o.setAttribute('aria-selected', String(o===b)); });
        panels.forEach(function(p){ p.hidden = p.dataset.rv !== b.dataset.rv; });
      });
    });
  });

  var tabs=document.querySelectorAll('.tab');
  tabs.forEach(function(t){
    t.addEventListener('click',function(){
      tabs.forEach(function(o){
        o.setAttribute('aria-selected', String(o===t));
        var p=document.getElementById(o.dataset.panel);
        if(p) p.hidden = (o!==t);
      });
      buildRail();
      // Persistent tabs should open the next section at its beginning.
      window.scrollTo(0, 0);
      // A tab's own panel may have deferred its first render until it is
      // actually looked at - the Scout tab's per-match history for the
      // whole league is not worth laying out before anyone opens it. This
      // fires every time the tab is selected; a listener that only wants
      // the first look removes itself after drawing.
      var shown=document.getElementById(t.dataset.panel);
      if(shown) shown.dispatchEvent(new Event('panel:shown'));
    });
  });

  // --- the chapter rail ---------------------------------------------------
  // Built from whichever chapters the open tab has rather than from a fixed
  // list, so it can never offer a section that is not on screen. A tab with
  // one chapter gets no rail at all - a nav of length one is furniture.
  var railWrap=document.querySelector('.railwrap');
  var rail=document.querySelector('.rail');
  var railTargets=[];
  var chapterSeq=0;

  function buildRail(){
    if(!rail) return;
    var panel=document.querySelector('.panel:not([hidden])');
    // Chapters inside a hidden view (the Scout tab's other positions) are
    // not on screen, so they are not offered either.
    var chapters=panel ? Array.prototype.filter.call(
      panel.querySelectorAll('.chapter'),
      function(ch){ return !ch.closest('[hidden]'); }) : [];
    rail.textContent='';
    railTargets=[];
    if(chapters.length < 2){ railWrap.hidden=true; return; }
    railWrap.hidden=false;
    chapters.forEach(function(ch,i){
      var h=ch.querySelector('h2');
      if(!h) return;
      // A running count, not the index: the index is within the visible
      // chapters only, so each Scout position handed its own chapters the
      // same three ids.
      if(!ch.id) ch.id='ch-'+(panel.id||'p')+'-'+(++chapterSeq);
      var b=document.createElement('button');
      b.type='button';
      b.className='railbtn';
      b.textContent=h.textContent.trim();
      b.addEventListener('click',function(){
        // An explicit position rather than scrollIntoView, and no smooth:
        // the sticky bar's height is the offset, and it is measured now
        // rather than assumed, because the bar grows a second row the
        // moment this rail exists.
        var bar=document.querySelector('.topbar');
        var off=(bar ? bar.getBoundingClientRect().height : 0) + 8;
        window.scrollTo(0, ch.getBoundingClientRect().top + window.scrollY - off);
        markRail();
      });
      rail.appendChild(b);
      railTargets.push({el:ch, btn:b});
    });
    markRail();
  }

  // Which chapter you are actually in: the last one whose top has passed
  // under the bar. Cheaper and steadier than an observer per section, and
  // it agrees with what is under the heading rather than what is centred.
  function markRail(){
    if(!railTargets.length) return;
    var cut=document.querySelector('.topbar').getBoundingClientRect().height + 8, current=railTargets[0];
    railTargets.forEach(function(t){
      if(t.el.getBoundingClientRect().top <= cut) current=t;
    });
    railTargets.forEach(function(t){
      t.btn.setAttribute('aria-current', String(t===current));
    });
  }

  // Called straight from the scroll event rather than deferred into a frame.
  // The rAF-throttled version had a real failure mode: it raised a "already
  // queued" flag before asking for the frame, so anywhere frames are paused -
  // a background tab, a hidden view - the flag was set, the callback never
  // ran to clear it, and every later scroll was dropped for the life of the
  // page. markRail is four getBoundingClientRect calls against a list that
  // is at most four long; it does not need deferring.
  window.addEventListener('scroll', markRail, {passive:true});
  // A view switch inside a tab (Scout's position control) swaps which
  // chapters exist without a tab change, so it asks for a rebuild.
  document.addEventListener('rail:rebuild', buildRail);
  buildRail();

  document.querySelectorAll('[data-dashboard-jump]').forEach(function(link){
    link.addEventListener('click', function(ev){
      var target = document.getElementById(link.hash.slice(1));
      if (!target) return;
      ev.preventDefault();
      var panel = target.closest('.panel');
      var tab = panel && document.querySelector('.tab[data-panel="'+panel.id+'"]');
      if (tab) tab.click();
      if (target.tagName === 'DETAILS') target.open = true;
      var details = target.closest('details');
      if (details) details.open = true;
      target.setAttribute('tabindex', '-1');
      target.focus({preventScroll:true});
      var offset = document.querySelector('.topbar').getBoundingClientRect().height + 16;
      window.scrollTo(0, target.getBoundingClientRect().top + window.scrollY - offset);
    });
  });

  // Starting XI: overview vs pick-team pitch. Same swap as the tabs above,
  // scoped to whichever card the clicked button lives in, since the page
  // only has one of these but a second squad card could add one later.
  // "Gameweek" is not a third pitch - it is the overview pitch with the
  // first figure swapped. Rendering another eleven shirt cards to change
  // one number per card would have put the same images on the page a third
  // time, and this page is already better than a megabyte.
  document.querySelectorAll('.pkview').forEach(function(group){
    var btns = group.querySelectorAll('.pkbtn');
    var card = group.closest('.card');
    function points(view){
      var key = view === 'gw' ? 'ptsNow' : 'ptsSeason';
      card.querySelectorAll('.pkpanel[data-view="ov"] .pl').forEach(function(pl){
        var cell = pl.querySelector('.sc .p');
        if (cell && pl.dataset[key] !== undefined) { cell.textContent = pl.dataset[key]; }
      });
    }
    btns.forEach(function(b){
      b.addEventListener('click', function(){
        var view = b.dataset.view;
        btns.forEach(function(o){ o.setAttribute('aria-selected', String(o===b)); });
        // Overview and Gameweek share one panel, so the panel to show is the
        // view itself for 'pk' and the overview panel for either other.
        var panel = view === 'pk' ? 'pk' : 'ov';
        card.querySelectorAll('.pkpanel').forEach(function(p){
          p.hidden = p.dataset.view !== panel;
        });
        card.querySelectorAll('[data-pkview]').forEach(function(p){
          p.hidden = p.dataset.pkview !== view;
        });
        // The figure selector only means anything on the two views that
        // share the overview pitch; the predicted-points toggle only means
        // anything on the one that does not.
        var sel = card.querySelector('.statsel');
        if (sel) { sel.hidden = view === 'pk'; }
        var epb = card.querySelector('.epbtn');
        if (epb) { epb.hidden = view !== 'pk' || !card.querySelector('.pkstage .epside'); }
        points(view);
      });
    });
  });

  document.querySelectorAll('.lineup-toggle').forEach(function(btn){
    var overview = btn.closest('.squad-overview');
    var variants = overview.querySelector('.lineup-variants');
    var animations = [];
    btn.addEventListener('click', function(){
      var on = btn.getAttribute('aria-checked') !== 'true';
      animations.forEach(function(animation){ animation.cancel(); });
      animations = [];
      var oldPositions = {};
      variants.querySelectorAll(':scope > :not([hidden]) .pl').forEach(function(player){
        oldPositions[player.dataset.player] = player.getBoundingClientRect();
      });
      btn.setAttribute('aria-checked', String(on));
      overview.classList.toggle('preview-on', on);
      overview.querySelectorAll('[data-lineup]').forEach(function(panel){
        panel.hidden = panel.dataset.lineup !== (on ? 'transfers' : 'owned');
      });
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      variants.querySelectorAll(':scope > :not([hidden]) .pl').forEach(function(player){
        if (!player.animate) return;
        var old = oldPositions[player.dataset.player];
        var next = player.getBoundingClientRect();
        var frames = old ? [
          {transform:'translate(' + (old.left-next.left) + 'px,' + (old.top-next.top) + 'px)'},
          {transform:'translate(0,0)'}
        ] : [{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}];
        animations.push(player.animate(frames, {duration:260,easing:'cubic-bezier(.22,1,.36,1)'}));
      });
    });
  });

  // Keep both point breakdowns in sync within the reserved pitch area.
  document.querySelectorAll('.epbtn').forEach(function (btn) {
    var stages = Array.from(btn.closest('.card').querySelectorAll('.pkstage'));
    if (!stages.length) { btn.hidden = true; return; }
    btn.addEventListener('click', function () {
      var on = btn.getAttribute('aria-pressed') !== 'true';
      btn.setAttribute('aria-pressed', String(on));
      stages.forEach(function(stage){
        stage.classList.toggle('ep-on', on);
        var side = stage.querySelector('.epside');
        if (side) { side.setAttribute('aria-hidden', String(!on)); }
      });
    });
  });

  // Click a figure to bring it forward on every card at once.
  document.querySelectorAll('.statsel').forEach(function (group) {
    var btns = group.querySelectorAll('.stbtn');
    var wrap = group.closest('.card').querySelector('.ovwrap');
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        btns.forEach(function (o) {
          o.setAttribute('aria-pressed', String(o === b));
        });
        if (!wrap) { return; }
        wrap.classList.remove('emph-p', 'emph-g', 'emph-x');
        wrap.classList.add('emph-' + b.dataset.stat);
      });
    });
  });

  document.querySelectorAll('table[data-sortable]').forEach(function(tbl){
    tbl.querySelectorAll('th.sortable').forEach(function(th,i){
      var idx=Array.prototype.indexOf.call(th.parentNode.children,th);
      th.setAttribute('tabindex','0');
      function go(){
        var dir = th.getAttribute('aria-sort')==='descending' ? 1 : -1;
        tbl.querySelectorAll('th').forEach(function(o){o.removeAttribute('aria-sort')});
        th.setAttribute('aria-sort', dir<0 ? 'descending' : 'ascending');
        var body=tbl.tBodies[0];
        var rows=Array.prototype.slice.call(body.rows);
        rows.sort(function(a,b){
          var x=a.cells[idx], y=b.cells[idx];
          var xv=x?(x.dataset.v!==undefined?x.dataset.v:x.textContent):'';
          var yv=y?(y.dataset.v!==undefined?y.dataset.v:y.textContent):'';
          var xn=parseFloat(xv), yn=parseFloat(yv);
          if(!isNaN(xn)&&!isNaN(yn)) return (xn-yn)*dir;
          return String(xv).localeCompare(String(yv))*dir;
        });
        rows.forEach(function(r){body.appendChild(r)});
      }
      th.addEventListener('click',go);
      th.addEventListener('keydown',function(ev){
        if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();go();}
      });
    });
  });
})();
