"""
form_worker.py - a small helper program that owns the browser window.

The website server starts this program and talks to it by sending one JSON line per command
(open / fill / close). It answers with one line starting with @@REPLY@@.
Running the browser in its own program keeps it safe from the server's auto-reload on Windows.
"""
import json
import os
import sys

PREFIX = "@@REPLY@@"


def reply(data: dict):
    sys.stdout.write(PREFIX + json.dumps(data) + "\n")
    sys.stdout.flush()


def launch(p):
    """Prefer the Chrome / Edge already installed on this computer (no download needed)."""
    headless = os.environ.get("EB_HEADLESS") == "1"
    errors = []
    for channel in (None if headless else "chrome", None if headless else "msedge", None):
        try:
            return p.chromium.launch(headless=headless, channel=channel)
        except Exception as error:
            errors.append(str(error).splitlines()[0])
    raise RuntimeError("Could not start a browser. Install Google Chrome, or run:  python -m playwright install chromium   (" + "; ".join(errors) + ")")


def answer_with_error_only(message):
    """Playwright is missing: keep running so we can tell the website WHY, instead of silently dying."""
    for line in sys.stdin:
        if line.strip():
            reply({"ok": False, "error": message})


def main():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        answer_with_error_only("Playwright is not installed in this Python environment. In the terminal run:  "
                               "python -m pip install -r requirements.txt   (" + str(error)[:80] + ")")
        return
    try:
        from form_filler import fill_current_page
    except Exception as error:
        answer_with_error_only("The file form_filler.py is missing or has the wrong name. It must be in the same folder as main.py "
                               "and be named exactly form_filler.py  (" + str(error)[:80] + ")")
        return
    with sync_playwright() as p:
        browser = None
        context = None
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                command = json.loads(line)
                action = command.get("cmd")
                if action == "open":
                    if browser is None or not browser.is_connected():
                        browser = launch(p)
                    if context is not None:
                        try:
                            context.close()
                        except Exception:
                            pass
                    context = browser.new_context(viewport=None if os.environ.get("EB_HEADLESS") != "1" else {"width": 1200, "height": 900})
                    page = context.new_page()
                    page.goto(command["url"], wait_until="domcontentloaded", timeout=45000)
                    try:
                        page.wait_for_selector('div[role="listitem"], input, textarea, select', timeout=15000)
                    except Exception:
                        pass
                    reply({"ok": True, "report": fill_current_page(page, command["values"])})
                elif action == "fill":
                    if browser is None or not browser.is_connected() or context is None:
                        reply({"ok": False, "error": "The browser window is not open. Press 'Open form' first."})
                        continue
                    pages = [pg for pg in context.pages if not pg.is_closed()]
                    if not pages:
                        reply({"ok": False, "error": "The form window was closed. Press 'Open form' again."})
                        continue
                    reply({"ok": True, "report": fill_current_page(pages[-1], command["values"])})
                elif action == "check":
                    test_browser = launch(p)
                    version = test_browser.version
                    test_browser.close()
                    reply({"ok": True, "message": f"The browser works (Chromium {version}). You can open a form now."})
                elif action == "close":
                    if browser is not None:
                        try:
                            browser.close()
                        except Exception:
                            pass
                    browser = context = None
                    reply({"ok": True})
                elif action == "quit":
                    break
                else:
                    reply({"ok": False, "error": "Unknown command."})
            except Exception as error:
                reply({"ok": False, "error": str(error).splitlines()[0][:300] if str(error) else "Something went wrong."})


if __name__ == "__main__":
    main()
