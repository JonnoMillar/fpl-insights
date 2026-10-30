"""Rebuild isolated icon deliverables. Standard library only; no app imports."""
from pathlib import Path
import math
import json

ROOT = Path(__file__).resolve().parent
STROKE = 2.4

def path(d, **attrs):
    extra = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<path d="{d}" {extra}/>'

def circle(x, y, r, solid=False):
    return f'<circle cx="{x}" cy="{y}" r="{r}"'+(' fill="currentColor" stroke="none"' if solid else '')+'/>'

def rect(x, y, w, h, r=1):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/>'

def polygon(cx, cy, r, n=5, angle=-90):
    return ' '.join(f'{cx+r*math.cos(math.radians(angle+i*360/n)):.3f},{cy+r*math.sin(math.radians(angle+i*360/n)):.3f}' for i in range(n))

def ball(x, y, r, compact=False):
    # Identical local master at every position/scale, with clipped edge panels.
    panels = f'<polygon points="{polygon(0,0,.38)}"/>'
    for i in range(5):
        a=math.radians(-90+i*72)
        panels += f'<polygon points="{polygon(math.cos(a)*1.03,math.sin(a)*1.03,.43)}"/>'
    return (f'<svg x="{x-r}" y="{y-r}" width="{2*r}" height="{2*r}" viewBox="-1.12 -1.12 2.24 2.24" overflow="hidden">'
            '<defs><clipPath id="ball-clip"><circle r="1"/></clipPath></defs>'
            '<circle r="1" stroke-width=".19"/>'
            f'<g clip-path="url(#ball-clip)" fill="currentColor" stroke="none">{panels}</g></svg>')

def goal(x=10, y=5, w=19, h=10):
    return path(f'M{x} {y+h}V{y}H{x+w}V{y+h}')

def arrow(x1,y1,x2,y2,head=4):
    dx,dy=x2-x1,y2-y1; length=math.hypot(dx,dy); ux,uy=dx/length,dy/length
    bx,by=x2-ux*head,y2-uy*head
    return path(f'M{x1} {y1}L{bx:.3f} {by:.3f}')+path(f'M{x2} {y2}L{bx-uy*head*.63:.3f} {by+ux*head*.63:.3f}L{bx+uy*head*.63:.3f} {by-ux*head*.63:.3f}Z',fill='currentColor',stroke='none')

def curved_arrow(d,x,y,angle,head=4):
    ux,uy=math.cos(math.radians(angle)),math.sin(math.radians(angle))
    bx,by=x-ux*head,y-uy*head
    return path(d)+path(f'M{x} {y}L{bx-uy*head*.63:.3f} {by+ux*head*.63:.3f}L{bx+uy*head*.63:.3f} {by-ux*head*.63:.3f}Z',fill='currentColor',stroke='none')

def shirt():
    return path('M11 5 4 9l3 8 4-2v13h14V15l4 2 3-8-7-4Z', transform='translate(-2 0)')+path('M9 5c1 6 13 6 14 0')

def check(d='M10 16l4 4 8-9'):
    return path(d)

def band(text):
    # Glyphs are paths, never font-dependent SVG text.
    glyph={'C':'M19 14c-6-4-9 10 0 6','V':'M12 14l4 8 4-8','3C':'M9 14q6-2 5 1l-3 3q4-1 4 2t-6 1 M24 15c-6-4-9 9 0 5'}[text]
    return path('M4 10c0-5 24-5 24 0v13c0 5-24 5-24 0Z M4 10c0 3 24 3 24 0')+path(glyph,stroke_width=1.8)

