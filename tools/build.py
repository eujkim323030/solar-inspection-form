# 공식 「태양광발전설비 사용전 및 정기검사 수검자 서식」 PDF에서
#  1) 예시값(회색 글자, 총괄표의 ㅇㅇ 예시, 예시로 칠해진 ■)을 지운 빈 양식 template.pdf
#  2) 앱 배경 그림 bg/pNN.png
#  3) 입력 칸 좌표 fields.json
# 을 만든다.  사용법: python -I build.py <원본.pdf> <앱 폴더(docs)> [디버그 그림 폴더]
import sys, json, re, os
import fitz

sys.stdout.reconfigure(encoding="utf-8")
SRC, APP = sys.argv[1], sys.argv[2]
DBG = sys.argv[3] if len(sys.argv) > 3 else None

# 원본 쪽 번호(1부터) → 서식 정보.  1·13쪽은 표지라 뺀다.
SHEETS = [
    (4,  "총괄표",              "점검 및 시험성적서 측정/시험 총괄표"),
    (5,  "모듈(1)",             "태양전지 모듈 점검기록표(1)"),
    (6,  "모듈(2)",             "태양전지 모듈 점검기록표(2)"),
    (7,  "인버터",              "태양광 발전용 전력변환장치 점검기록표"),
    (8,  "구조물",              "태양광 구조물 점검기록표"),
    (9,  "저압반·보호장치",      "저압설비(LV반) 및 보호장치 점검기록표"),
    (10, "시공 체크리스트",      "[사용전] 태양광발전설비 시공 체크리스트"),
    (11, "부지·구조물(정기)",    "(정기검사용) 태양광 부지·구조물 점검기록표"),
    (12, "BIPV·BAPV 방수",      "[사용전] (BIPV 또는 BAPV) 방수 시공상태 점검기록표"),
    (14, "변압기·접지",          "변압기 및 접지저항 점검기록표"),
    (15, "계전기·차단기(1)",     "계전기 및 차단기 동작시험기록표(1)"),
    (16, "계전기·차단기(2)",     "계전기 및 차단기 동작시험기록표(2)"),
    (17, "전선로·고압모선 절연",  "전선로 및 고압모선·기기 절연측정기록표"),
    (18, "DC 고전압 절연진단",    "DC 고전압 절연진단기록표"),
    (19, "절연저항(설비상태)",    "절연저항(설비상태) 점검기록표"),
    (20, "접지저항 측정",        "접지저항 측정기록표"),
]
SAMPLE_COLORS = {0x999999, 0x7F7F7F}
DEFAULT_COLOR = 0x7F7F7F            # 총괄표의 '태양광모듈' 같은 분야명은 지우되 기본값으로 넣어 준다
P4_SAMPLE_LABELS = ("상호:", "점검/시험자명:", "①장비명:", "제조번호:", "교정 유효일자:")
UNIT_RE = re.compile(r"^[\[\(（].*[\]\)）]$")
UNIT_TOKENS = {"Φ", "kVA", "kV", "㎎KOH/ｇ", "㎎KOH/g", "㎎KOH/", "ｇ", "g"}   # 앞에 숫자를 적는 단위 (변압기·계전기 서식)
DIAG_SPLIT = {14, 15, 16}   # 대각선 칸을 위·아래 두 칸(예: 400/5)으로 쓰는 서식
BG_ZOOM = 2


def R(r):
    return [round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1)]


def center(r):
    return fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)


