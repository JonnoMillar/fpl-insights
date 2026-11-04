// The player profile: one dialog for every player face on the page.
//
// Any element carrying data-player="<id>" opens it - portraits, shirt cards,
// table names, Scout rows and points - through one delegated listener. The
// records come from the profile-data island (playerprofile.py), which holds
// exactly the players the page shows. Figures, not sentences: the season
// tiles read against the player's own position, the fixtures and tiles use
// the page's night-grey-paper-green ramp, and every value is printed, so no
// colour ever carries a reading alone.
(function () {
  var holder = document.getElementById('profile-data');
  var dlg = document.querySelector('dialog.pf');
  if (!holder || !dlg) { return; }
  var store = JSON.parse(holder.textContent);
  var body = dlg.querySelector('.pf-body');
  var opener = null;
  var PHOTO_URL = 'https://resources.premierleague.com/premierleague25/photos/players/110x140/';
  // ticker.SCALE: night for the worst, deep green for the best.
  var RAMP = [['#16001a', '#fff'], ['#6e6474', '#fff'], ['#eeecef', '#16001a'],
              ['#00ff87', '#16001a'], ['#2fbf7a', '#16001a']];
  var PARTS = ['Goals', 'Assists', 'Clean sheet', 'Saves', 'Appearance', 'DefCon',
               'Bonus', 'Goals conceded', 'Cards'];
  var SET_PIECE = { penalties: 'Penalties', 'free-kicks': 'Free kicks', corners: 'Corners' };

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }
  function ico(name) { return '<span class="ico ico-' + name + '" aria-hidden="true"></span>'; }
  function tone(score10) { return RAMP[Math.max(0, Math.min(4, Math.floor(score10 / 2)))]; }
  function signed(v, dp) { return (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(dp); }
  function fmt(v, f) {
    if (v === null || v === undefined) { return '–'; }
    return f === 'pct' ? Math.round(v * 100) + '%' : Number(v).toFixed(+f);
  }
  function crest(tid, cls) {
    var t = store.teams[tid];
    if (!t) { return ''; }
    return t[1] ? '<img class="' + (cls || 'pf-crest') + '" src="' + t[1] + '" alt="' + esc(t[0]) + '">'
      : '<b>' + esc(t[0]) + '</b>';
  }
  function teamByShort(short) {
    for (var tid in store.teams) { if (store.teams[tid][0] === short) { return tid; } }
    return null;
  }
  function section(label, inner, extra) {
    return '<section class="pf-sec"><div class="pf-sechead"><span class="lab">' + label +
      '</span>' + (extra || '') + '</div>' + inner + '</section>';
  }

  // A face already on the page is the same cut-out; anyone else's comes
  // from the Premier League's own picture server, and a failed load leaves
  // the club crest standing in.
  function photo(id, p) {
    var face = document.querySelector('img[data-player="' + id + '"]');
    var src = face ? face.src : (p.cd ? PHOTO_URL + p.cd + '.png' : '');
    return '<div class="pf-photo">' + crest(p.t, 'pf-photo-crest') +
      (src ? '<img class="pf-cut" src="' + src + '" alt="" onerror="this.remove()">' : '') + '</div>';
  }

  function head(id, p) {
    var e = p.e;
    var meta = ['<b>£' + p.c.toFixed(1) + 'm</b>' + (p.pc ? ' <i>' + signed(p.pc, 1) + '</i>' : ''),
                '<b>' + p.o.toFixed(1) + '%</b> <i>owned</i>',
                '<b>' + (p.tr > 0 ? '+' : p.tr < 0 ? '−' : '') +
                  (Math.abs(p.tr) >= 1000 ? (Math.abs(p.tr) / 1000).toFixed(1) + 'k' : Math.abs(p.tr)) +
                  '</b> <i>this GW</i>'].map(function (m) { return '<span>' + m + '</span>'; });
    var duties = p.sp.map(function (s) {
      return '<span class="pf-duty" title="' + SET_PIECE[s[0]] + ' #' + s[1] + '">' + ico(s[0]) +
        '<b>' + s[1] + '</b><span class="vh">' + SET_PIECE[s[0]] + '</span></span>';
    }).join('');
    var status = '';
    if (p.f) {
      status = '<p class="pf-status">' + ico(/INJ|SUSP|UNAV|NOT IN/.test(p.f) ? 'injured' : 'doubtful') +
        '<b>' + esc(p.f) + '</b>' + (p.nw ? ' ' + esc(p.nw) : '') + '</p>';
    } else if (p.pr === false) {
      status = '<p class="pf-status">' + ico('doubtful') + '<b>Not in predicted XI</b></p>';
    } else if (p.pr === true) {
      status = '<p class="pf-status pf-ok">' + ico('available') + '<b>Predicted XI</b></p>';
    }
    return '<header class="pf-head">' + photo(id, p) +
      '<div class="pf-id"><span class="lab">' + p.p + ' · ' + esc((store.teams[p.t] || [''])[0]) + '</span>' +
      '<h2 class="disp" id="pf-name">' + esc(p.n) + '</h2>' +
      (p.ar.length ? '<p class="pf-arch">' + esc(p.ar.join(' · ')) + '</p>' : '') +
      '<p class="pf-meta tnum">' + meta.join('') + '</p>' +
      (duties ? '<p class="pf-duties">' + duties + '</p>' : '') + status + '</div>' +
      nextMatch(p) + '</header>';
  }

  function nextMatch(p) {
    var x = p.x;
    if (!x) { return '<div class="pf-next"><span class="lab">Next</span><b class="big">–</b><span>no fixture</span></div>'; }
    var attack = p.p === 'MID' || p.p === 'FWD';
    var fig = attack && x.txg ? x.txg.toFixed(2) + ' <span>team xG</span>' : x.cs + '% <span>CS</span>';
    return '<div class="pf-next"><span class="lab">Next</span>' +
      '<span class="pf-opp">' + crest(teamByShort(x.o)) + '<b>' + esc(x.o) + '</b> ' + (x.h ? 'H' : 'A') + '</span>' +
      '<b class="big tnum">' + x.t.toFixed(1) + '</b><span>xP</span>' +
      '<span class="pf-next-fig tnum">' + fig + '</span></div>';
  }

  function tileNote(field, e) {
    if (field === 'defconHitRate') { return e.dch + '/' + e.dcn; }
    if (field === 'startRate') { return e.st + '/' + e.tm; }
    if (field === 'csRate') { return e.cs + '/' + e.st; }
    if (field === 'xg90') { return e.g + ' G'; }
    if (field === 'xa90') { return e.a + ' A'; }
    if (field === 'xgi90') { return (e.g + e.a) + ' G+A'; }
    if (field === 'bonus90') { return e.b + ' bonus'; }
    if (field === 'saves90') { return e.sv + ' saves'; }
    return '';
  }

  // Five season figures, each on a plate shaded by where it sits among
  // players at the same position (over 180 minutes), with the position's
  // average printed beside it and the bar's length as the percentile.
  function tiles(p) {
    var meta = store.tiles[p.p];
    var html = meta.map(function (m, i) {
      var q = p.q[i], t = q === null ? null : tone(q / 10);
      var note = tileNote(m[3], p.e);
      return '<div class="pf-tile"><span class="pf-tk">' + esc(m[0]) + '</span>' +
        '<b class="pf-tv tnum"' + (t ? ' style="background:' + t[0] + ';color:' + t[1] + '"' : '') + '>' +
        fmt(p.v[i], m[1]) + '</b>' +
        '<span class="pf-bar" title="' + (q === null ? 'Under 180 minutes' : q + 'th percentile') + '">' +
        '<i style="width:' + (q === null ? 0 : q) + '%"></i></span>' +
        '<span class="pf-tn tnum">' + (q === null ? 'under 180 min' : 'avg ' + fmt(m[2], m[1])) +
        (note ? ' · ' + note : '') + '</span></div>';
    }).join('');
    return section('This season · v ' + p.p + 's', '<div class="pf-tiles">' + html + '</div>');
  }

  function fixtures(p) {
    var cells = store.fixtures[p.t];
    if (!cells || !cells.length) { return ''; }
    var field = p.p === 'GKP' || p.p === 'DEF' ? 'cs' : 'at';
    var html = cells.map(function (c) {
      if (c.blank || c.na) {
        return '<li class="pf-fx pf-fx-none"><span>GW' + c.gw + '</span><b>' +
          (c.blank ? 'Blank' : '–') + '</b><span>' + (c.blank ? '' : 'unavailable') + '</span></li>';
      }
      var t = tone(c[field]);
      return '<li class="pf-fx" style="background:' + t[0] + ';color:' + t[1] + '">' +
        '<span>GW' + c.gw + '</span>' + crest(c.opp) +
        '<span>' + esc((store.teams[c.opp] || [''])[0]) + ' ' + (c.h ? 'H' : 'A') + '</span>' +
        '<b class="tnum">' + c[field].toFixed(1) + '</b></li>';
    }).join('');
    return section('Next ' + cells.length,
      '<ul class="pf-fxs">' + html + '</ul>',
      '<span class="pf-unit">' + (field === 'cs' ? 'clean sheet' : 'goals') + ' /10</span>');
  }

  // Match by match: a bar per gameweek to his points, filled green when
  // he returned (goal, assist, clean sheet at the back, or DefCon), a dot
  // for a start and a triangle off the bench beneath, then his marks.
  function strip(p) {
    var ms = p.m;
    if (!ms.length) { return section('Match by match', '<p class="pf-none">No matches yet.</p>'); }
    var cfg = store.strip[p.p], marks = cfg[0], csBox = cfg[1];
    var back = p.p === 'GKP' || p.p === 'DEF';
    var colW = 22, top = 12, barH = 60, markY = top + barH + 12;
    var w = ms.length * colW, h = markY + 8 + marks.length * 13;
    var max = Math.max(3, Math.max.apply(null, ms.map(function (m) { return m[5] || 0; })));
    var cols = ms.map(function (m, i) {
      var cx = i * colW + colW / 2, played = m[3] > 0, pts = played ? m[5] : 0;
      var bh = Math.max(1, Math.max(0, pts) / max * barH), by = top + barH - bh;
      var returned = played && (m[6] || m[7] || (back && m[10]) || m[9] === 1);
      var title = 'GW' + m[0] + (m[1] ? (m[2] === 1 ? ' v ' : m[2] === 0 ? ' @ ' : ' ') + m[1] : '') +
        (played ? ': ' + m[4] + ' min, ' + pts + ' pts' + (m[6] ? ', ' + m[6] + ' G' : '') +
          (m[7] ? ', ' + m[7] + ' A' : '') + (marks.indexOf('defcon') >= 0 ? ', DefCon ' + m[8] : '')
          : ': did not play');
      var g = '<rect class="pf-sbar' + (returned ? ' ret' : '') + '" x="' + (cx - colW / 2 + 3) +
        '" y="' + by + '" width="' + (colW - 6) + '" height="' + bh + '" rx="2"/>';
      if (csBox && played && m[10]) {
        g += '<rect class="pf-scs" x="' + (cx - colW / 2 + 1) + '" y="' + (by - 2) + '" width="' +
          (colW - 2) + '" height="' + (bh + 4) + '" rx="3"/>';
      }
      if (played && m[11]) {
        g += '<path class="pf-scard c' + m[11] + '" d="M' + (cx - 3) + ',' + (by - 5) + 'L' + (cx + 3) +
          ',' + (by - 5) + 'L' + cx + ',' + (by - 10) + 'Z"/>';
      }
      g += m[3] === 2 ? '<circle class="pf-sst" cx="' + cx + '" cy="' + markY + '" r="3"/>'
        : m[3] === 1 ? '<path class="pf-ssub" d="M' + (cx - 3) + ',' + (markY + 3) + 'L' + cx + ',' +
          (markY - 3) + 'L' + (cx + 3) + ',' + (markY + 3) + 'Z"/>'
        : '<circle class="pf-sun" cx="' + cx + '" cy="' + markY + '" r="3"/>';
      if (played) {
        marks.forEach(function (mark, k) {
          var y = markY + 14 + k * 13, t = '';
          if (mark === 'ga') {
            t = (m[6] ? (m[6] > 1 ? m[6] : '') + 'G' : '') + (m[7] ? (m[7] > 1 ? m[7] : '') + 'A' : '');
          } else if (m[9] !== null) {
            t = m[9] ? '+' : '–';
          }
          if (t) {
            g += '<text class="pf-smk' + (mark === 'defcon' && !m[9] ? ' miss' : '') + '" x="' + cx +
              '" y="' + y + '" text-anchor="middle">' + t + '</text>';
          }
        });
      }
      return '<g><title>' + esc(title) + '</title>' + g + '</g>';
    }).join('');
    var key = ['<i class="k-ret"></i> returned', '<i class="k-st"></i> started',
               '<i class="k-sub"></i> off the bench'];
    if (marks.indexOf('ga') >= 0) { key.push('G A'); }
    if (marks.indexOf('defcon') >= 0) { key.push('+/– DefCon'); }
    if (csBox) { key.push('<i class="k-cs"></i> clean sheet'); }
    return section('Match by match',
      '<div class="pf-strip"><svg viewBox="0 0 ' + w + ' ' + h + '" width="' + (w * 1.5) + '" height="' +
      (h * 1.5) + '" role="img" aria-label="Points by gameweek">' + cols + '</svg></div>' +
      '<p class="pf-key">' + key.join('') + '</p>');
  }

  function stat(k, v, n) {
    return '<div class="pf-st"><span class="pf-tk">' + esc(k) + '</span><b class="tnum">' + v + '</b>' +
      (n ? '<span class="pf-tn tnum">' + n + '</span>' : '') + '</div>';
  }

  // What the Squad dialog used to show: the full season line and the
  // next match's expected points part by part.
  function extended(p) {
    var e = p.e, h = [];
    var grid = [stat('Points', e.pts, e.b + ' bonus'), stat('Minutes', e.min, e.st + ' starts'),
                stat('Goals', e.g, e.xg.toFixed(2) + ' xG'), stat('Assists', e.a, e.xa.toFixed(2) + ' xA'),
                stat('xGI per 90', e.xgi90.toFixed(2), e.xgi.toFixed(2) + ' xGI')];
    if (e.dct) { grid.push(stat('DefCon per 90', e.dc90.toFixed(1), e.dch + '/' + e.dcn + ' over ' + e.dct)); }
    if (p.p === 'GKP' || p.p === 'DEF') { grid.push(stat('Clean sheets', e.cs, '')); }
    if (p.p === 'GKP') { grid.push(stat('Saves', e.sv, '')); }
    Object.keys(p.op).forEach(function (k) { grid.push(stat(store.opta[k] || k, p.op[k], 'Opta')); });
    h.push('<div class="pf-grid">' + grid.join('') + '</div>');
    if (p.ls) {
      h.push('<p class="pf-last tnum"><span class="lab">Last season</span><b>' + p.ls.pts + '</b> pts · ' +
        p.ls.min.toLocaleString() + ' min · ' + (p.ls.g + p.ls.a) + ' G+A · ' + p.ls.xgi + ' xGI</p>');
    }
    if (p.x) {
      var top = Math.max.apply(null, p.x.parts.map(Math.abs)) || 1;
      var rows = p.x.parts.map(function (v, i) { return [PARTS[i], v]; })
        .filter(function (r) { return Math.abs(r[1]) >= 0.01; })
        .sort(function (a, b) { return Math.abs(b[1]) - Math.abs(a[1]); })
        .map(function (r) {
          return '<li><span>' + r[0] + '</span><i><s style="width:' + (Math.abs(r[1]) / top * 100).toFixed(0) +
            '%"></s></i><b class="tnum">' + signed(r[1], 2) + '</b></li>';
        }).join('');
      h.push('<div class="subhead pf-xphead"><span class="lab">xP v ' + esc(p.x.o) + ' (' + (p.x.h ? 'H' : 'A') +
        ') · <b class="tnum">' + p.x.t.toFixed(2) + '</b></span>' +
        '<button class="infobtn" type="button" aria-label="More information" aria-expanded="false">' +
        ico('information') + '</button><p class="note" hidden>' +
        (p.x.m === 'history' ? 'Match-history model, as on the Squad pitch.'
          : 'Season model, as in the Scout table.') + '</p></div><ul class="pf-parts">' + rows + '</ul>');
    }
    return '<details class="pf-more"><summary>' + ico('expand') + 'Extended stats</summary>' +
      h.join('') + '</details>';
  }

  function log(p) {
    var played = p.m.filter(function (m) { return m[3] > 0; });
    if (!played.length) { return ''; }
    var rows = played.slice().reverse().map(function (m) {
      return '<tr><td>GW' + m[0] + '</td><td>' + esc(m[1]) + (m[2] === null ? '' : m[2] ? ' H' : ' A') +
        '</td><td class="num">' + m[4] + '</td><td class="num">' + m[6] + '</td><td class="num">' + m[7] +
        '</td><td class="num">' + m[12].toFixed(2) + '</td><td class="num">' + m[13].toFixed(2) +
        '</td><td class="num">' + m[8] + '</td><td class="num">' + m[14] + '</td><td class="num"><b>' +
        m[5] + '</b></td></tr>';
    }).join('');
    return '<details class="pf-more"><summary>' + ico('expand') + 'Match log</summary>' +
      '<div class="scroll"><table class="pf-log"><thead><tr><th>GW</th><th>Opp</th><th class="num">Min</th>' +
      '<th class="num">G</th><th class="num">A</th><th class="num">xG</th><th class="num">xA</th>' +
      '<th class="num">DC</th><th class="num">BPS</th><th class="num">Pts</th></tr></thead><tbody>' +
      rows + '</tbody></table></div></details>';
  }

  function open(id, from) {
    var p = store.players[id];
    if (!p) { return; }
    opener = from;
    body.innerHTML = head(id, p) + tiles(p) + fixtures(p) + strip(p) + extended(p) + log(p);
    dlg.dataset.player = id;
    if (!dlg.open) {
      if (typeof dlg.showModal === 'function') { dlg.showModal(); } else { dlg.setAttribute('open', ''); }
    }
    body.scrollTop = 0;
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target.closest && ev.target.closest('[data-player]');
    if (t && !dlg.contains(t)) { ev.preventDefault(); open(t.dataset.player, t); }
  });
  // Native buttons click on Enter and Space themselves; faces, shirt cards
  // and scatter points are role="button" and need the keys wired.
  document.addEventListener('keydown', function (ev) {
    if (ev.key !== 'Enter' && ev.key !== ' ') { return; }
    var t = ev.target.closest && ev.target.closest('[data-player]');
    if (t && t.tagName !== 'BUTTON' && !dlg.contains(t)) { ev.preventDefault(); open(t.dataset.player, t); }
  });
  dlg.querySelector('.pf-close').addEventListener('click', function () { dlg.close(); });
  dlg.addEventListener('click', function (ev) { if (ev.target === dlg) { dlg.close(); } });
  dlg.addEventListener('close', function () {
    if (opener && opener.isConnected) { opener.focus({ preventScroll: true }); }
  });
})();
