"""
update_to_v7.py  -  upgrades your Exam Buddy folder from version 5 to version 7, IN PLACE.

How to use (run it ONCE):
  1. Copy this file into your exam_buddy folder, next to main.py.
  2. In the VS Code terminal, inside that folder, run:    python update_to_v7.py

What is new in version 7 (it also contains everything from version 6, so run only this one):
  - Applications page: pick your exam from a list (JEE, NEET, NDA, SSC, BITSAT ...) with its documents.
  - Overview: a "Completed" box with exam names.   - Admin: the useless "Documents" link is hidden.
  - Privacy: consent checkbox + privacy notice, "Delete my data", automatic deletion of documents 30 days
    after an application is Completed, Aadhaar shown as XXXX XXXX 1234 to admin (reveal is logged),
    activity log, login attempt limit (5 wrong tries = 10 minute wait).
  - Workflow: new statuses (Documents Verified, Filled, Awaiting OTP), copy-ready OTP message,
    "Request document" button, search and filter for admin.
  - Checks: warns about name or date-of-birth mismatch, wrong Aadhaar checksum, bad phone or pincode.
What it does: saves a backup of every file it changes, writes main.py, static/app.js, static/styles.css,
static/exams.js, and makes small edits in static/index.html. It checks everything and puts your
old files back if something is wrong. It NEVER touches your database or uploads.
"""
import base64
import hashlib
import shutil
import sys
import zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "main.py": (
        "65a108e1ffe0c376d61ccac9009f9399f37eef55d630ea211f43c456824b641b",
        "eNrdfWt320ay4Hf+ClxkcwwkMC3Jjzjay0lkiZ7RHVnSSvIkWVrLAxKghIgkOAAoWdHhf7/16CceJGQrO7ObnCODQD+qq6urq6qr"
        "qpPZIs0KJ807CT9lsXz6PU/n8jlfjhZZOo5zVS6/V4/FdRaHUTK/6kyydOYss+k0GXUXYZbHjigC7+i3rLJcJpF8vp6FY/Uc5tdQ"
        "WXUSj7O40H3+c5oU8UvuZhEWWFT2cAo/+UMUFnGRzFTf8nfg4N8onhYhP/6RzmOuUtwvAHxZ4WRRJOk8nHb44yTMi3CRyK/v4efe"
        "6WHg/O3i4rT/eRxT6cA5iBfxPMoD5+NimobR+2QKPYq/aTaD8oCkOLPa7GZxvkjneZyr1qHCmXhpF4W/RTKewHdV+JxeYZVc4OQ+"
        "CufwShZ4F+bxhxSGjJDE00iMCJrKpnFRxN1xOh8vsyyej+9lnWw5HybzIU/qIk0lGuLPRRaOizTTsB72jw7OYeQn+8OL30778Pj+"
        "8Kg/PDk++k2+6P96cbY3lCVFG8MJAgOowi6GBbztdM5OTi6cHk2jNxziMIdDH/GTTm9jz0dyiudF5+Dd8HTv4m9Qkiq8cNz4czgb"
        "jpZRdN+NRm7n4+nRyd7B8ODwzCizpCnJ3c75xd7F4X7pK2PWrNqd3URJ5sWfk7wYpje9i2wZ+51OuFhANUEAXpEU07jn9qF/5x32"
        "78BbN3Bu4ywHiui5292t7pbrY7XuLF3OC899IfoKzLnzoK8YMXvf0/D5gTMPZ9C+qOF3Puz9OhQgvvvton8OoLx1vnO2t3ZeiX86"
        "e0dHJ7/0D4aA9f7x+eHJMRZ6cLuL+RV06XZ/X8h/Y364i0cLelhEE3dF6Pl43udaxylRWFbEERY5SMfLGUxB7vwjzhKYQXp7OHdO"
        "s/QK5inHn8dxHOXOfprhgAAJ+O4MJvnemaSZcxbfJvEdvoNxT7GBjmP85+7dhUmBC/Hk4hRL7aezBdAp97Qfzscx1Vp1zvowvgsY"
        "3/Bg7zeENgHkpnk3nt8mWTrvXsWA6/67oV0OW3kJE+JDX984kRoPUJYDawQ7Al6W5M4snN8D27iHT5MizkxAOp0onjjz9G6Y5Knn"
        "79IAgEcts7liNF347EkG010WY78LhQEBs7DwfG4BFt4cUCRbwJ8wDMHguvKroHZflelm0POEluG9Uf4svdNF4s/xeFnEnnt6tvfX"
        "D3uI+Ti5mg9vYhhQzzk5dn0TaqzDMCHzHS7CPL9Ls8iTD7vALrLAycNpsatY42B0X8T5JTR3DGP0ned/wVI8FiyJsOE/MOmCh3eL"
        "9CaeD6met/2GQYiSqzjHwoLvdxejm2iyM8QtwXPz63Dn9RuYNQkKzO8YuJnnMziBs/Nqa7i1tWWNB790r+PPnu9877j/w4W/3A2/"
        "5KHeIgnfNw8W8BvzDxrbCNggD67I7ncV0WJXQ2g1ED3gM46canfzBUyOBxAEzrav6ozDeZQgpXzJqAl7XWTHOBbZva8RIcYoOxMo"
        "wYaBpmbIQ4cMqqfgMIHnmjFtao7a23bL7b0Pp7A7ESKTeVIMo5Gk47ukuNa07YS5E4109WgkiTMfZ8kCkOO66uP+WX/vou9c7L07"
        "6juH751jYM79Xw/PL84doPfkNinuh9P0yvEsnpFEzuHxRf+v/TPn9Ozww97Zb87f+785ex8vTg6PockPsP5tLhMWzgXwR2r/+OPR"
        "UekrLq2hbrXuK/JlaqPyEZC1tvEFkMQ4xGKNXURxESZTbuWg/37v49GF8+yZKuL/zzYIW+awB301ptQ4G4YTzxSksoDz8fjwf33s"
        "2+UkIQ+R3tc1mKXTUocaBXmxjIBbP7NrAGsBEo6G5Ul9JL5AAMMtu4wyZlkaagNvNhiIb2NGNfhn/ff9s/7xfl/MiZdEPnBgGNYR"
        "bE3O/t75/t5B/08ZE8jrLCx6a0E1aeFLoF1cwwZQJtfSgGDpri+BfGiYToajJCuu1xddLqKnwI7e/b92lTzp3KdZcpXA/jrctPZ4"
        "j9lYjORo0G7Wt5X8EfPGXBlEacGz+B6zzL5h0p+Gig2W+W82VaR3bGSRWEhwlybO9qw8s2GxzJsKG0J5qd48xQn8ojn5U1ZYvlyg"
        "ljjM4n8uQbz4N5s9MGj8DjLKOjzMYNrCqw2rcN1cnYBB4CtWBQhHhiSX3oHAqAUozz2H0e1fIB7fn518EFv+L38DTIiNuef8BFKk"
        "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"
        "AA=="
    ),
    "static/app.js": (
        "a31f338455b0e1cda671f389cfcceeaf1edeb4b35a2746df4e530416dceabb86",
        "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"
    ),
    "static/styles.css": (
        "75f8699ff5acd28a3f16b6c17a0724a04c75df8083a6905ff21d159d5f2f12ed",
        "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"
        "509FdrKd00/SPf0fN0wytQ=="
    ),
    "static/exams.js": (
        "aad90371f06d056bc782075aaaf016aa584a44a6388f5e029aa472547a2793f4",
        "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"
    ),
}

