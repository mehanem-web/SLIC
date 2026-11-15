# SLIC: Site Lead Installation Check

A tablet form for the site lead installation check. The inspector taps through the
checklist and finishes with two files to put in Box:

- **a PDF report**: score, failed checks with notes and photos, and the full checklist
- **the Excel sheet**: the existing workbook, with this check filled into the first
  inspection columns. The workbook's layout, checkboxes and formulas are not changed.

Photos taken in the form are also saved straight away as their own files, named after
the check they belong to. Answers, notes and photos are kept on the tablet as the form
is filled in, so a flat battery or a closed browser loses nothing.

The site works offline after the first visit and can be added to the home screen.
Nothing is sent anywhere: the files are built on the tablet.

## Layout

| Path | What it is |
| --- | --- |
| `src/form.html` | The form: markup, styles and script |
| `src/checklist.json` | The categories and checks, read from the workbook |
| `src/workbook-template.json` | The workbook the Excel export is built from, with personal details removed |
| `vendor/` | fflate (zip) and jsPDF, with their licences |
| `tools/import_workbook.py` | Reads a new version of the workbook into `src/` |
| `tools/build.py` | Builds the site into `docs/` |
| `tests/smoke_test.py` | End-to-end test of the built site |
| `docs/` | The built site, served by GitHub Pages |

## Changing the checklist

1. Get the current workbook from Box. Do not add it to this repository.
2. `python tools/import_workbook.py path/to/workbook.xlsx`
3. `python tools/build.py`
4. `python tests/smoke_test.py`
5. Commit `src/` and `docs/`.

The import removes the names on the Summary tab, the sample inspector, the document's
author fields and Windows file paths before anything is written to `src/`, and stops
if a name is still present.

## Hidden office step

`#merge` at the end of the address opens a screen for adding saved check files into the
master workbook on a computer. It is not linked from the form.

## Status

Prototype, hosted here until it is approved and moved to a company host. To move it,
copy the contents of `docs/` to any web server that serves HTTPS.
