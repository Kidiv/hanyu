# Генератор прописей 田字格 с порядком черт.
# python propisi.py <урок.txt> <выход.pdf> "<заголовок>"
# Формат строки входного файла: иероглифы<TAB>пиньинь<TAB>перевод
import sys, os, json, re, fitz

HERE = os.path.dirname(os.path.abspath(__file__))
SIMSUN = r"C:\Windows\Fonts\simsun.ttc"
YAHEI = r"C:\Windows\Fonts\msyh.ttc"
GRAPHICS = os.path.join(HERE, "data", "graphics.txt")

MM = 72 / 25.4
W, H = 210 * MM, 297 * MM
LM, TM, RM, BM = 10 * MM, 14 * MM, 10 * MM, 10 * MM
WORD_W = 30 * MM          # колонка слова (иероглифы, пиньинь, перевод)
LABEL_W = WORD_W + 2 * MM
PC = 10 * MM              # квадрат почертного написания
PGAP = 1.2 * MM           # зазор между строкой черт и клетками
CELL = 14 * MM
GAP = 2.4 * MM
INNER = 0.6 * MM
TRACE = 2                 # серых образцов в первой строке
ROWS = 2                  # строк клеток на знак
NCELLS = int((W - LM - RM - LABEL_W) // CELL)
NPROG = int((W - LM - RM - LABEL_W) // PC)

GREY_LINE = (0.72, 0.72, 0.72)
GREY_CHAR = (0.62, 0.62, 0.62)
GLYPH_FILL = (0.25, 0.25, 0.25)
NUM_COLOR = (0.85, 0.1, 0.1)
BLACK = (0, 0, 0)


def load_strokes(chars):
    need = set(chars)
    found = {}
    if not os.path.exists(GRAPHICS):
        return found
    with open(GRAPHICS, encoding="utf-8") as f:
        for line in f:
            i = line.find('"character":"') + 13
            ch = line[i]
            if ch in need:
                d = json.loads(line)
                found[ch] = (d["strokes"], d["medians"])
                if len(found) == len(need):
                    break
    return found


_tok = re.compile(r"[MLQCZ]|-?\d+(?:\.\d+)?")


def draw_stroke_path(shape, path, tr):
    toks = _tok.findall(path)
    i = 0
    cur = start = None
    while i < len(toks):
        c = toks[i]
        if c == "M":
            cur = start = tr(float(toks[i + 1]), float(toks[i + 2])); i += 3
        elif c == "L":
            p = tr(float(toks[i + 1]), float(toks[i + 2]))
            shape.draw_line(cur, p); cur = p; i += 3
        elif c == "Q":
            q = tr(float(toks[i + 1]), float(toks[i + 2]))
            p = tr(float(toks[i + 3]), float(toks[i + 4]))
            c1 = fitz.Point(cur.x + 2 / 3 * (q.x - cur.x), cur.y + 2 / 3 * (q.y - cur.y))
            c2 = fitz.Point(p.x + 2 / 3 * (q.x - p.x), p.y + 2 / 3 * (q.y - p.y))
            shape.draw_bezier(cur, c1, c2, p); cur = p; i += 5
        elif c == "C":
            c1 = tr(float(toks[i + 1]), float(toks[i + 2]))
            c2 = tr(float(toks[i + 3]), float(toks[i + 4]))
            p = tr(float(toks[i + 5]), float(toks[i + 6]))
            shape.draw_bezier(cur, c1, c2, p); cur = p; i += 7
        elif c == "Z":
            if cur != start:
                shape.draw_line(cur, start)
            cur = start; i += 1
        else:
            i += 1


def stroke_order_glyph(page, x, y, size, strokes, medians, fl):
    # данные в поле 1024x1024, ось y вверх, базовая линия на 900
    def tr(px, py):
        return fitz.Point(x + px / 1024 * size, y + (900 - py) / 1024 * size)
    shape = page.new_shape()
    for path in strokes:
        draw_stroke_path(shape, path, tr)
        shape.finish(fill=GLYPH_FILL, color=None, closePath=True)
    shape.commit()
    page.draw_rect(fitz.Rect(x, y, x + size, y + size), color=GREY_LINE, width=0.4)
    # номера черт у начала срединной линии, со сдвигом против направления черты
    placed = []
    R = 1.25 * MM
    halo = page.new_shape()
    tw = fitz.TextWriter(page.rect, color=NUM_COLOR)
    for n, med in enumerate(medians, 1):
        p0 = tr(*med[0])
        p1 = tr(*med[min(1, len(med) - 1)])
        dx, dy = p0.x - p1.x, p0.y - p1.y
        L = (dx * dx + dy * dy) ** 0.5 or 1
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        cands = [(1.7, 0), (1.7, 2.4), (1.7, -2.4), (3.6, 0), (3.6, 2.4), (3.6, -2.4), (0, 2.6), (0, -2.6)]
        best = None
        for a, b in cands:
            cx = p0.x + (ux * a + nx * b) * MM
            cy = p0.y + (uy * a + ny * b) * MM
            cx = min(max(cx, x + R), x + size - R)
            cy = min(max(cy, y + R), y + size - R)
            dmin = min([((cx - qx) ** 2 + (cy - qy) ** 2) ** 0.5 for qx, qy in placed] or [99])
            if best is None or dmin > best[0]:
                best = (dmin, cx, cy)
            if dmin >= 2 * R:
                break
        _, cx, cy = best
        placed.append((cx, cy))
        halo.draw_circle((cx, cy), R)
        s = str(n)
        adv = fl.text_length(s, fontsize=6.5)
        tw.append((cx - adv / 2, cy + 0.85 * MM), s, font=fl, fontsize=6.5)
    halo.finish(fill=(1, 1, 1), color=NUM_COLOR, width=0.25)
    halo.commit()
    tw.write_text(page)


def stroke_progression(page, x, y, strokes):
    """Ряд квадратов: в k-м квадрате черты 1..k, новая черта красным. Возвращает число строк."""
    n = len(strokes)
    rows = (n + NPROG - 1) // NPROG
    pad = 0.8 * MM
    size = PC - 2 * pad
    for k in range(n):
        cx = x + (k % NPROG) * PC
        cy = y + (k // NPROG) * PC
        page.draw_rect(fitz.Rect(cx, cy, cx + PC, cy + PC), color=GREY_LINE, width=0.3)
        def tr(px, py, cx=cx, cy=cy):
            return fitz.Point(cx + pad + px / 1024 * size, cy + pad + (900 - py) / 1024 * size)
        shape = page.new_shape()
        for j in range(k + 1):
            draw_stroke_path(shape, strokes[j], tr)
            shape.finish(fill=(NUM_COLOR if j == k else GLYPH_FILL), color=None, closePath=True)
        shape.commit()
    return rows


def cell(page, x, y):
    r = fitz.Rect(x, y, x + CELL, y + CELL)
    page.draw_rect(r, color=BLACK, width=0.6)
    page.draw_line((x, y + CELL / 2), (x + CELL, y + CELL / 2), color=GREY_LINE, width=0.4, dashes="[2 2] 0")
    page.draw_line((x + CELL / 2, y), (x + CELL / 2, y + CELL), color=GREY_LINE, width=0.4, dashes="[2 2] 0")
    page.draw_line((x, y), (x + CELL, y + CELL), color=GREY_LINE, width=0.3, dashes="[2 2] 0")
    page.draw_line((x + CELL, y), (x, y + CELL), color=GREY_LINE, width=0.3, dashes="[2 2] 0")


def char_in_cell(page, x, y, ch, font, color):
    fs = CELL * 0.78
    tw = fitz.TextWriter(page.rect, color=color)
    adv = font.text_length(ch, fontsize=fs)
    tw.append((x + (CELL - adv) / 2, y + CELL * 0.5 + fs * 0.38), ch, font=font, fontsize=fs)
    tw.write_text(page)


def label(page, x, y, hanzi, pinyin, ru, fz, fl):
    tw = fitz.TextWriter(page.rect, color=BLACK)
    n = len(hanzi)
    hs = 26 if n <= 2 else (19 if n <= 3 else 14)
    tw.append((x, y + 9.5 * MM), hanzi, font=fz, fontsize=hs)
    tw.append((x, y + 14.0 * MM), pinyin, font=fl, fontsize=8.5)
    maxw = WORD_W - 2 * MM
    t = ru
    while fl.text_length(t, fontsize=7.5) > maxw and len(t) > 3:
        t = t[:-2] + "…"
    tw.append((x, y + 18.0 * MM), t, font=fl, fontsize=7.5)
    tw.write_text(page)


def header(page, title, fl, pageno):
    tw = fitz.TextWriter(page.rect, color=BLACK)
    tw.append((LM, 9 * MM), title, font=fl, fontsize=11)
    tw.append((W - RM - 6 * MM, 9 * MM), str(pageno), font=fl, fontsize=9)
    tw.write_text(page)


def make(words, title, out):
    doc = fitz.open()
    fz = fitz.Font(fontfile=SIMSUN)
    fl = fitz.Font(fontfile=YAHEI)
    allchars = [c for h, _, _ in words for c in h if '\u4e00' <= c <= '\u9fff']
    strokes = load_strokes(allchars)
    missing = sorted(set(c for c in allchars if c not in strokes))
    page = None
    y = TM
    pageno = 0
    cells_h = ROWS * CELL + (ROWS - 1) * INNER
    for hanzi, pinyin, ru in words:
        chars = [c for c in hanzi if '一' <= c <= '鿿']
        if not chars:
            continue
        need_label = True
        for ch in chars:
            nstr = len(strokes[ch][0]) if ch in strokes else 0
            prow = (nstr + NPROG - 1) // NPROG if nstr else 0
            block_h = prow * PC + (PGAP if prow else 0) + cells_h + GAP
            if page is None or y + block_h > H - BM:
                pageno += 1
                page = doc.new_page(width=W, height=H)
                header(page, title, fl, pageno)
                y = TM
                need_label = True
            if need_label:
                label(page, LM, y, hanzi, pinyin, ru, fz, fl)
                need_label = False
            x0 = LM + LABEL_W
            if prow:
                stroke_progression(page, x0, y, strokes[ch][0])
                y += prow * PC + PGAP
            for r in range(ROWS):
                for i in range(NCELLS):
                    x = x0 + i * CELL
                    cell(page, x, y)
                    if r == 0 and i < TRACE:
                        char_in_cell(page, x, y, ch, fz, GREY_CHAR)
                y += CELL + (GAP if r == ROWS - 1 else INNER)
    doc.save(out)
    return pageno, missing


if __name__ == "__main__":
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    words = []
    for line in open(src, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        while len(parts) < 3:
            parts.append("")
        words.append(tuple(parts[:3]))
    n, missing = make(words, title, out)
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{out}: {n} стр., {len(words)} слов, без порядка черт: {''.join(missing) or 'нет'}")
