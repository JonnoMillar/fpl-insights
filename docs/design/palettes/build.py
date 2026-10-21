"""Build a disposable colour study from an existing complete dashboard.

python docs/design/palettes/build.py --input dashboard-artifact.html --out PATH
No source fetches or changes to the production dashboard.
"""

import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.input.read_text(encoding="utf-8")
    if not source.lstrip().lower().startswith("<!doctype html"):
        parser.error("Input must be a complete dashboard HTML document.")
    here = Path(__file__).parent
    picker = '''<section class="palette-picker" aria-label="Colour palette preview">
      <div class="palette-options" role="group" aria-label="Choose a palette"></div>
      <p class="palette-description" aria-live="polite"></p>
    </section>'''
    source, count = re.subn(
        r'<section class="product-intro".*?</section>', picker, source,
        count=1, flags=re.DOTALL,
    )
    if count != 1:
        parser.error("Could not locate the dashboard introduction.")
    source = source.replace("</head>", "<style>" + here.joinpath("preview.css").read_text(encoding="utf-8") + "</style></head>", 1)
    source = source.replace("</body>", "<script>" + here.joinpath("preview.js").read_text(encoding="utf-8") + "</script></body>", 1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(source, encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