def chars(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                for ch in s["chars"]:
                    out.append(dict(c=ch["c"], r=fitz.Rect(ch["bbox"]), color=s["color"], size=s["size"], line=id(l)))
    return out


def rows_of(cs):
    """글자를 높이(y) 기준으로 줄로 묶는다. 공백은 뺀다."""
    solid = sorted([c for c in cs if not c["c"].isspace()], key=lambda c: center(c["r"]).y)
    rows = []
    for c in solid:
        yc = center(c["r"]).y
        if rows and abs(yc - rows[-1]["yc"]) <= max(2.2, 0.3 * c["size"]):
            rows[-1]["cs"].append(c)
        else:
            rows.append(dict(yc=yc, cs=[c]))
    for row in rows:
        row["cs"].sort(key=lambda c: c["r"].x0)
    return [row["cs"] for row in rows]


def box_ratio(doc):
    """□ 글자 안에서 실제 네모가 차지하는 비율(그려서 잰다)."""
    p = doc[4]
    ch = next(c for c in chars(p) if c["c"] == "□")
    z = 12
    pix = p.get_pixmap(matrix=fitz.Matrix(z, z), clip=ch["r"], colorspace=fitz.csGRAY)
    xs, ys = [], []
    for y in range(pix.height):
        for x in range(pix.width):
            if pix.pixel(x, y)[0] < 128:
                xs.append(x); ys.append(y)
    w, h = pix.width, pix.height
    ymid = (min(ys) + max(ys)) // 2
    x, run = min(xs), 0
    while pix.pixel(x + run, ymid)[0] < 128:
        run += 1
    return (min(xs) / w, min(ys) / h, (max(xs) + 1) / w, (max(ys) + 1) / h, run / z)


def clean(page, pno, ratio):
    """예시값을 지운다. (지운 예시값 덩어리, 빈 □로 바꾼 ■ 글자) 를 돌려준다."""
    cs = chars(page)
    samples, filled = [], []
    for c in cs:
        if c["c"].isspace():
            continue
        if c["color"] in SAMPLE_COLORS:
            samples.append(c)
        elif c["c"] == "■":
            filled.append(c)
    if pno == 4:
        # 같은 글자 덩어리 안에 '상호: ㅇㅇ전기시험(주)'처럼 붙어 있는 예시값
        by_line = {}
        for c in cs:
            by_line.setdefault(c["line"], []).append(c)
        for line in by_line.values():
            text = "".join(c["c"] for c in line)
            for lab in P4_SAMPLE_LABELS:
                i = text.find(lab)
                if i < 0:
                    continue
                j = i + len(lab)
                nxt = min([text.find(l2, j) for l2 in P4_SAMPLE_LABELS if text.find(l2, j) > 0] + [len(text)])
                samples += [c for c in line[j:nxt] if not c["c"].isspace() and c["color"] == 0]
    for c in samples + filled:
        p = center(c["r"])
        page.add_redact_annot(fitz.Rect(p.x - 0.6, p.y - 0.6, p.x + 0.6, p.y + 0.6), fill=False, cross_out=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)
    for c in filled:   # 예시로 칠해진 ■ 자리에 빈 □를 그린다
        r = c["r"]
        sq = fitz.Rect(r.x0 + r.width * ratio[0], r.y0 + r.height * ratio[1],
                       r.x0 + r.width * ratio[2], r.y0 + r.height * ratio[3])
        # 선 굵기만큼 안쪽으로 그려야 원래 □ 와 크기가 같다
        t = ratio[4]
        page.draw_rect(sq + (t / 2, t / 2, -t / 2, -t / 2), color=(0, 0, 0), width=t)
    left = [c for c in chars(page) if (c["color"] in SAMPLE_COLORS or c["c"] == "■") and not c["c"].isspace()]
    assert not left, f"p{pno}: 안 지워진 예시값 {''.join(c['c'] for c in left)}"
    groups = {}
    for c in samples:
        groups.setdefault((c["line"], c["color"]), []).append(c)
    # '2020년 7월 10일'처럼 한 줄에 떨어져 있는 예시값은 따로따로
    split = []
    for (_, color), g in groups.items():
        g.sort(key=lambda c: c["r"].x0)
        part = [g[0]]
        for c in g[1:]:
            if c["r"].x0 - part[-1]["r"].x1 > 4:
                split.append((color, part)); part = []
            part.append(c)
        split.append((color, part))
    out = []
    for color, g in split:
        r = fitz.Rect(g[0]["r"])
        for c in g[1:]:
            r |= c["r"]
        out.append(dict(text="".join(c["c"] for c in g).strip(), r=r, default=color == DEFAULT_COLOR))
    return out, [dict(c, c="□") for c in filled]


def vlines(page):
    """세로 선(칸 경계) 목록 [(x, y0, y1)], 대각선 가운데점 목록, 가로선(점선 포함) 목록 [(y, x0, x1)]."""
    out, diag, hl = [], [], []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.x - b.x) < 1.2 and abs(a.y - b.y) > 4:
                    out.append((a.x, min(a.y, b.y), max(a.y, b.y)))
                elif abs(a.x - b.x) > 4 and abs(a.y - b.y) > 4:
                    diag.append(center(fitz.Rect(a, b)))
                elif abs(a.y - b.y) < 1.2:
                    hl.append(((a.y + b.y) / 2, min(a.x, b.x), max(a.x, b.x)))
            elif it[0] == "re":
                r = it[1]
                if r.width < 1.6 and r.height > 4:
                    out.append(((r.x0 + r.x1) / 2, r.y0, r.y1))
                elif r.height < 1.6:
                    hl.append(((r.y0 + r.y1) / 2, r.x0, r.x1))
                elif r.height > 4:
                    out += [(r.x0, r.y0, r.y1), (r.x1, r.y0, r.y1)]
    return out, diag, hl


