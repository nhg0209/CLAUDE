#!/usr/bin/env python3
"""2단 논문 PDF의 본문을 컬럼 순서대로 추출한다.

markitdown 은 2단 조판을 왼쪽 줄 -> 오른쪽 줄 번갈아 뽑아서 문단이 교차한다.
이 스크립트는 블록 중심 x 좌표로 좌/우단을 나눈 뒤 각 단을 y 순서로 정렬한다.

사용:
    python3 pdf_columns.py paper.pdf                 # 2단 가정, stdout
    python3 pdf_columns.py paper.pdf -o cols.txt
    python3 pdf_columns.py paper.pdf --single        # 1단 논문
    python3 pdf_columns.py paper.pdf --pages 2-5
"""
import argparse, sys

try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf 가 없다. `pip install PyMuPDF` 후, 인터프리터 불일치 시 "
             "pip 이 설치한 쪽(예: /usr/local/bin/python3.13)으로 실행할 것.")


def parse_pages(spec, n):
    if not spec:
        return range(n)
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a) - 1, int(b)))
        else:
            out.append(int(part) - 1)
    return [p for p in out if 0 <= p < n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out")
    ap.add_argument("--single", action="store_true", help="1단 조판")
    ap.add_argument("--pages", help="예: 2-5 또는 1,3,7 (1-based)")
    ap.add_argument("--full-width-ratio", type=float, default=0.75,
                    help="이 비율보다 넓은 블록은 전폭(제목/표)으로 따로 묶는다")
    a = ap.parse_args()

    doc = pymupdf.open(a.pdf)
    buf = []
    for pno in parse_pages(a.pages, len(doc)):
        page = doc[pno]
        W = page.rect.width
        mid = W / 2
        full, left, right = [], [], []
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, txt, _, btype = b[:7]
            if btype != 0 or not txt.strip():
                continue
            if a.single:
                left.append((y0, x0, txt))
            elif (x1 - x0) > a.full_width_ratio * W:
                full.append((y0, x0, txt))
            elif (x0 + x1) / 2 < mid:
                left.append((y0, x0, txt))
            else:
                right.append((y0, x0, txt))
        buf.append(f"\n\n=== PAGE {pno + 1} ===\n")
        groups = [("FULLWIDTH", full), ("LEFT COL", left), ("RIGHT COL", right)]
        if a.single:
            groups = [("BODY", left)]
        for label, grp in groups:
            if not grp:
                continue
            buf.append(f"\n--- p{pno + 1} {label} ---\n")
            for _, _, txt in sorted(grp):
                buf.append(txt.rstrip() + "\n")

    text = "".join(buf)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"wrote {a.out} ({len(text)} chars, {text.count('=== PAGE')} pages)")
    else:
        print(text)


if __name__ == "__main__":
    main()
