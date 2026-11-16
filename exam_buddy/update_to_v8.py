"""
update_to_v8.py  -  upgrades your Exam Buddy folder from version 5 to version 8, IN PLACE.

How to use (run it ONCE):
  1. Copy this file into your exam_buddy folder, next to main.py.
  2. In the VS Code terminal, inside that folder, run:    python update_to_v8.py

What is new in version 8 (it also contains versions 6 and 7, so run only this one):
  - Admin password: the default password must be changed at the first login. Everyone can change
    their password on My profile.
  - Forgot password: a 6-digit code (sent by email if email is set up, otherwise printed in the
    server terminal). Admin can also give a student a temporary password (Admin panel -> Reset password).
  - Uploaded files are now ENCRYPTED on disk (a key file data_key.key is created next to main.py).
    BACK UP data_key.key and never share or upload it: without it the uploaded files cannot be opened.
What it does: saves a backup of every file it changes, writes main.py, requirements.txt, static/app.js, static/styles.css,
static/exams.js, and makes small edits in static/index.html. It checks everything and puts your
old files back if something is wrong. It NEVER touches your database or uploads.
"""
import base64
import hashlib
import shutil
import subprocess
import sys
import zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "main.py": (
        "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"
    ),
    "requirements.txt": (
        "d9753cac14996de8cad8ad4a8c81a7dc28fb7bf7186b8e6ffb996718c28f653e",
        "eNotyksOwyAMRdE5a2ktCMmgUsNGqg4s8kMiwTLQiN0Xms78fO6CMSE5M0pQarg9FUiRP84GPl5Vjgl5ejfV8kIqaQvHfc8+OUJO"
        "zSQ8BDnvw2lGJa9ojnFmtD/XoNqPpsWMPfxPl/euTV23x3KyW7daK+gHYblQCisjbaU2HUjxBb96NTk="
    ),
    "static/app.js": (
        "38e53a16f76dcb019bf60c1ea8658d644295cf45db1749a0abdc2d7646267196",
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
INDEX_EDITS += [('          <p id="auth-error" class="form-error"></p>', '          <label id="consent-label" class="consent hidden"><input id="auth-consent" type="checkbox"> <span>I have read the <a href="#" onclick="openPrivacy();return false;">privacy notice</a> and I agree that Exam Buddy stores my documents to help with my application.</span></label>\n          <p id="auth-error" class="form-error"></p>'), ('  <script src="/static/exams.js"></script>', '  <div id="privacy-modal" class="modal hidden" onclick="if(event.target===this)closePrivacy()"><div class="modal-box">\n    <h3>Privacy notice</h3>\n    <ul>\n      <li><b>What we store:</b> your name, email, the documents you upload (Aadhaar, marksheets, photo, signature) and the details read from them.</li>\n      <li><b>Why:</b> only to fill your exam application form for you. We do not sell or share your data.</li>\n      <li><b>Who can see it:</b> you, and the Exam Buddy staff who fill your form. Staff see your Aadhaar number masked (XXXX XXXX 1234) and every time they open your documents is written to a log.</li>\n      <li><b>How long:</b> your documents and details are deleted automatically <span id="retention-days">30</span> days after your application is marked Completed.</li>\n      <li><b>Your control:</b> you can delete all your documents and details at any time from My profile, using "Delete my data".</li>\n      <li><b>Your responsibility:</b> check every detail before confirming. Exam Buddy is not an official exam portal. OTP, CAPTCHA, payment and final submission are always done with you.</li>\n    </ul>\n    <button class="btn btn-primary" onclick="closePrivacy()">Close</button>\n  </div></div>\n  <script src="/static/exams.js"></script>'), ('<div class="form-actions"><button class="btn btn-primary" type="submit">Save profile</button></div></form>', '<div class="form-actions"><button class="btn btn-primary" type="submit">Save profile</button></div></form><div class="privacy-box"><h4>Privacy &amp; data</h4><p class="muted tiny">Your documents are deleted automatically 30 days after an application is marked Completed. You can also delete everything yourself.</p><div class="inline-actions"><button class="btn btn-outline btn-sm" onclick="openPrivacy()">Read privacy notice</button><button class="btn btn-danger btn-sm" onclick="deleteMyData()">Delete my data</button></div></div>'), ('<div id="admin-applications" class="record-list"></div></div>', '<div class="inline-actions"><input id="admin-search" class="grow" type="search" placeholder="Search by student, email or exam" oninput="renderAdminApps()"><select id="admin-filter" onchange="renderAdminApps()"></select></div><div id="admin-applications" class="record-list"></div></div><div class="panel"><div class="panel-heading"><div><h3>Activity log</h3><p>Who opened or changed what. Latest 100 entries.</p></div></div><div id="admin-activity" class="table-wrap"></div></div>'), ('          <p class="form-foot">By continuing,', '          <p id="forgot-row" class="form-foot"><a href="#" onclick="openReset();return false;">Forgot your password?</a></p>\n          <p class="form-foot">By continuing,'), ('  <script src="/static/exams.js"></script>', '  <div id="reset-modal" class="modal hidden" onclick="if(event.target===this)closeReset()"><div class="modal-box">\n    <h3>Reset your password</h3>\n    <div id="reset-step1"><p class="muted tiny">Enter your account email. We send a 6-digit code that works for 15 minutes.</p>\n      <label>Email address<input id="reset-email" type="email" autocomplete="email"></label>\n      <div class="inline-actions"><button class="btn btn-primary" onclick="sendResetCode()">Send code</button><button class="btn btn-outline" onclick="closeReset()">Cancel</button></div></div>\n    <div id="reset-step2" class="hidden"><p id="reset-info" class="muted tiny"></p>\n      <label>6-digit code<input id="reset-code" inputmode="numeric" maxlength="6" autocomplete="one-time-code"></label>\n      <label>New password<input id="reset-new" type="password" minlength="8" autocomplete="new-password" placeholder="At least 8 characters"></label>\n      <div class="inline-actions"><button class="btn btn-primary" onclick="finishReset()">Set new password</button><button class="btn btn-outline" onclick="closeReset()">Cancel</button></div></div>\n    <p id="reset-error" class="form-error"></p>\n  </div></div>\n  <div id="pw-modal" class="modal hidden"><div class="modal-box">\n    <h3>Choose a new password</h3>\n    <p class="muted tiny">For your safety you must set your own password before you continue.</p>\n    <label>Current (temporary) password<input id="pw-current" type="password" autocomplete="current-password"></label>\n    <label>New password<input id="pw-new" type="password" minlength="8" autocomplete="new-password" placeholder="At least 8 characters"></label>\n    <label>Repeat the new password<input id="pw-new2" type="password" minlength="8" autocomplete="new-password"></label>\n    <p id="pw-error" class="form-error"></p>\n    <div class="inline-actions"><button class="btn btn-primary" onclick="doChangePassword(\'pw\')">Save new password</button><button class="btn btn-outline" onclick="logout()">Log out</button></div>\n  </div></div>\n  <script src="/static/exams.js"></script>'), ('<div class="privacy-box"><h4>Privacy &amp; data</h4>', '<div class="privacy-box" id="change-pw"><h4>Change password</h4><div class="form-grid"><label>Current password<input id="cp-current" type="password" autocomplete="current-password"></label><label>New password<input id="cp-new" type="password" minlength="8" autocomplete="new-password"></label><label>Repeat new password<input id="cp-new2" type="password" minlength="8" autocomplete="new-password"></label></div><p id="cp-error" class="form-error"></p><button class="btn btn-outline btn-sm" onclick="doChangePassword(\'cp\')">Change password</button></div><div class="privacy-box"><h4>Privacy &amp; data</h4>')]
ALREADY += ['id="consent-label"', 'id="privacy-modal"', 'class="privacy-box"', 'id="admin-search"', 'id="forgot-row"', 'id="reset-modal"', 'id="change-pw"']



def main():
    if not (HERE / "main.py").exists() or not (HERE / "static").is_dir():
        print("STOP: put update_to_v8.py inside your exam_buddy folder (the one that contains main.py and the static folder).")
        sys.exit(1)
    backup = HERE / ("backup_before_v8_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    touched = []   # (relative path, existed before)
    print("Updating Exam Buddy to version 8 ...")
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

    if "--no-pip" not in sys.argv:
        print("\nInstalling the new requirement (cryptography) - this can take a minute ...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(HERE / "requirements.txt")])
        if result.returncode != 0:
            print("The install did not finish. Run this yourself:  python -m pip install -r requirements.txt")
    print("\nIMPORTANT: a file called data_key.key will appear next to main.py when the server starts. It locks all uploaded files.")
    print("Copy it to a safe place (like a pen drive) and NEVER share it. Without it the uploaded files cannot be opened.")
    print("\nALL DONE. Next steps:")
    print("  1. If the server is running it reloads by itself. If not:  python -m uvicorn main:app --reload --port 8002")
    print("  2. In the browser press Ctrl + Shift + R")
    print("  3. Admin: log in with the old password (ChangeMe123!), you will be asked to choose a new one.")


if __name__ == "__main__":
    main()
