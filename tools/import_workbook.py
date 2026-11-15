"""Read the checklist workbook and write the two inputs the form is built from.

    python tools/import_workbook.py path/to/Quality_Inspections_SOP.xlsx

Writes src/checklist.json (the categories and checks) and src/workbook-template.json
(the workbook itself, used to produce the Excel export). Personal details are removed
from the template on the way in: the names on the Summary tab, the sample inspector,
the document's author fields, and Windows file paths. Never commit the original .xlsx.
"""
import base64, io, json, re, struct, sys, zipfile
import openpyxl

src = sys.argv[1]
wb = openpyxl.load_workbook(src)
ws = wb["QA Checklist"]
merged = {}
for rng in ws.merged_cells.ranges:
    if rng.min_col == 1 and rng.max_col == 1:
        for r in range(rng.min_row, rng.max_row + 1):
            merged[r] = rng.min_row
cats, cur = [], None
for r in range(10, 107):
    b = ws.cell(r, 2).value
    if not b or not str(b).strip():
        continue
    top = merged.get(r, r)
    name = (ws.cell(top, 1).value or "").strip()
    if cur is None or cur["top"] != top:
        cur = {"top": top, "name": name, "items": []}
        cats.append(cur)
    c = ws.cell(r, 3).value
    cur["items"].append({"row": r, "check": " ".join(str(b).split()), "expected": " ".join(str(c).split()) if c else ""})
for c in cats:
    del c["top"]
footnotes = [str(ws.cell(r, 1).value).strip() for r in (108, 110) if ws.cell(r, 1).value]
checklist = {"categories": cats, "footnotes": footnotes}

parts = {}
for n in zipfile.ZipFile(src).namelist():
    raw = zipfile.ZipFile(src).read(n)
    try:
        t = raw.decode("utf-8")
        assert t.encode("utf-8") == raw
        parts[n] = {"t": t}
    except Exception:
        parts[n] = {"b": base64.b64encode(raw).decode()}

# ---- remove personal details ----
s1 = parts["xl/worksheets/sheet1.xml"]["t"]
idx = set()
for col, row, attrs, inner in re.findall(r'<c r="([A-C])(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', s1):
    if int(row) >= 2 and 't="s"' in attrs:
        idx.add(int(re.search(r"<v>(\d+)</v>", inner).group(1)))
ss = parts["xl/sharedStrings.xml"]["t"]
items = re.findall(r"<si>.*?</si>|<si/>", ss, re.S)
text = lambda si: re.sub(r"<[^>]+>", "", si)
names = sorted(text(items[i]).strip() for i in idx)
sample = [i for i, si in enumerate(items) if text(si).strip() == "Josh T."]
idx.update(sample)
for sh in ("xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"):
    used = set(int(x) for x in re.findall(r't="s"><v>(\d+)</v>', parts[sh]["t"]))
    clash = (used & idx) - set(sample)
    assert not clash, ("summary strings reused elsewhere", sh, clash)
n = [0]
def blank(m):
    i = n[0]; n[0] += 1
    return "<si><t/></si>" if i in idx else m.group(0)
parts["xl/sharedStrings.xml"]["t"] = re.sub(r"<si>.*?</si>|<si/>", blank, ss, flags=re.S)

wb = parts["xl/workbook.xml"]["t"]
wb2 = re.sub(r"<mc:AlternateContent.*?</mc:AlternateContent>", "", wb, count=1, flags=re.S)
assert wb2 != wb and "absPath" not in wb2
parts["xl/workbook.xml"]["t"] = wb2

core = parts["docProps/core.xml"]["t"]
core = re.sub(r"<dc:creator>.*?</dc:creator>", "<dc:creator></dc:creator>", core)
core = re.sub(r"<cp:lastModifiedBy>.*?</cp:lastModifiedBy>", "<cp:lastModifiedBy></cp:lastModifiedBy>", core)
parts["docProps/core.xml"]["t"] = core

# the leftover data query holds a full Windows path with a user name: shorten it
raw = base64.b64decode(parts["customXml/item1.xml"]["b"]).decode("utf-16")
m = re.search(r"(<DataMashup[^>]*>)(.*?)(</DataMashup>)", raw, re.S)
blob = base64.b64decode(m.group(2))
ver, plen = struct.unpack("<II", blob[:8])
zin = zipfile.ZipFile(io.BytesIO(blob[8:8 + plen]))
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():
        data = zin.read(info.filename)
        if info.filename.endswith(".m"):
            t = data.decode("utf-8")
            t2 = re.sub(r'File\.Contents\("[^"]*"\)', 'File.Contents("C:\\\\New Text Document.txt")', t)
            assert t2 != t
            data = t2.encode("utf-8")
        zout.writestr(info.filename, data)
pkg = buf.getvalue()
blob2 = struct.pack("<II", ver, len(pkg)) + pkg + blob[8 + plen:]
raw2 = raw[:m.start(2)] + base64.b64encode(blob2).decode() + raw[m.end(2):]
parts["customXml/item1.xml"]["b"] = base64.b64encode(b"\xff\xfe" + raw2.encode("utf-16-le")).decode() if raw.startswith("\ufeff") is False else base64.b64encode(raw2.encode("utf-16")).decode()


blob_text = json.dumps(parts, ensure_ascii=False).lower()
leftover = [n for n in names if len(n) > 3 and re.search(r"(?<![a-z])" + re.escape(n.lower()) + r"(?![a-z])", blob_text)]
assert not leftover, ("names still present", leftover)
json.dump(checklist, open("src/checklist.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump(parts, open("src/workbook-template.json", "w", encoding="utf-8"), ensure_ascii=False)
print("categories:", len(cats), "| checks:", sum(len(c["items"]) for c in cats), "| names removed:", len(names))