def split_rows(cell, hl):
    """칸 안을 가로지르는 가로선(점선 포함) 위치로 칸을 줄 단위로 나눈다."""
    span = {}   # y → [가장 왼쪽, 가장 오른쪽]  (점선은 짧은 조각들이라 걸친 범위로 잰다)
    for y, x0, x1 in hl:
        if cell.y0 + 4 < y < cell.y1 - 4 and x1 > cell.x0 and x0 < cell.x1:
            key = round(y * 2) / 2
            lo, hi = span.get(key, (x0, x1))
            span[key] = (min(lo, x0), max(hi, x1))
    ys = sorted(y for y, (lo, hi) in span.items() if min(hi, cell.x1) - max(lo, cell.x0) > cell.width * 0.6)
    merged = []
    for y in ys:
        if not merged or y - merged[-1] > 3:
            merged.append(y)
    edges = [cell.y0] + merged + [cell.y1]
    return [fitz.Rect(cell.x0, a, cell.x1, b) for a, b in zip(edges, edges[1:])]


# 자동으로 못 잡는 칸 (원본 쪽 번호 → [(x0, y0, x1, y1, 이름)])
def manual(pno):
    out = []
    if pno == 4:
        ys = [416.0, 433.9, 451.9, 469.9, 487.8, 505.8, 523.8, 541.7]   # 장비 ①~⑦ + 빈 줄
        for k, y in enumerate(ys):
            n = "①②③④⑤⑥⑦⑧"[k]
            if k >= 1:
                out.append((273, y - 3, 386, y + 12, f"{n}장비 제조번호"))
                out.append((391, y - 3, 536, y + 12, f"{n}장비 교정 유효일자"))
            if k == 7:
                out.append((112, y - 3, 268, y + 12, f"{n}장비명"))
    if pno == 18:
        out.append((60, 717, 536, 764, "종합의견(이어서)"))
    return out


