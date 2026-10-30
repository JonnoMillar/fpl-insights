"""Optional asset checks using the locally installed Playwright; no app changes."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
import json
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def verify():
    files = list((ROOT/'icons').glob('*.svg')) + list((ROOT/'compact').glob('*.svg'))
    assert len(files) == 80
    for file in files:
        element = ET.parse(file).getroot()
        assert element.attrib['viewBox'] == '0 0 32 32'
        assert '<text' not in file.read_text(encoding='utf-8')
    server = ThreadingHTTPServer(('127.0.0.1',0), partial(Quiet,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page(viewport={'width':1280,'height':900},device_scale_factor=1)
            page.goto(f'http://127.0.0.1:{server.server_port}/preview.html')
            page.wait_for_function('[...document.images].every(i=>i.complete&&i.naturalWidth>0)')
            issues=page.evaluate('''()=>{let issues=[];for(const img of document.images){let c=document.createElement('canvas');c.width=c.height=64;let ctx=c.getContext('2d');ctx.drawImage(img,0,0,64,64);let d=ctx.getImageData(0,0,64,64).data;let ink=0,edge=0;for(let y=0;y<64;y++)for(let x=0;x<64;x++){if(d[(y*64+x)*4+3]>32){ink++;if(x==0||y==0||x==63||y==63)edge++}}if(!ink||edge)issues.push({src:img.getAttribute('src'),ink,edge})}return issues}''')
            assert not issues, issues
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(ROOT/'preview.png'),full_page=True)
            page.get_by_role('button').click()
            page.screenshot(path=str(ROOT/'preview-dark.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(ROOT/'preview-mobile.png'),full_page=True)
            browser.close()
        report={'svg_count':80,'preview_samples':160,'sizes':[16,20,24,32],
                'parsed':True,'all_images_loaded':True,'render_border_issues':issues,
                'desktop_1280px_overflow':False,'mobile_390px_overflow':False,
                'recognition':'visual review only; no user recognition testing'}
        (ROOT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
    finally:
        server.shutdown()
        server.server_close()

if __name__=='__main__':
    verify()
