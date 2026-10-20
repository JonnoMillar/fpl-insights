(function(){
  // Squad by gameweek: one pitch per week of the transfer plan. Keyboard
  // movement between the week tabs comes from the shared tablist handler in
  // dashboard.js, which clicks the next button; this only shows its panel.
  document.querySelectorAll('.plan-card').forEach(function(card){
    var buttons = Array.from(card.querySelectorAll('.plan-gwbtn'));
    function show(gw){
      buttons.forEach(function(b){
        var on = b.dataset.panel === 'plan-pitch-' + gw;
        b.setAttribute('aria-selected', String(on));
        b.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(b.dataset.panel);
        if (panel) panel.hidden = !on;
      });
    }
    buttons.forEach(function(b){
      b.addEventListener('click', function(){ show(b.dataset.panel.replace('plan-pitch-', '')); });
    });
    // "GWn squad" beside a week in the move list opens that week's pitch.
    card.querySelectorAll('.plan-view').forEach(function(btn){
      btn.addEventListener('click', function(){
        // Through the tab itself, so the tab bar's indicator follows.
        var tab = card.querySelector('.plan-gwbtn[data-panel="plan-pitch-' + btn.dataset.showGw + '"]');
        if (!tab) return;
        tab.click();
        // Below the sticky header, which would otherwise cover the tabs.
        var bar = document.querySelector('.topbar');
        var top = bar ? bar.getBoundingClientRect().bottom : 0;
        var tabs = card.querySelector('.plan-gwtabs');
        window.scrollTo({top: tabs.getBoundingClientRect().top + window.scrollY - top - 8});
        tab.focus({preventScroll: true});
      });
    });
  });
})();
