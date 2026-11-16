"""
form_filler.py - fills a web form (Google Forms first, other simple forms too) with a student's details.

How it works, in plain words:
  1. Find every question on the page (its label + its input box / radio buttons / dropdown).
  2. Work out which of the student's details the label asks for ("Candidate's Name" -> name).
  3. Type the value in, and colour the question GREEN (filled) or YELLOW (not sure, left empty).
Nothing is ever submitted, no checkbox is ticked and no file is uploaded - the person at the
keyboard checks everything and presses Submit themselves.
"""
import re
from difflib import SequenceMatcher

# ------------------------------------------------------------------ what each detail is called
# key -> phrases that a form might use for it (lower case). Longer / more exact phrases win.
SYNONYMS = {
    "name": ["name of candidate", "name of the candidate", "candidate name", "candidates name", "applicant name",
             "name of applicant", "student name", "name of student", "name of the student", "full name",
             "your name", "complete name", "name as per aadhaar", "name as on aadhaar", "name"],
    "father_name": ["father name", "fathers name", "name of father", "name of the father", "father s name",
                    "father full name", "fathers full name"],
    "mother_name": ["mother name", "mothers name", "name of mother", "name of the mother", "mother s name",
                    "mother full name", "mothers full name"],
    "dob": ["date of birth", "birth date", "birthdate", "dob", "d o b"],
    "gender": ["gender", "sex"],
    "aadhaar_number": ["aadhaar number", "aadhar number", "aadhaar no", "aadhar no", "aadhaar card number",
                       "aadhar card number", "uid number", "aadhaar", "aadhar", "uid"],
    "email": ["email address", "e mail address", "email id", "e mail id", "email", "e mail"],
    "phone": ["mobile number", "mobile no", "phone number", "contact number", "whatsapp number", "mobile", "phone",
              "contact no", "contact"],
    "city": ["city", "town", "place"],
    "category": ["reservation category", "caste category", "social category", "category", "caste"],
    "pwd": ["person with disability", "persons with disability", "person with benchmark disability", "pwbd", "pwd",
            "differently abled", "disability", "divyang"],
    "nationality": ["nationality", "citizenship"],
    "address": ["permanent address", "correspondence address", "residential address", "postal address", "home address",
                "full address", "current address", "address"],
    "district": ["district"],
    "state": ["state of residence", "state name", "name of state", "state or union territory", "state"],
    "pincode": ["pin code", "pincode", "postal code", "zip code", "postcode", "pin"],
    "alt_phone": ["alternate mobile", "alternative mobile", "alternate phone", "alternative phone", "alternate contact",
                  "alternate number", "alternative number", "parent mobile", "parents mobile", "guardian mobile",
                  "parent contact", "parents contact", "guardian contact"],
    "father_occupation": ["fathers occupation", "father occupation", "occupation of father", "occupation of the father",
                          "fathers profession", "father profession"],
    "mother_occupation": ["mothers occupation", "mother occupation", "occupation of mother", "occupation of the mother",
                          "mothers profession", "mother profession"],
    # these three depend on the class (10 or 12) - see _class_of()
    "board": ["board name", "name of board", "board of education", "examination board", "board"],
    "roll_no": ["roll number", "roll no", "roll", "seat number", "seat no"],
    "year": ["year of passing", "passing year", "year of examination", "year of exam", "pass out year",
             "passing out year", "year"],
}
# A label that contains one of these words can NOT be that key (stops "School name" matching "name").
BLOCKERS = {
    "name": ["father", "mother", "guardian", "parent", "school", "board", "institute", "college", "user", "company"],
    "father_name": ["mother"],
    "mother_name": ["father"],
    "city": ["birth", "school"],
    "phone": ["father", "mother", "parent", "guardian", "alternate", "alternative", "emergency"],
    "email": ["father", "mother", "parent", "guardian"],
    "year": ["birth", "admission"],
    "board": [],
    "roll_no": [],
    "address": ["email", "mail", "web", "ip"],
    "state": ["birth", "domicile", "status"],
    "district": ["birth"],
    "category": ["age"],
    "pincode": [],
}
CLASS10_WORDS = ["10th", "10", "x ", " x", "tenth", "matric", "matriculation", "secondary school", "high school", "ssc"]
CLASS12_WORDS = ["12th", "12", "xii", "twelfth", "senior secondary", "higher secondary", "intermediate", "hsc", "plus two"]
CLASS_DEPENDENT = {"board", "roll_no", "year"}


