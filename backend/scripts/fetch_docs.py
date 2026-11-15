"""Download + extract transcripts (last N) and the latest annual report for given symbols."""
import sys, logging, json
logging.basicConfig(level=logging.WARNING)
from app.sources import screener, pdf
syms = sys.argv[1:] or ["DIXON", "PERSISTENT", "VBL", "KAYNES"]
for s in syms:
    sc, src = screener.load_screener(s)
    if not sc: print(s, "no screener"); continue
    docs = sc["documents"]
    for t in docs["transcripts"][:6]:
        p = pdf.pages(s, t["url"]); print(s, "transcript", t["when"], len(p) if p else None, flush=True)
    for ar in docs["annual_reports"][:1]:
        p = pdf.pages(s, ar["url"]); print(s, "AR", ar["fy"], len(p) if p else None, flush=True)
