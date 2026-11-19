#!/usr/bin/env python3
"""논문 PDF의 페이지·단·영역을 PNG 로 렌더링한다.

쓰는 이유 두 가지:
  1) 수식 확인 — 텍스트 추출은 분수/적분/위아래첨자를 조각내서 순서를 뒤집는다.
     설명하기 전에 눈으로 봐야 원문 그대로 옮길 수 있다.
  2) Figure 추출 — 벡터 그림은 임베드된 래스터가 없어 영역 렌더링이 유일한 방법이다.

사용:
    python3 pdf_render.py paper.pdf --pages 2-5 --half both -o out/
    python3 pdf_render.py paper.pdf --pages 6 --half L --crop 0.55,0.84 -o out/
    python3 pdf_render.py paper.pdf --pages 1 -o out/            # 페이지 전체
"""
import argparse, os, sys

try:
    import pymupdf
except ImportError:
    sys.exit("pymupdf 가 없다. `pip install PyMuPDF` 후, 인터프리터 불일치 시 "
             "pip 이 설치한 쪽(예: /usr/local/bin/python3.13)으로 실행할 것.")


def parse_pages(spec, n):
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
    ap.add_argument("--pages", required=True, help="1-based. 예: 2-5 또는 1,3")
    ap.add_argument("--half", choices=["L", "R", "both", "none"], default="none",
                    help="2단 논문의 어느 단을 자를지")
    ap.add_argument("--crop", help="세로 구간 비율 'y0,y1' (0~1). 예: 0.55,0.84")
    ap.add_argument("--zoom", type=float, default=3.2,
                    help="수식은 3.2 이상 권장. 너무 키우면 파일이 커진다")
    ap.add_argument("-o", "--out", default=".")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    doc = pymupdf.open(a.pdf)
    y0f, y1f = (0.0, 1.0)
    if a.crop:
        y0f, y1f = (float(v) for v in a.crop.split(","))

    halves = ["L", "R"] if a.half == "both" else ([a.half] if a.half != "none" else ["F"])
    for pno in parse_pages(a.pages, len(doc)):
        page = doc[pno]
        r = page.rect
        mid = r.width / 2
        top, bot = r.y0 + y0f * r.height, r.y0 + y1f * r.height
        for h in halves:
            if h == "L":
                clip = pymupdf.Rect(r.x0, top, mid + 8, bot)
            elif h == "R":
                clip = pymupdf.Rect(mid - 8, top, r.x1, bot)
            else:
                clip = pymupdf.Rect(r.x0, top, r.x1, bot)
            pix = page.get_pixmap(matrix=pymupdf.Matrix(a.zoom, a.zoom), clip=clip)
            name = f"p{pno + 1}{'' if h == 'F' else h}.png"
            path = os.path.join(a.out, name)
            pix.save(path)
            print(f"{path}  {pix.width}x{pix.height}  {os.path.getsize(path) // 1024} KB")


if __name__ == "__main__":
    main()