def icons(compact=False):
    wall=''
    for x in (6,12,18):
        wall+=circle(x,12,1.65)+path(f'M{x-2.35} 17Q{x} 15.7 {x+2.35} 17L{x+1.5} 26H{x-1.5}Z',stroke_width=1.55)
    glove=path('M7 25 4 16q-1-3 1-3l3 4-3-9q0-3 2-2l4 9-1-11q1-2 2 0l2 10 1-9q1-2 2 0v10l3-6q2-1 2 1l-3 11-7 7Z',stroke_width=1.8)
    if compact:
        glove=path('M6 25 3 15q0-3 2-2l3 4-2-9q0-3 2-2l4 9V5q1-3 2 0l1 10 3-7q2-2 2 1l-1 11-7 8Z',stroke_width=2)
    return {
      'goals':goal()+ball(6.7,24,5.2)+arrow(13,20,24,10.5),
      'assists':goal()+ball(24,22,4.6)+arrow(4,26,18.5,20.8),
      'penalties':goal(5,5,22,11)+ball(16,24,5.2),
      'free-kicks':wall+ball(26,25,4.6)+curved_arrow('M28 17Q26 5 12 5',8,5,180),
      'corners':path('M16 20V4 M19 5l8 4-8 4 M3 28l13-8 13 8 M8 25q8 7 16 0'),
      'clean-sheet':goal(4,5,24,19)+check('M10 17l4 4 8-9'),
      'saves':glove+ball(25,24,4.6),
      'minutes':circle(16,18,10)+path('M13 3h6 M16 3v4 M25 8l2 2 M16 12v6l5-3'),
      'yellow-card':rect(8,4,16,24)+path('M12 23h8'),
      'red-card':'<rect x="8" y="4" width="16" height="24" rx="1" fill="currentColor" stroke="none"/>',
      'injured':'<defs><mask id="injury-cut" maskUnits="userSpaceOnUse" x="0" y="0" width="32" height="32"><rect width="32" height="32" fill="white" stroke="none"/><circle cx="24.5" cy="24" r="7.5" fill="black" stroke="none"/></mask></defs><g mask="url(#injury-cut)">'+shirt()+'</g>'+circle(24.5,24,5.5)+path('M24.5 21v6 M21.5 24h6'),
      'doubtful':path('M16 4 29 27H3Z M16 12v7')+circle(16,23,.9,True),
      'available':circle(16,16,12)+check(),
      'captain':band('C'), 'vice-captain':band('V'),
      'bonus':circle(16,12,8)+path('M10 18 6 29l6-2 3 2 2-9 M22 18l4 11-6-2-3 2')+(circle(16,12,2,True) if compact else f'<polygon points="{polygon(16,12,3,5)}" fill="currentColor" stroke="none"/>'),
      'squad':shirt(),
      'planning':path('M9 6h11v8 M20 20v6h4')+circle(6,6,3)+circle(20,17,3)+circle(27,26,3),
      'mini-league':path('M9 4h14v9c0 9-14 9-14 0Z M9 7H4v5q0 6 7 6 M23 7h5v5q0 6-7 6 M16 20v7 M10 28h12'),
      'scout':circle(14,14,10)+path('M21 21l8 8'),
      'transfers':arrow(4,10,28,10)+arrow(28,22,4,22),
      'roll-transfer':curved_arrow('M8 25A11 11 0 1 1 25.43 8.94',28,12,50),
      'fixtures':rect(4,7,24,22,2)+path('M4 13h24 M10 3v7 M22 3v7')+circle(10,20,1,True)+circle(16,20,1,True)+circle(22,20,1,True),
      'deadline':circle(16,16,12)+path('M16 8v9l6 3'),
      'wildcard':path('M4 8h4l16 16 M4 24h4l6-6 M19 13l5-5')+arrow(23,8,29,8,3.6)+arrow(23,24,29,24,3.6),
      'free-hit':path('M19 3 6 18h9l-2 11 13-16h-9Z'),
      'bench-boost':rect(4,11,22,7)+path('M3 22h26 M7 18v11 M25 18v11 M23.5 5h6 M26.5 2v6'),
      'triple-captain':band('3C'),
      'filter':path('M4 7h4 M13 7h15 M4 16h14 M23 16h5 M4 25h5 M14 25h14')+circle(10.5,7,2.5)+circle(20.5,16,2.5)+circle(11.5,25,2.5),
      'compare':rect(4,5,10,22)+rect(18,5,10,22),
      'information':circle(16,16,12)+path('M16 14v10')+circle(16,9,1,True),
      'close':path('M7 7l18 18 M25 7 7 25'),
      'previous':path('M21 6 11 16l10 10'),
      'next':path('M11 6l10 10-10 10'),
      'expand':path('M6 11l10 10 10-10'),
      'external-link':path('M16 5H5v22h22V16')+arrow(14,18,29,3),
      'price-rise':path('M3 26h7v-7h7v-7h5')+arrow(22,12,29,5),
      'price-fall':path('M3 6h7v7h7v7h5')+arrow(22,20,29,27),
      'defence':path('M16 3Q10 7 5 8v9q1 9 11 13 10-4 11-13V8Q22 7 16 3Z')+check(),
      'suspended':circle(16,16,12)+path('M7.5 24.5l17-17'),
    }