def normalize(text: str) -> str:
    """Lower case, no punctuation, single spaces. ("Father's Name *" -> "father s name")"""
    text = re.sub(r"['\u2019`]", "", (text or "").lower())          # father's -> fathers
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _class_of(label: str):
    """Does the label talk about class 10, class 12 or neither?"""
    padded = " " + normalize(label) + " "
    is12 = any((" " + w.strip() + " ") in padded or (len(w.strip()) > 3 and w.strip() in padded) for w in CLASS12_WORDS)
    is10 = any((" " + w.strip() + " ") in padded or (len(w.strip()) > 3 and w.strip() in padded) for w in CLASS10_WORDS)
    if is12 and not is10:
        return "12"
    if is10 and not is12:
        return "10"
    if "senior secondary" in padded:
        return "12"
    return None


def match_label(label: str):
    """Returns (key, certainty 0-100) for the best detail this label asks for, or (None, 0)."""
    text = normalize(label)
    if not text:
        return None, 0
    # remove hints such as "(dd/mm/yyyy)" so they do not confuse the match
    text = re.sub(r"\b(dd|mm|yyyy|required|optional)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    padded = " " + text + " "
    best_key, best_score = None, 0
    for key, phrases in SYNONYMS.items():
        if any(((" " + b + " ") in padded) or (len(b) > 4 and b in padded) for b in BLOCKERS.get(key, [])):
            continue
        for phrase in phrases:
            if text == phrase:
                score = 100
            elif (" " + phrase + " ") in padded:
                score = 60 + min(len(phrase), 25)           # a longer phrase found inside = more certain
                if phrase in ("name", "roll", "year", "city", "contact", "mobile", "phone", "uid", "board", "sex", "state", "pin",
                              "caste", "category", "address", "district", "disability"):
                    score -= 25                              # very short words alone are risky
            else:
                continue
            if score > best_score:
                best_key, best_score = key, score
    if best_key in CLASS_DEPENDENT and _class_of(label):
        best_score += 25                                       # "Class 10 Board" - the class makes it certain
    if best_key is None:
        # last try: spelling mistakes ("Fathers Nme")
        for key, phrases in SYNONYMS.items():
            for phrase in phrases:
                if len(phrase) < 8:
                    continue
                ratio = SequenceMatcher(None, text, phrase).ratio()
                if ratio > 0.86 and ratio * 70 > best_score:
                    best_key, best_score = key, ratio * 70
    return best_key, int(best_score)


def lookup_value(values: dict, key: str, label: str):
    """Gets the student's value for this key. Returns (value, problem_text)."""
    if key in CLASS_DEPENDENT:
        which = _class_of(label)
        if which is None:
            return "", "asks for board/roll/year but does not say Class 10 or 12"
        key = f"{key}_{which}"
    value = (values.get(key) or "").strip()
    if not value:
        return "", "we do not have this detail yet"
    return value, ""


# ------------------------------------------------------------------ formatting values
def format_for_text_box(key: str, value: str, label: str) -> str:
    if key == "dob":
        m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value)
        if m:
            d, mth, y = m.groups()
            hint = (label or "").lower()
            if "yyyy-mm-dd" in hint or "yyyy/mm/dd" in hint:
                return f"{y}-{mth}-{d}"
            if "mm/dd/yyyy" in hint or "mm-dd-yyyy" in hint:
                return f"{mth}/{d}/{y}"
            if "dd-mm-yyyy" in hint:
                return f"{d}-{mth}-{y}"
            return value                                    # DD/MM/YYYY
    if key == "aadhaar_number":
        return re.sub(r"\D", "", value)                     # 12 digits, no spaces
    if key in ("phone", "alt_phone"):
        digits = re.sub(r"\D", "", value)
        return digits[-10:] if len(digits) > 10 else digits
    if key == "pincode":
        return re.sub(r"\D", "", value)
    return value


def dob_iso(value: str) -> str:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", value)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else value


