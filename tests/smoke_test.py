"""End-to-end check of the built site in docs/, offline included.

    python tests/smoke_test.py

Needs Python Playwright and a Chrome or Chromium browser (set CHROME to its path if it
is not at /usr/bin/google-chrome). Serves docs/ on localhost, fills in a check with a
note and a photo, goes offline, reloads, finishes, and checks the Excel file it saves
against the workbook template: only the first inspection block may change, the
checkboxes must stay checkboxes, and the score formulas must survive.
"""
import asyncio, functools, http.server, io, json, os, re, tempfile, threading, zipfile
from playwright.async_api import async_playwright
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")

def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    handler = functools.partial(Quiet, directory=os.path.join(ROOT, "docs"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def check_xlsx(data):
    tpl = json.load(open(os.path.join(ROOT, "src", "workbook-template.json"), encoding="utf-8"))
    z = zipfile.ZipFile(io.BytesIO(data))
    assert z.testzip() is None
    assert sorted(z.namelist()) == sorted(tpl), "the export must contain exactly the template's parts"
    pat = r'<c r="([A-Z]+\d+)"[^>]*?(?:/>|>.*?</c>)'
    old, new = tpl["xl/worksheets/sheet2.xml"]["t"], z.read("xl/worksheets/sheet2.xml").decode("utf-8")
    co = dict((m.group(1), m.group(0)) for m in re.finditer(pat, old, re.S))
    cn = dict((m.group(1), m.group(0)) for m in re.finditer(pat, new, re.S))
    cols = {re.match(r"[A-Z]+", k).group(0) for k in set(co) | set(cn) if co.get(k) != cn.get(k)}
    assert cols <= {"D", "E", "F", "G"}, cols
    assert re.sub(pat, "", old, flags=re.S) == re.sub(pat, "", new, flags=re.S), "only cell contents may change"
    assert ' s="2" t="b"><v>1</v>' in cn["E19"], "a failed check must stay a ticked checkbox"
    assert "<f>COUNTIF(D10:D106, TRUE)</f>" in cn["D8"] and "<f>D8/(D8+E8)</f>" in cn["G8"]
    assert "Zip ties used" in cn["G19"]
    for name, part in tpl.items():
        if name not in ("xl/worksheets/sheet2.xml", "xl/workbook.xml") and "t" in part:
            assert z.read(name).decode("utf-8") == part["t"], name

async def main():
    srv = serve()
    url = "http://127.0.0.1:%d/" % srv.server_address[1]
    tmp = tempfile.mkdtemp()
    photo = os.path.join(tmp, "photo.jpg")
    Image.new("RGB", (4000, 3000), (60, 110, 160)).save(photo, quality=90)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = await ctx.new_page()
        errors, downloads = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("download", lambda d: downloads.append(d))
        await page.goto(url)
        await page.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
        await page.fill("#f-lead", "Test Lead"); await page.fill("#f-inspector", "Tester")
        await page.click("#f-ann-yes"); await page.click("#f-mode-in")
        await page.fill("#f-date", "2026-11-14"); await page.fill("#f-job", "NA"); await page.fill("#f-evm", "50")
        await page.click("#b-10-p"); await page.click("#b-19-f"); await page.fill("#note-19", "Zip ties used")
        await page.set_input_files("#pin-19", photo)
        await page.wait_for_function("document.querySelectorAll('#row-19 .thumb').length === 1")
        await page.click("#finish-top")
        assert await page.is_hidden("#fin-save"), "Finish must refuse while checks are unanswered"
        await page.click("#fin-back")

        await ctx.set_offline(True)
        await page.reload()
        await page.wait_for_function("document.querySelectorAll('#row-19 .thumb').length === 1")
        assert await page.input_value("#note-19") == "Zip ties used"
        for i in range(16):
            if await page.is_visible("#allna-%d" % i):
                await page.click("#allna-%d" % i)
        downloads.clear()
        await page.click("#finish-top"); await page.click("#fin-save")
        await page.wait_for_function("document.getElementById('fin-save').textContent === 'Saved'", timeout=20000)
        for _ in range(50):
            if len(downloads) >= 2:
                break
            await page.wait_for_timeout(100)
        names = sorted(d.suggested_filename for d in downloads)
        assert names == ["SLIC_Test-Lead_2026-11-14.xlsx", "SLIC_Test-Lead_2026-11-14_Report.pdf"], names
        for d in downloads:
            path = os.path.join(tmp, d.suggested_filename)
            await d.save_as(path)
            data = open(path, "rb").read()
            if path.endswith(".xlsx"):
                check_xlsx(data)
            else:
                assert data[:5] == b"%PDF-" and len(data) > 20000
        assert not errors, errors
        await browser.close()
    srv.shutdown()
    print("ok: form, photo, offline reload, finish, report and Excel export all pass")

asyncio.run(main())