# (old text, new text) edits for static/index.html. Skipped if the edit is already there.
INDEX_EDITS = [
    ('<script src="/static/app.js"></script>',
     '<script src="/static/exams.js"></script>\n  <script src="/static/app.js"></script>'),
    ('<button class="side-link" data-page="documents" onclick="openJee()">',
     '<button id="docs-nav" class="side-link" data-page="documents" onclick="openJee()">'),
    ('<small>Not yet completed</small></div></div>',
     '<small>Not yet completed</small></div><div class="metric-card"><span class="metric-icon mint">\u2605</span><span class="metric-label">Completed</span><strong id="metric-completed">0</strong><small id="metric-completed-names">No exam completed yet</small></div></div>'),
    ('<div class="panel-heading"><div><h3>Application assistance</h3><p>Create a preparation record and track your progress.</p></div></div><form',
     '<div class="panel-heading"><div><h3>Application assistance</h3><p>Pick your exam to see the documents you need, then create your record.</p></div></div><div id="exam-picker"></div><form'),
]
ALREADY = ['src="/static/exams.js"', 'id="docs-nav"', 'id="metric-completed"', 'id="exam-picker"']
INDEX_EDITS += [('          <p id="auth-error" class="form-error"></p>', '          <label id="consent-label" class="consent hidden"><input id="auth-consent" type="checkbox"> <span>I have read the <a href="#" onclick="openPrivacy();return false;">privacy notice</a> and I agree that Exam Buddy stores my documents to help with my application.</span></label>\n          <p id="auth-error" class="form-error"></p>'), ('  <script src="/static/exams.js"></script>', '  <div id="privacy-modal" class="modal hidden" onclick="if(event.target===this)closePrivacy()"><div class="modal-box">\n    <h3>Privacy notice</h3>\n    <ul>\n      <li><b>What we store:</b> your name, email, the documents you upload (Aadhaar, marksheets, photo, signature) and the details read from them.</li>\n      <li><b>Why:</b> only to fill your exam application form for you. We do not sell or share your data.</li>\n      <li><b>Who can see it:</b> you, and the Exam Buddy staff who fill your form. Staff see your Aadhaar number masked (XXXX XXXX 1234) and every time they open your documents is written to a log.</li>\n      <li><b>How long:</b> your documents and details are deleted automatically <span id="retention-days">30</span> days after your application is marked Completed.</li>\n      <li><b>Your control:</b> you can delete all your documents and details at any time from My profile, using "Delete my data".</li>\n      <li><b>Your responsibility:</b> check every detail before confirming. Exam Buddy is not an official exam portal. OTP, CAPTCHA, payment and final submission are always done with you.</li>\n    </ul>\n    <button class="btn btn-primary" onclick="closePrivacy()">Close</button>\n  </div></div>\n  <script src="/static/exams.js"></script>'), ('<div class="form-actions"><button class="btn btn-primary" type="submit">Save profile</button></div></form>', '<div class="form-actions"><button class="btn btn-primary" type="submit">Save profile</button></div></form><div class="privacy-box"><h4>Privacy &amp; data</h4><p class="muted tiny">Your documents are deleted automatically 30 days after an application is marked Completed. You can also delete everything yourself.</p><div class="inline-actions"><button class="btn btn-outline btn-sm" onclick="openPrivacy()">Read privacy notice</button><button class="btn btn-danger btn-sm" onclick="deleteMyData()">Delete my data</button></div></div>'), ('<div id="admin-applications" class="record-list"></div></div>', '<div class="inline-actions"><input id="admin-search" class="grow" type="search" placeholder="Search by student, email or exam" oninput="renderAdminApps()"><select id="admin-filter" onchange="renderAdminApps()"></select></div><div id="admin-applications" class="record-list"></div></div><div class="panel"><div class="panel-heading"><div><h3>Activity log</h3><p>Who opened or changed what. Latest 100 entries.</p></div></div><div id="admin-activity" class="table-wrap"></div></div>')]
ALREADY += ['id="consent-label"', 'id="privacy-modal"', 'class="privacy-box"', 'id="admin-search"']



