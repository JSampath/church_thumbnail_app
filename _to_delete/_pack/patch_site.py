import os, shutil, sys
root = sys.argv[1]
bk = os.path.join(root, "_backup", "before-thumbnail-generator-update")
os.makedirs(bk, exist_ok=True)
for f in ("index.html", "assets/css/site.css"):
    shutil.copy2(os.path.join(root, f), os.path.join(bk, os.path.basename(f)))

p = os.path.join(root, "index.html")
s = open(p, encoding="utf-8").read()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)

# 1) Hero picture: five app tiles on an arc instead of four.
a = s.index('<g class="traces">'); b = s.index('</g>', a) + 4
traces = ['M60 318V272', 'M160 318V272', 'M360 318V272', 'M460 318V272', 'M60 272H460', 'M260 318V226',
          'M260 166V140H50V100', 'M260 166V140H155V74', 'M260 166V62', 'M260 166V140H365V74', 'M260 166V140H470V100']
s = s[:a] + '<g class="traces">' + ''.join(
    f'<path class="trace" style="--d:{i*0.07:.2f}s" d="{d}"/>' for i, d in enumerate(traces)) + '</g>' + s[b:]

a = s.index('<a class="app-link"'); b = s.rindex('</a>', 0, s.index('<g class="people">')) + 4
tiles = [
    ("church-management-system/", "Church Management System", "Church Management System", 50, 66, "assets/img/cms-emblem-180.png", 25),
    ("holy-bible/", "Mana Bible", "Mana Bible - పరిశుద్ధ గ్రంథము", 155, 40, "assets/img/mana-bible-180.png", 31),
    ("te-deum/", "Te Deum", "Te Deum", 260, 28, "assets/img/te-deum-icon-180.png", 31),
    ("bible-champs/", "The Bible Champs", "The Bible Champs", 365, 40, "assets/img/bible-champs-icon-180.png", 31),
    ("thumbnail-generator/", "Livestream Thumbnail Generator", "Livestream Thumbnail Generator", 470, 66, "assets/img/thumbnail-generator-icon-180.png", 31),
]
s = s[:a] + ''.join(
    f'<a class="app-link" href="{h}" aria-label="Open {n}"><title>{t}</title><g transform="translate({x} {y})"><g class="app-lift">'
    f'<rect x="-34" y="-34" width="68" height="68" rx="18" class="app-tile"/>'
    f'<image href="{img}" x="-{r}" y="-{r}" width="{2*r}" height="{2*r}"/></g></g></a>'
    for h, n, t, x, y, img, r in tiles) + s[b:]
rep('to four apps. Select an app', 'to five apps. Select an app')

# 2) Apps list intro + new catalogue entry.
rep('One Windows application and three mobile apps — all free, with no ads.',
    'Two apps for your computer and three for your phone — all free, with no ads.')
entry = '''          <li>
            <article class="entry">
              <div class="icon full"><img src="assets/img/thumbnail-generator-icon-180.png" alt="" width="96" height="96"></div>
              <div>
                <h3><a href="thumbnail-generator/">Livestream Thumbnail Generator <span class="new">New</span></a></h3>
                <p>A YouTube thumbnail for your church's live stream in a minute: pick a template (Sunday worship, anniversary, Christmas and more), type the words, choose the date and time, and download. Your logo, colours and photos — the picture updates as you type.</p>
                <span class="platform">Windows, Mac and Linux, free download</span>
              </div>
              <a class="btn btn-quiet go" href="thumbnail-generator/">View app</a>
            </article>
          </li>
        </ul>'''
i = s.index('</ul>', s.index('class="catalogue"'))
s = s[:i - len('        ')] + entry + s[i + len('</ul>'):] if s[i - 8:i] == '        ' else None
assert s
open(p, "w", encoding="utf-8", newline="").write(s)

# 3) Thumbnail examples are 16:9 pictures: show them whole.
c = os.path.join(root, "assets/css/site.css")
css = open(c, encoding="utf-8").read()
if "Livestream Thumbnail Generator" not in css:
    css += '''
/* ── Livestream Thumbnail Generator: 16:9 examples shown whole ───────── */
.shots.wide img { aspect-ratio: 16 / 9; object-position: center; }
.entry h3 .new { font-size: .72rem; vertical-align: .35em; }
'''
    open(c, "w", encoding="utf-8", newline="").write(css)
print("patched")
