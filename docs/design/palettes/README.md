# Squad palette study

Five disposable colour options on the same real dashboard snapshot. This is a
design comparison, not a production theme selector. Only the Squad view is in
scope. Existing type, data, pitch geometry and interactions are retained.

Build from an already verified complete dashboard:

```powershell
python docs/design/palettes/build.py --input PATH_TO_HTML --out PATH_TO_PREVIEW
```

Open the output through the local review server. The five buttons switch colours
without reloading the squad or resetting the transfer preview. A URL fragment
selects an initial option: `#touchline`, `#cyan`, `#pink`, `#lime`, `#floodlights`.

| Direction | Ground | Structure | Attention | FPL connection |
| --- | --- | --- | --- | --- |
| Touchline | `#edf1ee` | `#193e32` | `#00ed87` | Mint, football greens, small purple masthead |
| Cyan pulse | `#eaf0f5` | `#152d49` | `#05d8ed` | Electric cyan, purple masthead, green gains |
| Pink accent | `#f2eff1` | `#302c36` | `#ff7cba` | Pink, plum masthead, green pitch/gains |
| Lime press | `#eff1e8` | `#303c28` | `#d4f64a` | Pitch greens, electric accent, purple masthead |
| Floodlights | `#10232c` | `#081b24` | `#00ed87` | Mint against a dark matchday setting |

Keep colour roles consistent across all five: the next action and projection
receive the attention accent; completed results are quieter; gains/incoming
players remain green, losses red, and availability warnings amber. Pale player
cards keep kit images readable even in the dark option. Bright accents use dark
text when filled; on white, use the darker accent ink.

The comparison deliberately reduces purple's area rather than replacing every
purple block with another loud block. Main tabs remain functional, but only the
Squad workspace is refined for this comparison; the other sections are outside
this colour study. Production files and the hosted artifact are untouched.
