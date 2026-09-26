
(function(){
  // The "i" beside a title reveals that card's explanation. Delegated once
  // rather than wired per-card, since the same markup shape (title, button,
  // then the text it reveals as the next sibling in a .card-head or .find)
  // repeats everywhere on the page.
  document.addEventListener('click', function(ev){
    var btn = ev.target.closest('.infobtn');
    if (!btn) return;
    var scope = btn.closest('.card-head, .find');
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
      // Panels differ in height. Without this, switching from a long panel to
      // a short one leaves you scrolled past the end of the new one, staring
      // at empty background.
      var bar=t.parentNode;
      if(bar.getBoundingClientRect().top < 0) bar.scrollIntoView({block:'start'});
      buildRail();
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
      if(!ch.id) ch.id='ch-'+(panel.id||'p')+'-'+i;
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
    var cut=110, current=railTargets[0];
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
        var sel = group.querySelector('.statsel');
        if (sel) { sel.hidden = view === 'pk'; }
        var epb = group.querySelector('.epbtn');
        if (epb) { epb.hidden = view !== 'pk'; }
        // The hero's one-liner belongs to the view, not to the card: on
        // Pick team it should be looking at the week ahead rather than
        // reporting the one just gone. It lives above the tabs, outside
        // this card, so it is switched separately.
        // Only two lines exist - looking forward on Pick team, looking back
        // on either of the other two - so they key off the same collapse
        // the panels use rather than off all three view names.
        var heroKey = view === 'pk' ? 'pk' : 'back';
        document.querySelectorAll('.hero [data-pkview]').forEach(function(p){
          p.hidden = p.dataset.pkview !== heroKey;
        });
        points(view);
      });
    });
  });

  // Predicted points: the eleven shrink into a column and the bars extend
  // across the space that opens beside them.
  document.querySelectorAll('.epbtn').forEach(function (btn) {
    var stage = btn.closest('.card').querySelector('.pkstage');
    if (!stage) { btn.hidden = true; return; }
    var side = stage.querySelector('.epside');
    var reduce = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    btn.addEventListener('click', function () {
      var on = btn.getAttribute('aria-pressed') !== 'true';
      btn.setAttribute('aria-pressed', String(on));
      stage.classList.toggle('ep-on', on);
      if (side) { side.setAttribute('aria-hidden', String(!on)); }
      if (!on || reduce || !side) { return; }
      // Run the bars out only once the column has finished opening,
      // otherwise they animate to a width that is still changing.
      window.setTimeout(function () {
        side.querySelectorAll('.epcr .epbar').forEach(function (bar, i) {
          if (!bar.animate) { return; }
          bar.animate(
            [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
            { duration: 340, delay: i * 45, easing: 'cubic-bezier(.2,.7,.3,1)' }
          );
        });
      }, 260);
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