GENDER_WORDS = {
    "male": ["male", "m", "man", "boy"],
    "female": ["female", "f", "woman", "girl"],
    "transgender": ["transgender", "third gender", "other", "others", "t"],
}
BOARD_WORDS = {
    "CBSE": ["cbse", "central board of secondary education"],
    "CISCE (ICSE/ISC)": ["icse", "isc", "cisce", "council for the indian school certificate"],
    "UP Board (UPMSP)": ["up board", "upmsp", "uttar pradesh"],
    "MP Board (MPBSE)": ["mp board", "mpbse", "madhya pradesh"],
    "Bihar Board (BSEB)": ["bihar", "bseb"],
    "Rajasthan Board (RBSE)": ["rajasthan", "rbse"],
    "Haryana Board (HBSE)": ["haryana", "hbse"],
    "NIOS": ["nios", "open schooling"],
}


CATEGORY_WORDS = {
    "General": ["general", "gen", "unreserved", "ur", "open", "general ur", "general unreserved"],
    "OBC-NCL": ["obc", "obc ncl", "obc non creamy layer", "other backward class", "other backward classes", "obc nc"],
    "SC": ["sc", "scheduled caste", "scheduled castes"],
    "ST": ["st", "scheduled tribe", "scheduled tribes"],
    "EWS": ["ews", "gen ews", "general ews", "economically weaker section", "economically weaker sections"],
}
YES_NO = {"yes": ["yes", "y", "true"], "no": ["no", "n", "false", "none", "not applicable", "na"]}


def pick_option(key: str, value: str, options: list):
    """Chooses which of the offered options (list of strings) means `value`. Returns index or None."""
    wanted = normalize(value)
    norm = [normalize(o) for o in options]
    # exact match first
    for i, o in enumerate(norm):
        if o and o == wanted:
            return i
    synonyms = []
    if key == "gender":
        for words in GENDER_WORDS.values():
            if wanted in words:
                synonyms = words
    elif key == "board":
        for official, words in BOARD_WORDS.items():
            if value == official or wanted in words:
                synonyms = words
    elif key == "category":
        for official, words in CATEGORY_WORDS.items():
            if value == official or wanted in words:
                synonyms = words
    elif key == "pwd":
        for words in YES_NO.values():
            if wanted in words:
                synonyms = words
    for i, o in enumerate(norm):
        if o and o in synonyms:
            return i
    if key == "board":
        for i, o in enumerate(norm):
            if o and any(w in o for w in synonyms):
                return i
    if key in ("category", "pwd"):
        return None                                         # these must match exactly (or by the lists above)
    for i, o in enumerate(norm):                            # one contains the other
        if o and len(o) > 2 and (o in wanted or wanted in o):
            return i
    best_i, best_r = None, 0.8
    for i, o in enumerate(norm):
        r = SequenceMatcher(None, wanted, o).ratio()
        if r > best_r:
            best_i, best_r = i, r
    return best_i


# ------------------------------------------------------------------ page helpers (Playwright)
GREEN = "3px solid #21865e"
YELLOW = "3px solid #e0a100"


def _mark(locator, colour):
    try:
        locator.evaluate("(el, c) => { el.style.outline = c; el.style.outlineOffset = '2px'; }", colour)
    except Exception:
        pass


def _visible_text(locator) -> str:
    try:
        return (locator.inner_text(timeout=1500) or "").strip()
    except Exception:
        return ""


def _fill_text_like(box, key, value, label):
    kind = (box.get_attribute("type") or "text").lower()
    if kind == "date":
        box.fill(dob_iso(value) if key == "dob" else value)
    else:
        box.fill(format_for_text_box(key, value, label))
    # Google Forms only notices typing when the field loses focus
    try:
        box.dispatch_event("change")
        box.dispatch_event("blur")
    except Exception:
        pass