def build_page(page, pno, samples, filled, ratio):
    cs = chars(page) + filled
    rows = rows_of(cs)
    vl, diag, hl = vlines(page)
    try:
        cells = [fitz.Rect(c) for t in page.find_tables().tables for c in t.cells if c]
    except Exception:
        cells = []
    cells = [c for c in cells if c.width > 3 and c.height > 3]
    solid = [c for c in cs if not c["c"].isspace()]
    cell_chars = [[c for c in solid if cell.contains(center(c["r"]))] for cell in cells]
    cell_text = ["".join(c["c"] for c in sorted(cc, key=lambda c: (round(c["r"].y0), c["r"].x0))).strip() for cc in cell_chars]

    def cell_of(r):
        p = center(r)
        best = [i for i, c in enumerate(cells) if c.contains(p)]
        return min(best, key=lambda i: cells[i].get_area()) if best else None

    def right_bound(x, y):
        xs = [vx for vx, y0, y1 in vl if vx > x + 1 and y0 - 1 <= y <= y1 + 1]
        return min(xs) if xs else 540

    fields = []

    def add(kind, r, **kw):
        fields.append(dict(t=kind, r=R(r), **kw))

    for row in rows:
        y0 = min(c["r"].y0 for c in row) - 2
        y1 = max(c["r"].y1 for c in row) + 2
        ymid = (y0 + y1) / 2
        rowtext = "".join(c["c"] for c in row)

        # R4 체크박스: □ 하나마다. 누르는 범위는 뒤의 글자까지.
        boxes = [i for i, c in enumerate(row) if c["c"] == "□"]
        for n, i in enumerate(boxes):
            c = row[i]
            end = boxes[n + 1] if n + 1 < len(boxes) else len(row)
            lab, last_x = [], c["r"].x1
            for c2 in row[i + 1:end]:
                if c2["r"].x0 - last_x > 14 or c2["c"] in "(（":
                    break
                lab.append(c2)
                last_x = c2["r"].x1
            hit = fitz.Rect(c["r"].x0 - 2, c["r"].y0 - 2, last_x + 2, c["r"].y1 + 2)
            ci = cell_of(c["r"])
            grp = f"{ymid:.0f}-{ci}"
            cr = c["r"]
            sq = fitz.Rect(cr.x0 + cr.width * ratio[0], cr.y0 + cr.height * ratio[1],
                           cr.x0 + cr.width * ratio[2], cr.y0 + cr.height * ratio[3])
            add("check", cr, sq=R(sq), hit=R(hit), label="".join(c2["c"] for c2 in lab), grp=grp)

        for i, c in enumerate(row):
            nxt = row[i + 1]["r"].x0 if i + 1 < len(row) else None
            # R2 '항목 :' 뒤 빈칸
            if c["c"] in ":：":
                rb = right_bound(c["r"].x1, ymid)
                x0, x1 = c["r"].x1 + 1.5, (min(nxt, rb) if nxt else rb) - 1.5
                if x1 - x0 < 14:
                    continue
                lab = []
                for c2 in reversed(row[:i]):
                    if c2["c"] in ":：" or (lab and lab[-1]["r"].x0 - c2["r"].x1 > 10):
                        break
                    lab.append(c2)
                add("text", fitz.Rect(x0, y0, x1, y1), label="".join(c2["c"] for c2 in reversed(lab)).strip(), line=rowtext)
            # R6 '기타(      )' 괄호 안 빈칸
            if c["c"] in "(（" and i + 1 < len(row) and row[i + 1]["c"] in ")）" and nxt - c["r"].x1 >= 10:
                before = "".join(c2["c"] for c2 in row[max(0, i - 3):i])
                add("text", fitz.Rect(c["r"].x1 + 1, y0, nxt - 1, y1), label=before + "( )", line=rowtext)

        # R3 '년 월 일' 앞 빈칸 (같은 칸 안에 년·월·일 중 둘 이상). '(일기'의 '일'처럼 낱말 첫 글자는 빼고.
        def word_start(i):
            return i + 1 < len(row) and row[i + 1]["r"].x0 - row[i]["r"].x1 < 1 and "가" <= row[i + 1]["c"] <= "힣"
        ymd = [c for i, c in enumerate(row) if c["c"] in "년월일" and not word_start(i)]
        by_cell = {}
        for c in ymd:
            by_cell.setdefault(cell_of(c["r"]), []).append(c)
        for ci, group in by_cell.items():
            if len({c["c"] for c in group}) < 2:
                continue
            for c in group:
                prev = [c2 for c2 in row if c2["r"].x1 <= c["r"].x0 + 0.1]
                lo = cells[ci].x0 + 1 if ci is not None else c["r"].x0 - 45
                x0 = max(prev[-1]["r"].x1 + 1.5, lo) if prev else lo
                x0 = max(x0, c["r"].x0 - 60)
                if c["r"].x0 - 1 - x0 >= 4.5:
                    add("text", fitz.Rect(x0, y0, c["r"].x0 - 1, y1), label=c["c"], date=c["c"], line=rowtext)

    # R1 빈 칸 / R5 오른쪽에 단위·안내문만 있는 칸
    taken = [fitz.Rect(f["r"]) for f in fields if f["t"] != "check"] + [fitz.Rect(f["hit"]) for f in fields if f["t"] == "check"]
    def free(r):
        core = fitz.Rect(r.x0 + 3, r.y0 + 3, r.x1 - 3, r.y1 - 3)
        return not any(t.intersects(core) and (t & core).get_area() > 4 for t in taken)

    for ci, cell in enumerate(cells):
        inner = fitz.Rect(cell.x0 + 1.2, cell.y0 + 1.2, cell.x1 - 1.2, cell.y1 - 1.2)
        inside = cell_chars[ci]
        if not inside:
            if cell.height > 120 or cell.width < 7 or not free(cell):
                continue
            if any(cell.contains(p) for p in diag):
                if pno in DIAG_SPLIT:   # 왼쪽 위 / 오른쪽 아래
                    w, h = cell.width, cell.height
                    add("text", fitz.Rect(cell.x0 + 1.5, cell.y0 + 1, cell.x0 + w * 0.55, cell.y0 + h * 0.5), label="대각선 위")
                    add("text", fitz.Rect(cell.x0 + w * 0.45, cell.y0 + h * 0.5, cell.x1 - 1.5, cell.y1 - 1), label="대각선 아래")
                continue
            for part in split_rows(cell, hl):
                inner = fitz.Rect(part.x0 + 1.2, part.y0 + 1.2, part.x1 - 1.2, part.y1 - 1.2)
                add("area" if part.height >= 40 else "text", inner)
            continue
        tx0 = min(c["r"].x0 for c in inside)
        tx1 = max(c["r"].x1 for c in inside)
        txt = cell_text[ci]
        right_aligned = inner.x1 - tx1 < 8
        gap = tx0 - inner.x0
        r = fitz.Rect(inner.x0, inner.y0, tx0 - 1.5, inner.y1)
        if right_aligned and ((UNIT_RE.match(txt) and len(txt) <= 6 and gap >= 14) or gap >= 60) and free(r):
            add("text", r, unit=txt if UNIT_RE.match(txt) else None)
            continue
        # 'Φ', 'kVA', 'kV ㎎KOH/g' 처럼 단위만 있는 칸: 단위마다 앞에 빈칸
        tokens = []
        for row in rows_of(inside):
            tok = [row[0]]
            for c in row[1:]:
                if c["r"].x0 - tok[-1]["r"].x1 > 5:
                    tokens.append(tok); tok = []
                tok.append(c)
            tokens.append(tok)
        if tokens and all("".join(c["c"] for c in t) in UNIT_TOKENS for t in tokens):
            for t in tokens:
                tr = fitz.Rect(t[0]["r"])
                prev = [u for u in tokens if u is not t and abs(center(u[0]["r"]).y - center(tr).y) < 3 and u[-1]["r"].x1 <= tr.x0]
                x0 = max(u[-1]["r"].x1 for u in prev) + 1.5 if prev else inner.x0
                if tr.x0 - 1.5 - x0 >= 8:
                    add("text", fitz.Rect(x0, tr.y0 - 2, tr.x0 - 1.5, tr.y1 + 2), unit="".join(c["c"] for c in t))

    # 한 개만 고르는 체크 묶음(양호/불량 같은 것)만 서로 배타적으로
    ONE = {"양호", "불량", "없음", "있음", "유", "무", "맑음", "구름", "흐림", "비", "단면형", "양면형", "DC측", "AC측"}
    grps = {}
    for f in fields:
        if f["t"] == "check":
            grps.setdefault(f["grp"], []).append(f)
    for g in grps.values():
        if len(g) >= 2 and all(f["label"] in ONE for f in g):
            for f in g:
                f["ex"] = 1
    for f in fields:
        if f["t"] == "check" and "ex" not in f:
            del f["grp"]

    for x0, y0, x1, y1, lab in manual(pno):
        add("area" if y1 - y0 >= 40 else "text", fitz.Rect(x0, y0, x1, y1), label=lab)

    # 같은 자리를 두 규칙이 겹쳐 잡은 칸('점검일자 : _년'의 ':' 뒤 = '년' 앞)은 하나만
    texts = [f for f in fields if f["t"] != "check"]
    drop = set()
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            ra, rb = fitz.Rect(a["r"]), fitz.Rect(b["r"])
            ov = (ra & rb).get_area() if ra.intersects(rb) else 0
            if ov > 0.6 * min(ra.get_area(), rb.get_area()):
                drop.add(id(a) if b.get("date") and not a.get("date") else id(b))
    fields[:] = [f for f in fields if id(f) not in drop]

    # 예시값 → placeholder / 기본값
    for s in samples:
        p = center(s["r"])
        hits = [f for f in fields if f["t"] != "check" and fitz.Rect(f["r"][0] - 2, f["r"][1] - 2, f["r"][2] + 2, f["r"][3] + 2).contains(p)]
        if hits:
            f = min(hits, key=lambda f: fitz.Rect(f["r"]).get_area())
            f["default" if s["default"] else "ph"] = s["text"]

    # 칸 이름: 같은 열 위쪽 글자 칸 · 같은 줄 왼쪽 글자 칸
    for f in fields:
        if f["t"] == "check" or f.get("label"):
            continue
        r = fitz.Rect(f["r"])
        p = center(r)
        left = [i for i, c in enumerate(cells) if c.x1 <= r.x0 + 2 and c.y0 - 1 <= p.y <= c.y1 + 1 and cell_text[i]
                and not UNIT_RE.match(cell_text[i])]
        up = [i for i, c in enumerate(cells) if c.y1 <= r.y0 + 2 and c.x0 - 1 <= p.x <= c.x1 + 1 and cell_text[i]]
        parts = []
        if up:
            parts.append(cell_text[max(up, key=lambda i: cells[i].y1)])
        if left:
            parts.append(cell_text[max(left, key=lambda i: cells[i].x1)])
        f["label"] = " · ".join(parts)[:40]

    for f in fields:
        if f.get("unit") is None:
            f.pop("unit", None)
    fields.sort(key=lambda f: (round(f["r"][1] / 3), f["r"][0]))
    return fields


