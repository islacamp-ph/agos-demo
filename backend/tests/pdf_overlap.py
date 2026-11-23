# Render a pitch-summary PDF with pymupdf: check text spans don't overlap / stay on page, save PNG
import sys, itertools
import pymupdf

path = sys.argv[1]
doc = pymupdf.open(path)
pg = doc[0]
print("pages", doc.page_count, "size", pg.rect)
spans = []
for b in pg.get_text("dict")["blocks"]:
    for l in b.get("lines", []):
        for s in l["spans"]:
            if s["text"].strip():
                spans.append((pymupdf.Rect(s["bbox"]), s["text"]))
bad = 0
for (r1, t1), (r2, t2) in itertools.combinations(spans, 2):
    i = r1 & r2
    if not i.is_empty and i.width > 1 and i.height > 1:
        bad += 1
        print("OVERLAP", round(i.width, 1), round(i.height, 1), repr(t1[:50]), "<>", repr(t2[:50]))
for r, t in spans:
    if not pg.rect.contains(r) or r.x1 > pg.rect.x1 - 20:
        print("NEAR/OFF EDGE", r, repr(t[:50]))
imgs = pg.get_images()
print("spans", len(spans), "overlaps", bad, "images", len(imgs), "links", [l.get("uri") for l in pg.get_links()])
pg.get_pixmap(dpi=90).save(path.replace(".pdf", ".png"))