# ------------------------------------------------------------------ Google Forms
def _fill_google_form(page, values, report):
    items = page.locator('div[role="listitem"]')
    for n in range(items.count()):
        item = items.nth(n)
        heading = item.locator('[role="heading"]').first
        label = _visible_text(heading)
        if not label:
            continue
        label = re.sub(r"\s*\*\s*$", "", label.replace("\n", " ")).strip()     # drop the red * of required questions
        key, certainty = match_label(label)

        text_box = item.locator('input[type="text"], input[type="email"], input[type="tel"], input[type="number"], input[type="date"], textarea').first
        radios = item.locator('[role="radio"]')
        listbox = item.locator('[role="listbox"]').first
        checkboxes = item.locator('[role="checkbox"]')
        has_text = text_box.count() > 0
        has_radio = radios.count() > 0
        has_list = listbox.count() > 0

        if checkboxes.count() > 0 and not (has_text or has_radio or has_list):
            report.append({"label": label, "status": "left", "reason": "tick-boxes are never ticked automatically"})
            continue
        if not (has_text or has_radio or has_list):
            if item.locator('input[type="file"], [aria-label*="Add file"]').count() or "upload" in label.lower():
                report.append({"label": label, "status": "left", "reason": "file upload: do this yourself"})
            continue
        if key is None or certainty < 50:
            _mark(item, YELLOW)
            report.append({"label": label, "status": "unsure", "reason": "could not tell which detail this asks for"})
            continue
        value, problem = lookup_value(values, key, label)
        if not value:
            _mark(item, YELLOW)
            report.append({"label": label, "status": "unsure", "reason": problem})
            continue
        try:
            if has_text:
                _fill_text_like(text_box, key, value, label)
                shown = format_for_text_box(key, value, label)
            elif has_radio:
                options = [(radios.nth(i).get_attribute("data-value") or radios.nth(i).get_attribute("aria-label") or _visible_text(radios.nth(i))) for i in range(radios.count())]
                index = pick_option(key, value, options)
                if index is None:
                    raise ValueError(f"no option matches '{value}' (options: {', '.join(options[:6])})")
                radios.nth(index).click()
                shown = options[index]
            else:
                listbox.click()
                page.wait_for_timeout(400)
                popup = page.locator('[role="option"]:visible')
                options = [(popup.nth(i).get_attribute("data-value") or _visible_text(popup.nth(i))) for i in range(popup.count())]
                index = pick_option(key, value, options)
                if index is None:
                    page.keyboard.press("Escape")
                    raise ValueError(f"no option matches '{value}' (options: {', '.join(o for o in options[:6] if o)})")
                popup.nth(index).click()
                page.wait_for_timeout(300)
                shown = options[index]
            _mark(item, GREEN)
            report.append({"label": label, "status": "filled", "value": shown, "detail": key})
        except Exception as error:
            _mark(item, YELLOW)
            report.append({"label": label, "status": "unsure", "reason": str(error)[:160]})


# ------------------------------------------------------------------ any other simple form
LABEL_JS = """
(el) => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  if (el.labels && el.labels.length) return clean(el.labels[0].innerText);
  const by = el.getAttribute('aria-labelledby');
  if (by) { const t = by.split(' ').map(id => (document.getElementById(id) || {}).innerText || '').join(' '); if (clean(t)) return clean(t); }
  return clean(el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('name') || el.id || '');
}
"""


# Finds the QUESTION that a group of radio buttons answers (not the answers themselves).
QUESTION_JS = """
(e) => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  // 1) a <fieldset> that holds only this one group of radio buttons
  const f = e.closest('fieldset');
  if (f) {
    const names = new Set(Array.from(f.querySelectorAll('input[type=radio]')).map(r => r.name));
    const legend = f.querySelector('legend');
    if (names.size <= 1 && legend && clean(legend.innerText)) return clean(legend.innerText);
  }
  // 2) an accessible name on the group
  const g = e.closest('[role=radiogroup]');
  if (g) {
    const label = g.getAttribute('aria-label');
    if (label) return clean(label);
    const by = g.getAttribute('aria-labelledby');
    if (by) { const t = by.split(' ').map(id => (document.getElementById(id) || {}).innerText || '').join(' '); if (clean(t)) return clean(t); }
  }
  // 3) walk upwards; the closest earlier text that is not itself a radio option is the question
  let node = e;
  for (let i = 0; i < 5; i++) {
    node = node.parentElement;
    if (!node) break;
    let prev = node.previousElementSibling;
    while (prev) {
      if (!prev.querySelector('input[type=radio]') && clean(prev.innerText)) return clean(prev.innerText);
      prev = prev.previousElementSibling;
    }
  }
  return clean(e.getAttribute('name') || '');
}
"""


