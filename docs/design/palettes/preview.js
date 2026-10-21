/* Disposable Squad colour study. The production renderer is unchanged. */
(function () {
  'use strict';
  const palettes = [
    {
      id: 'touchline', name: 'Touchline',
      note: 'Forest and mint. Mint leads you to the next decision; purple stays in the FPL masthead.',
      swatches: ['#193e32', '#00ed87', '#37003c'],
      tokens: {ground:'#edf1ee', surface:'#fcfdfb', soft:'#e0e8e1', context:'#d5e2d9', ink:'#192e25', muted:'#4c6156', line:'#81998a', divider:'#c4d1c7', anchor:'#193e32', 'anchor-muted':'#cee4d6', accent:'#00ed87', 'accent-ink':'#00683b', 'accent-wash':'#dcfae9', 'action-ink':'#092c20', recent:'#e0e8e1', upcoming:'#193e32', 'upcoming-ink':'#f1fcf4', 'upcoming-muted':'#c4dfce', bar:'#37003c', pitchA:'#28714f', pitchB:'#226445', bench:'#173e2d', player:'#f7f9ed', shirt:'#dfe7d9', 'player-ink':'#192e25'}
    },
    {
      id: 'cyan', name: 'Cyan pulse',
      note: 'Navy and cyan. Cyan marks the next action and forecast; green is reserved for positive changes.',
      swatches: ['#152d49', '#05d8ed', '#37003c'],
      tokens: {ground:'#eaf0f5', surface:'#fcfdff', soft:'#dce6ee', context:'#cddde9', ink:'#192b40', muted:'#4a6076', line:'#829aaf', divider:'#c2d0dc', anchor:'#152d49', 'anchor-muted':'#ccdeed', accent:'#05d8ed', 'accent-ink':'#006575', 'accent-wash':'#d8f9fc', 'action-ink':'#082d3b', recent:'#dce6ee', upcoming:'#152d49', 'upcoming-ink':'#f2f9ff', 'upcoming-muted':'#c6d9e9', bar:'#291135', pitchA:'#217360', pitchB:'#1a6554', bench:'#123d36', player:'#f4f9fc', shirt:'#dce6ec', 'player-ink':'#192b40'}
    },
    {
      id: 'pink', name: 'Pink accent',
      note: 'Charcoal and FPL pink. Pink singles out the next decision; the pitch and transfer gains keep their greens.',
      swatches: ['#302c36', '#ff7cba', '#13774f'],
      tokens: {ground:'#f2eff1', surface:'#fffcfd', soft:'#e8e1e6', context:'#e2d7df', ink:'#302731', muted:'#685462', line:'#a18c9a', divider:'#d6c9d1', anchor:'#302c36', 'anchor-muted':'#e3d4e0', accent:'#ff7cba', 'accent-ink':'#92325e', 'accent-wash':'#ffe5f0', 'action-ink':'#3d1528', recent:'#e8e1e6', upcoming:'#302c36', 'upcoming-ink':'#fff7fb', 'upcoming-muted':'#e3d3dd', bar:'#302039', pitchA:'#277252', pitchB:'#206347', bench:'#173e30', player:'#fff8f4', shirt:'#eadfe5', 'player-ink':'#302731'}
    },
    {
      id: 'lime', name: 'Lime press',
      note: 'Olive and electric lime. Lime pulls the eye toward the upcoming week; a small purple masthead keeps the FPL cue.',
      swatches: ['#303c28', '#d4f64a', '#37003c'],
      tokens: {ground:'#eff1e8', surface:'#fdfef8', soft:'#e1e7d5', context:'#d8e0c7', ink:'#293222', muted:'#57624b', line:'#939f7e', divider:'#cbd3ba', anchor:'#303c28', 'anchor-muted':'#dde6cb', accent:'#d4f64a', 'accent-ink':'#536600', 'accent-wash':'#eff9d1', 'action-ink':'#293400', recent:'#e1e7d5', upcoming:'#303c28', 'upcoming-ink':'#f7fbe9', 'upcoming-muted':'#d6e0c4', bar:'#32133c', pitchA:'#4a7040', pitchB:'#406237', bench:'#293f26', player:'#fffdeb', shirt:'#e5e7cd', 'player-ink':'#293222'}
    },
    {
      id: 'floodlights', name: 'Floodlights',
      note: 'A dark matchday view. FPL mint lights up the next action and projection; pale player cards keep the shirts and figures clear.',
      swatches: ['#10232c', '#00ed87', '#b9e1ec'],
      tokens: {ground:'#10232c', surface:'#1b333d', soft:'#243e47', context:'#2b4851', ink:'#edf5f3', muted:'#bbd0d2', line:'#587780', divider:'#42616b', anchor:'#081b24', 'anchor-muted':'#c2d9dd', accent:'#00ed87', 'accent-ink':'#78efb4', 'accent-wash':'#214a3a', 'action-ink':'#082d20', recent:'#213b45', upcoming:'#123c2e', 'upcoming-ink':'#f1fcf4', 'upcoming-muted':'#c1decf', bar:'#20152d', pitchA:'#235b47', pitchB:'#1b4e3c', bench:'#12362b', player:'#edf5eb', shirt:'#d3e2d5', 'player-ink':'#173126'}
    }
  ];
  const root = document.documentElement;
  const choices = document.querySelector('.palette-options');
  const description = document.querySelector('.palette-description');
  function choose(palette) {
    Object.entries(palette.tokens).forEach(([key, value]) => root.style.setProperty('--study-' + key, value));
    root.dataset.palette = palette.id;
    choices.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.palette === palette.id)));
    description.textContent = palette.note;
    history.replaceState(null, '', '#' + palette.id);
  }
  palettes.forEach(palette => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.palette = palette.id;
    button.setAttribute('aria-pressed', 'false');
    const swatches = document.createElement('span');
    swatches.className = 'palette-swatches';
    swatches.setAttribute('aria-hidden', 'true');
    palette.swatches.forEach(colour => {
      const swatch = document.createElement('i');
      swatch.style.background = colour;
      swatches.append(swatch);
    });
    button.append(swatches, document.createTextNode(palette.name));
    button.addEventListener('click', () => choose(palette));
    choices.append(button);
  });
  choose(palettes.find(p => p.id === location.hash.slice(1)) || palettes[0]);
  document.querySelector('.pkbtn[data-view="pk"]').click();
})();