def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32" fill="none" stroke="currentColor" stroke-width="{STROKE}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>\n'

def build():
    records=[]
    for compact,folder in ((False,'icons'),(True,'compact')):
        target=ROOT/folder;target.mkdir(exist_ok=True)
        for name,body in icons(compact).items():
            (target/f'{name}.svg').write_text(svg(body),encoding='utf-8')
            if not compact: records.append({'name':name,'path':f'icons/{name}.svg','compact':f'compact/{name}.svg'})
    (ROOT/'catalog.json').write_text(json.dumps({'status':'vector_review_not_user_approved','viewBox':[0,0,32,32],'stroke':STROKE,'icons':records},indent=2)+'\n',encoding='utf-8')
    cards=[]
    for item in records:
        name=item['name'];label=name.replace('-',' ').title()
        sizes=''.join(f'<span><img src="{item["compact"] if size==16 else item["path"]}" width="{size}" height="{size}" alt=""><small>{size}</small></span>' for size in (16,20,24,32))
        cards.append(f'<article><div class="hero">{svg(icons()[name])}</div><b>{label}</b><div class="sizes">{sizes}</div></article>')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FPL Insights vector review</title><style>*{box-sizing:border-box}body{margin:0;background:#f4f3f4;color:#37003c;font:14px Arial,sans-serif}main{max-width:1280px;margin:auto;padding:28px}h1{font-size:26px}p{max-width:760px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px}article{background:white;border-radius:12px;padding:20px 8px;text-align:center}.hero{height:96px;display:grid;place-items:center}.hero>svg{width:72px;height:72px}b{display:block;margin:10px 0 20px}.sizes{height:56px;display:flex;gap:15px;justify-content:center;align-items:flex-start}.sizes span{display:flex;align-items:center;flex-direction:column;gap:8px;min-width:32px}.sizes img{display:block}.sizes small{font-size:10px;color:#726575}button{background:#37003c;color:white;padding:10px 16px;border:0;border-radius:6px;cursor:pointer}.dark article{background:#37003c;color:white}.dark .sizes img{filter:brightness(0) invert(1)}.dark .sizes small{color:#ddd}@media(max-width:800px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:530px){main{padding:14px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.sizes{gap:4px}}</style><main><h1>FPL Insights — vector review</h1><p>40 individual icons, shared geometry. Large drawings plus actual-size 16 / 20 / 24 / 32px samples. The 16px column uses the compact version. These are review assets; semantic recognition and final approval remain with Jonno.</p><p><button onclick="document.body.classList.toggle('dark')">Toggle dark background</button> <a href="README.md">Usage and review notes</a></p><div class="grid">'''+''.join(cards)+'</div></main></html>'
    (ROOT/'preview.html').write_text(html,encoding='utf-8')
    print(f'Built {len(records)} icons, 40 compact exports and preview.')

if __name__=='__main__':build()