def tag(fields, pno):
    """여러 장에 똑같이 들어가는 칸: 새 장을 만들 때 마지막 값으로 미리 채운다."""
    for f in fields:
        line = f.get("line", "").replace(" ", "")
        lab = f.get("label", "").replace(" ", "")
        if "(서명)" in line or "서명또는인" in line:
            m = {"소속(담당분야)": "sig.org", "직책": "sig.title", "성명": "sig.name", "작성자": "writer.name"}
            if lab in m:
                f["tag"] = m[lab]
        if f.get("date") and re.fullmatch(r"년월일", line):
            f["tag"] = "date." + f["date"]
        if pno == 4:
            m = {"사업장명": "site.name", "대표자명": "site.ceo", "설치주소": "site.addr", "설치용량": "site.kw",
                 "한전계통연계전압": "site.volt"}
            if lab in m:
                f["tag"] = m[lab]
            if 555 < f["r"][1] < 600:
                m2 = {"상호": "writer.co", "성명": "writer.name", "전화번호": "writer.tel", "E-mail": "writer.mail"}
                if lab in m2:
                    f["tag"] = m2[lab]


def dbg_page(page, fields, path):
    d = fitz.open()
    d.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
    p = d[0]
    for f in fields:
        r = fitz.Rect(f["r"])
        if f["t"] == "check":
            p.draw_rect(fitz.Rect(f["hit"]), color=(1, 0, 0), width=0.5)
        else:
            col = (0, 0.6, 0) if f.get("tag") else ((0.6, 0, 0.8) if f["t"] == "area" else (0, 0.3, 1))
            p.draw_rect(r, color=col, fill=col, fill_opacity=0.15, width=0.5)
            if f.get("ph") or f.get("default"):
                p.insert_text((r.x0 + 1, r.y1 - 2), "*", fontsize=6, color=(1, 0, 1))
    p.get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).save(path)