def main():
    if not (HERE / "main.py").exists() or not (HERE / "static").is_dir():
        print("STOP: put update_to_v7.py inside your exam_buddy folder (the one that contains main.py and the static folder).")
        sys.exit(1)
    backup = HERE / ("backup_before_v7_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    touched = []   # (relative path, existed before)
    print("Updating Exam Buddy to version 7 ...")
    try:
        index = HERE / "static" / "index.html"
        text = index.read_text(encoding="utf-8")
        for (old, new), marker in zip(INDEX_EDITS, ALREADY):
            if marker in text:
                continue
            if old not in text:
                raise RuntimeError("static/index.html is different from what I expected (could not find: %s...). Send me this message." % old[:50])
            text = text.replace(old, new, 1)
        (backup / "static").mkdir(parents=True, exist_ok=True)
        shutil.copy2(index, backup / "static" / "index.html")
        touched.append(("static/index.html", True))
        index.write_text(text, encoding="utf-8")
        print("  edited   static/index.html")

        for rel, (digest, blob) in FILES.items():
            data = zlib.decompress(base64.b64decode(blob))
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError("this updater file is damaged (" + rel + "). Download it again.")
            target = HERE / rel
            existed = target.exists()
            if existed:
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup / rel)
            touched.append((rel, existed))
            target.write_bytes(data)
            print("  updated  %-22s %5.1f KB" % (rel, len(data) / 1024))
    except Exception as error:
        print("\nSOMETHING WENT WRONG: %s" % error)
        print("Putting your old files back ...")
        for rel, existed in touched:
            if existed and (backup / rel).exists():
                shutil.copy2(backup / rel, HERE / rel)
            elif not existed and (HERE / rel).exists():
                (HERE / rel).unlink()
        print("Done. Nothing was changed. Send me the message above.")
        sys.exit(1)

    print("\nYour old files are saved in: %s" % backup.name)
    print("\nALL DONE. Next steps:")
    print("  1. If the server is running it reloads by itself. If not:  python -m uvicorn main:app --reload --port 8002")
    print("  2. In the browser press Ctrl + Shift + R")
    print("  3. Student: Applications page -> pick an exam.  Overview -> new Completed box.")


if __name__ == "__main__":
    main()
