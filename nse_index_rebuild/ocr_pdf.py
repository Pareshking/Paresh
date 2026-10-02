import subprocess, sys, glob, tempfile
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
def ocr_pdf(path, dpi=170):
    out = []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", path, f"{d}/p"], check=True)
        for img in sorted(glob.glob(f"{d}/p-*.png")):
            res, _ = engine(img)
            boxes = []
            for box, text, conf in (res or []):
                ys = [p[1] for p in box]; xs = [p[0] for p in box]
                boxes.append(((min(ys) + max(ys)) / 2, min(xs), text))
            boxes.sort()
            rows = []
            for y, x, t in boxes:
                if rows and abs(rows[-1][0] - y) < 12: rows[-1][1].append((x, t))
                else: rows.append([y, [(x, t)]])
            for y, items in rows:
                items.sort()
                out.append("   ".join(t for x, t in items))
            out.append("")
    return "\n".join(out)
if __name__ == "__main__":
    print(ocr_pdf(sys.argv[1]))