def _fill_generic_form(page, values, report):
    boxes = page.locator('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="file"]):not([type="checkbox"]):not([type="radio"]):not([type="password"]), textarea, select')
    for n in range(boxes.count()):
        box = boxes.nth(n)
        try:
            if not box.is_visible():
                continue
            label = box.evaluate(LABEL_JS)
        except Exception:
            continue
        key, certainty = match_label(label)
        if key is None or certainty < 50:
            _mark(box, YELLOW)
            report.append({"label": label or "(no label)", "status": "unsure", "reason": "could not tell which detail this asks for"})
            continue
        value, problem = lookup_value(values, key, label)
        if not value:
            _mark(box, YELLOW)
            report.append({"label": label, "status": "unsure", "reason": problem})
            continue
        try:
            if box.evaluate("e => e.tagName") == "SELECT":
                options = box.evaluate("e => Array.from(e.options).map(o => o.text)")
                index = pick_option(key, value, options)
                if index is None:
                    raise ValueError(f"no option matches '{value}'")
                box.select_option(index=index)
                shown = options[index]
            else:
                _fill_text_like(box, key, value, label)
                shown = format_for_text_box(key, value, label)
            _mark(box, GREEN)
            report.append({"label": label, "status": "filled", "value": shown, "detail": key})
        except Exception as error:
            _mark(box, YELLOW)
            report.append({"label": label, "status": "unsure", "reason": str(error)[:160]})

    # photo / signature upload boxes
    files = page.locator('input[type="file"]')
    for n in range(files.count()):
        box = files.nth(n)
        try:
            label = box.evaluate(LABEL_JS)
            around = box.evaluate("e => ((e.closest('div, td, li, fieldset, label') || e.parentElement || {}).innerText || '').slice(0, 120)")
        except Exception:
            continue
        text = normalize(f"{label} {around}")
        if re.search(r"\bsign(ature)?\b", text):
            kind = "signature"
        elif re.search(r"\b(photo|photograph|passport size|picture|image)\b", text):
            kind = "photo"
        else:
            report.append({"label": label or "file upload", "status": "left", "reason": "file upload: do this yourself"})
            continue
        path = values.get(f"{kind}_path")
        if not path:
            report.append({"label": label or kind, "status": "unsure", "reason": f"no {kind} uploaded for this student yet"})
            continue
        try:
            box.set_input_files(path)
            report.append({"label": label or kind, "status": "filled", "value": f"{kind} file attached", "detail": kind})
        except Exception as error:
            report.append({"label": label or kind, "status": "unsure", "reason": str(error)[:160]})

    # radio buttons (grouped by name)
    seen = set()
    radios = page.locator('input[type="radio"]')
    for n in range(radios.count()):
        radio = radios.nth(n)
        name = radio.get_attribute("name") or f"_{n}"
        if name in seen:
            continue
        seen.add(name)
        group = page.locator(f'input[type="radio"][name="{name}"]') if radio.get_attribute("name") else radio
        try:
            question = radio.evaluate(QUESTION_JS)
        except Exception:
            question = name
        key, certainty = match_label(question)
        if key is None or certainty < 50:
            report.append({"label": question, "status": "unsure", "reason": "could not tell which detail this asks for"})
            continue
        value, problem = lookup_value(values, key, question)
        if not value:
            report.append({"label": question, "status": "unsure", "reason": problem})
            continue
        options = [group.nth(i).evaluate("e => (e.labels && e.labels[0] ? e.labels[0].innerText : e.value)") for i in range(group.count())]
        index = pick_option(key, value, options)
        if index is None:
            report.append({"label": question, "status": "unsure", "reason": f"no option matches '{value}'"})
            continue
        group.nth(index).check()
        _mark(group.nth(index), GREEN)
        report.append({"label": question, "status": "filled", "value": options[index], "detail": key})


# ------------------------------------------------------------------ main entry point
def fill_current_page(page, values: dict) -> dict:
    """Fills whatever form is on the page right now. Returns a report for the admin screen."""
    report = []
    page.wait_for_timeout(500)
    if page.locator('div[role="listitem"] [role="heading"]').count() > 0:
        mode = "Google Form"
        _fill_google_form(page, values, report)
    else:
        mode = "web form"
        _fill_generic_form(page, values, report)
    return {
        "mode": mode,
        "title": page.title(),
        "filled": [r for r in report if r["status"] == "filled"],
        "unsure": [r for r in report if r["status"] == "unsure"],
        "left": [r for r in report if r["status"] == "left"],
    }