def main():
    src = fitz.open(SRC)
    ratio = box_ratio(src)
    out = fitz.open()
    for pno, _, _ in SHEETS:
        out.insert_pdf(src, from_page=pno - 1, to_page=pno - 1)
    os.makedirs(os.path.join(APP, "bg"), exist_ok=True)
    meta = []
    for i, (pno, short, title) in enumerate(SHEETS):
        page = out[i]
        samples, filled = clean(page, pno, ratio)
        fields = build_page(page, pno, samples, filled, ratio)
        tag(fields, pno)
        tpl = f"p{pno:02d}"
        # 칸 이름 = 칸 왼쪽 위 좌표. 규칙을 고쳐 다시 만들어도 이미 적은 값이 다른 칸으로 밀리지 않게.
        for f in fields:
            f["id"] = f"{f['t'][0]}{round(f['r'][0])}_{round(f['r'][1])}"
            f.pop("line", None)
        ids = [f["id"] for f in fields]
        assert len(ids) == len(set(ids)), f"{tpl}: 칸 이름 중복"
        page.get_pixmap(matrix=fitz.Matrix(BG_ZOOM, BG_ZOOM)).save(os.path.join(APP, "bg", f"{tpl}.png"))
        meta.append(dict(tpl=tpl, page=i, short=short, title=title,
                         w=round(page.rect.width, 1), h=round(page.rect.height, 1), fields=fields))
        if DBG:
            dbg_page(page, fields, os.path.join(DBG, f"{tpl}.png"))
        kinds = {}
        for f in fields:
            kinds[f["t"]] = kinds.get(f["t"], 0) + 1
        print(tpl, short, kinds, flush=True)
    out.save(os.path.join(APP, "template.pdf"), garbage=4, deflate=True)
    with open(os.path.join(APP, "fields.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, separators=(",", ":"))


main()
