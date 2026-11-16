"""
extractors.py - reads uploaded documents and guesses the important fields.

Everything here is FREE (no paid AI):
  - Images (png/jpg/webp)  -> Tesseract OCR
  - PDFs with real text    -> pypdf (reads the text directly)
  - Scanned PDFs           -> pypdfium2 turns pages into pictures, then Tesseract
OCR is never perfect, so the student always reviews and corrects the result.

Because photos differ a lot (white paper vs. coloured watermarks, small vs. big),
each picture is read several different ways. Different ways rescue different words,
so we parse every reading and let the readings "vote" on each field.
"""
import os
import re
from collections import Counter
from pathlib import Path

# Which fields we look for in each type of document.
# (key, label shown to the student)
FIELDS = {
    "aadhaar": [
        ("name", "Name (as on Aadhaar)"),
        ("dob", "Date of birth (DD/MM/YYYY)"),
        ("gender", "Gender"),
        ("aadhaar_number", "Aadhaar number"),
    ],
    "class10": [
        ("name", "Candidate name"),
        ("father_name", "Father's name"),
        ("mother_name", "Mother's name"),
        ("dob", "Date of birth (DD/MM/YYYY)"),
        ("board", "Board"),
        ("roll_no", "Roll number"),
        ("year", "Year of passing"),
        ("school", "School name"),
    ],
    "class12": [
        ("name", "Candidate name"),
        ("father_name", "Father's name"),
        ("mother_name", "Mother's name"),
        ("dob", "Date of birth (DD/MM/YYYY)"),
        ("board", "Board"),
        ("roll_no", "Roll number"),
        ("year", "Year of passing"),
        ("school", "School name"),
    ],
}
DOC_TYPES = set(FIELDS.keys())

# Documents we only store (nothing to read in them): the photo and signature for upload boxes.
FILE_ONLY_TYPES = {"photo", "signature"}

# Details the student types in themselves (they are not on the three documents).
# options = a drop-down list; None = a normal text box.
EXTRA_FIELDS = [
    {"key": "phone", "label": "Mobile number", "options": None},
    {"key": "alt_phone", "label": "Alternate mobile (parent / guardian)", "options": None},
    {"key": "category", "label": "Category", "options": ["", "General", "OBC-NCL", "SC", "ST", "EWS"]},
    {"key": "pwd", "label": "Person with disability (PwD)?", "options": ["", "No", "Yes"]},
    {"key": "nationality", "label": "Nationality", "options": None},
    {"key": "address", "label": "Address (house, street, area)", "options": None},
    {"key": "city", "label": "City / town", "options": None},
    {"key": "district", "label": "District", "options": None},
    {"key": "state", "label": "State", "options": None},
    {"key": "pincode", "label": "Pincode", "options": None},
    {"key": "father_occupation", "label": "Father's occupation", "options": None},
    {"key": "mother_occupation", "label": "Mother's occupation", "options": None},
]


# ---------------------------------------------------------------- picture preparation
MAX_PDF_PAGES = 5          # scanned PDFs: only the first pages are read (keeps uploads fast)
MIN_PDF_TEXT = 30          # fewer characters than this = the PDF is a scan, not real text
TARGET_WIDTH = 2000        # pictures are resized to about this width before reading


def _scale_to(img, width):
    from PIL import Image
    if img.width == width:
        return img
    factor = width / img.width
    return img.resize((max(1, int(img.width * factor)), max(1, int(img.height * factor))), Image.LANCZOS)


def _otsu_threshold(img) -> int:
    """Picks the black/white cut-off automatically (Otsu's method)."""
    hist = img.histogram()[:256]
    total = sum(hist)
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_b = weight_b = 0
    best, threshold = 0, 127
    for i, h in enumerate(hist):
        weight_b += h
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += i * h
        mean_b = sum_b / weight_b
        mean_f = (sum_all - sum_b) / weight_f
        between = weight_b * weight_f * (mean_b - mean_f) ** 2
        if between > best:
            best, threshold = between, i
    return threshold


def _prep_plain(image):
    """Grey, bigger, higher contrast, sharper."""
    from PIL import ImageOps, ImageFilter
    img = ImageOps.exif_transpose(image).convert("L")       # also fixes phone rotation
    if img.width < 1800:
        img = _scale_to(img, 1800)
    return ImageOps.autocontrast(img).filter(ImageFilter.SHARPEN)


def _prep_black_white(channel):
    """Pure black text on white. Using only one colour channel removes coloured
    watermarks/backgrounds (for example the pink pattern on UP Board marksheets)."""
    def prepare(image):
        from PIL import ImageOps
        img = ImageOps.exif_transpose(image).convert("RGB")
        gray = img.convert("L") if channel == "L" else img.split()["RGB".index(channel)]
        gray = ImageOps.autocontrast(_scale_to(gray, TARGET_WIDTH))
        cut = _otsu_threshold(gray)
        return gray.point(lambda p: 255 if p > cut else 0)
    return prepare


PREPARERS = [_prep_plain, _prep_black_white("R"), _prep_black_white("G"), _prep_black_white("L")]


def _ocr(img) -> str:
    import pytesseract
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract.image_to_string(img, lang="eng").strip()


def _pdf_page_pictures(path: Path):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(path))
    return [pdf[i].render(scale=2.5).to_pil() for i in range(min(len(pdf), MAX_PDF_PAGES))]


def iter_texts(path: Path):
    """Yields the document's text, read in several different ways (one after the other,
    so the caller can stop early as soon as it has everything it needs)."""
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            plain = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            has_text = len(plain) >= MIN_PDF_TEXT          # real text inside the PDF (not a scan)
            if has_text:
                # "layout" reading keeps each label on the same line as its value
                try:
                    layout = "\n".join((page.extract_text(extraction_mode="layout") or "") for page in reader.pages)
                    layout = re.sub(r"[ \t]{3,}", "  ", layout).strip()
                except Exception:
                    layout = ""
                if layout:
                    yield layout
            # A picture reading is a second opinion: some PDFs have broken text inside
            # (garbled labels, values separated from their labels), which OCR does not suffer from.
            pictures = _pdf_page_pictures(path)
            for prepare in PREPARERS:
                joined = "\n\n".join(_ocr(prepare(p)) for p in pictures).strip()
                if joined:
                    yield joined
            if has_text:
                yield plain
        else:
            from PIL import Image
            picture = Image.open(path)
            for prepare in PREPARERS:
                yield _ocr(prepare(picture))
    except Exception as error:
        print("OCR problem:", error)


def read_text(path: Path) -> str:
    """Return the text of an image or PDF (first reading only). Empty string if none."""
    for text in iter_texts(path):
        return text
    return ""


# ---------------------------------------------------------------- small helpers
STOP_WORDS = r"\b(?:Class|Section|Date|DOB|Roll|Enroll\w*|Father\w*|Mother\w*|Session|Add?mission|In\s*Word|Sex|Gender)\b"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" :-.,|")


def _name_only(value: str) -> str:
    """Keep only the name: drop symbols, stop at the next label on the same line (e.g. 'Class',
    'Date of Birth'), and refuse results that cannot be a person's name."""
    value = re.sub(r"[^A-Za-z .']", " ", value)                  # symbols / digits -> space
    value = re.split(STOP_WORDS, value, flags=re.IGNORECASE)[0]
    value = _clean(value).upper()
    words = value.split()
    while len(words) >= 3 and len(words[-1]) == 1:               # stray OCR letter at the end ("SINGH A")
        words.pop()
    while len(words) >= 3 and len(words[0]) == 1:
        words.pop(0)
    value = " ".join(words)
    if not words or len(words) > 4 or len(value) > 40:           # a real name is 1-4 short words
        return ""
    return value


def _after_label(text: str, labels: list) -> str:
    """Find 'Label: value' on one line and return the value."""
    for label in labels:
        m = re.search(label + r"[ \t]*[:\-]?[ \t]*([A-Za-z][^\n]{2,70})", text, re.IGNORECASE)
        if m:
            value = _name_only(m.group(1))
            if len(value) >= 3:
                return value
    return ""


# ---------------------------------------------------------------- Aadhaar
_V_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
        [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_V_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
        [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]


def aadhaar_checksum_ok(number: str) -> bool:
    """True if a 12-digit Aadhaar number passes the Verhoeff checksum (catches misread digits)."""
    digits = re.sub(r"\D", "", number)
    if len(digits) != 12:
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _V_D[c][_V_P[i % 8][int(ch)]]
    return c == 0


def parse_aadhaar(text: str) -> dict:
    result = {}

    # Aadhaar number = 12 digits in groups of 4. OCR often adds extra spaces, so allow several.
    # The 16-digit "VID" line is removed first so we never mistake it for the Aadhaar number.
    without_vid = re.sub(r"VID[^\n]*", "", text, flags=re.IGNORECASE)
    # A real Aadhaar number passes the Verhoeff checksum, so if the page holds several look-alike
    # numbers (e.g. one misread), the valid one wins.
    numbers = []
    for m in re.finditer(r"(?<!\d)(\d{4})[ \t\-]{1,4}(\d{4})[ \t\-]{1,4}(\d{4})(?![ \t\-]*\d)", without_vid):
        numbers.append(f"{m.group(1)} {m.group(2)} {m.group(3)}")
    if numbers:
        result["aadhaar_number"] = next((n for n in numbers if aadhaar_checksum_ok(n)), numbers[0])

    # Date of birth: prefer the date right after "DOB" / "Date of Birth"; never use the
    # "issued" / "details as on" / "download" dates that also appear on an Aadhaar letter.
    date_pattern = r"(?<!\d)(\d{2})\s*[/\-.]\s*(\d{2})\s*[/\-.]\s*(\d{4})(?!\d)"
    date = re.search(r"(?:DOB|D\.?O\.?B|Date\s*of\s*Birth)\W{0,6}" + date_pattern, text, re.IGNORECASE)
    if date:
        date = re.search(date_pattern, date.group(0))
    else:
        for found in re.finditer(date_pattern, text):
            before = text[max(0, found.start() - 40): found.start()].lower()
            if re.search(r"issued|details\s*as\s*on|download|generated|printed|enrol", before):
                continue
            if 1900 <= int(found.group(3)) <= 2020:
                date = found
                break
    if date:
        result["dob"] = f"{date.group(1)}/{date.group(2)}/{date.group(3)}"
    else:
        year = re.search(r"Year\s*of\s*Birth\W{0,6}((?:19|20)\d{2})", text, re.IGNORECASE)
        if year:
            result["dob"] = year.group(1)

    m = re.search(r"\b(male|female|transgender)\b", text, re.IGNORECASE)
    if m:
        result["gender"] = m.group(1).capitalize()

    # The name is normally the nearest clean line ABOVE the line that holds the date of birth.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    anchor = None
    for i, line in enumerate(lines):
        if date and date.group(0).replace(" ", "") in line.replace(" ", ""):
            anchor = i
            break
    skip_words = ("government", "india", "authority", "unique", "identification", "aadhaar",
                  "dob", "birth", "male", "address", "enrolment", "download", "vid", "issued",
                  "details", "proof", "citizenship", "verification", "helpline", "scanning", "uidai")
    if anchor:
        for j in range(anchor - 1, max(anchor - 4, -1), -1):
            candidate = lines[j]
            if re.fullmatch(r"[A-Za-z][A-Za-z .']{2,60}", candidate) and not any(w in candidate.lower() for w in skip_words):
                result["name"] = _clean(candidate).upper()
                break
    return result


# ---------------------------------------------------------------- marksheets
BOARDS = [
    ("CBSE", r"central\s*bo?\s*ard|\bC?ENTRAL\s*BO\s*ARD|\bCBSE\b|senior\s*school\s*certificate|marks\s*statement\s*cum\s*certificate"),
    ("CISCE (ICSE/ISC)", r"council for the indian school certificate|\bICSE\b|\bISC\b|\bCISCE\b"),
    ("NIOS", r"national institute of open schooling|\bNIOS\b"),
    ("UP Board (UPMSP)", r"high\s*school\s*and\s*intermediate|madhyamik\s*shiksha\s*parishad|uttar\s*pradesh\s*board|\bU\.?\s?P\.?\s*board\b"),
    ("MP Board (MPBSE)", r"madhya\s*pradesh|\bM\.?\s?P\.?\s*board\b|\bMPBSE\b|\(M\.?P\.?\)"),
    ("Bihar Board (BSEB)", r"bihar\s*school\s*examination|\bBSEB\b"),
    ("Rajasthan Board (RBSE)", r"rajasthan\s*board|\bRBSE\b"),
    ("Haryana Board (HBSE)", r"board\s*of\s*school\s*education\s*haryana|\bHBSE\b"),
    ("State Board", r"board of (secondary|school|intermediate)|state board"),
]

MONTHS = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05", "JUN": "06",
          "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"}


def _find_dob(text: str) -> str:
    """Finds a date of birth and returns it as DD/MM/YYYY."""
    label = r"(?:Date\s*of\s*Birth|D\.?O\.?B\.?)\s*(?:is)?\s*[:\-]?\s*"
    # 1) "Date of Birth: 14-08-2008"
    m = re.search(label + r"(\d{1,2})\s*[/\-. ]?\s*(\d{2})\s*[/\-. ]\s*(\d{4})", text, re.IGNORECASE)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    # 2) "Date of Birth: 14 AUGUST 2008"
    m = re.search(label + r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*[/\-. ]?\s*([A-Za-z]{3})[A-Za-z]*\s*[/\-. ,]?\s*(\d{4})", text, re.IGNORECASE)
    if m and m.group(2).upper() in MONTHS:
        return f"{int(m.group(1)):02d}/{MONTHS[m.group(2).upper()]}/{m.group(3)}"
    # 3) a date in brackets, e.g. "NINETEEN HUNDRED NINETY NINE (09/11/1999)"  (UP Board style)
    m = re.search(r"\(\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*((?:19|20)\d{2})\s*\)", text)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    # 4) last try: any date whose year is a believable birth year
    m = re.search(r"(?<!\d)(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(19[89]\d|200\d|201[0-2])(?!\d)", text)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return ""


def _find_roll_no(text: str) -> str:
    # "Roll No: 12345678"  (number on the same line)
    m = re.search(r"Roll\s*(?:No|Number)\.?\s*[:.\-]?\s*([A-Z0-9]{5,15})\b", text, re.IGNORECASE)
    if m and re.search(r"\d", m.group(1)):
        return m.group(1).upper()
    # UP Board style: "Roll No." is a table heading and the number sits in a cell below it
    m = re.search(r"Roll\s*No\.?", text, re.IGNORECASE)
    if m:
        nearby = text[m.end(): m.end() + 400]
        n = re.search(r"(?<![\d/])(\d{6,10})(?![\d/])", nearby)
        if n:
            return n.group(1)
    # labels garbled ("Doli No.", "lNo."): a CBSE roll number is a standalone 8-digit number
    m = re.search(r"(?<![\d/\-])(\d{8})(?![\d/\-])", text)
    if m:
        return m.group(1)
    return ""


NOT_NAMES = {"CENTRAL", "BOARD", "SECONDARY", "EDUCATION", "SCHOOL", "EXAMINATION", "CERTIFICATE", "SENIOR",
             "MARKS", "STATEMENT", "SUBJECT", "ENGLISH", "HINDI", "SCIENCE", "SOCIAL", "MATHEMATICS", "PHYSICS",
             "CHEMISTRY", "BIOLOGY", "PHYSICAL", "WORK", "EXPERIENCE", "HEALTH", "GENERAL", "STUDIES", "CORE",
             "COURSE", "STANDARD", "LNG", "LIT", "THEORY", "TOTAL", "RESULT", "PASS", "FAIL", "GRADE", "ADDITIONAL",
             "INFORMATION", "TECHNOLOGY", "COMPUTER", "PRACTICAL", "POSITIONAL", "CODE", "SUB", "LAXMI", "PUB",
             "ROAD", "BOARD", "THOUSAND", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
             "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN",
             "EIGHT", "NINE", "TEN", "TWENTY", "THIRTY", "FORTY", "FIFTY", "SIXTY", "SEVENTY", "EIGHTY", "NINETY",
             "HUNDRED", "FIRST", "ST", "ND", "RD", "TH", "ISSUED", "DATE", "ROLL", "NAME", "MOTHER", "FATHER",
             "GUARDIAN", "REGN", "REGISTRATION", "INDIA", "DELHI", "COMMERCE", "ARTS", "HUMANITIES", "VOCATIONAL"}


def _name_candidates(text: str) -> list:
    """Capital-letter lines that look like a person's name, in the order they appear on the page.
    Used when the labels ('Mother's Name' ...) are damaged but the names themselves are readable.
    On CBSE marksheets the order is always: candidate, mother, father."""
    found = []
    for line in text.splitlines():
        for run in re.findall(r"(?<![A-Za-z])[A-Z]{2,}(?: [A-Z]{2,}){1,3}(?![A-Za-z])", re.sub(r"[^A-Za-z ]", " ", line)):
            words = run.split()
            # every word of a real name has at least 3 letters here (rejects OCR noise like "BT ATA", "OF SECOND")
            if len(words) <= 3 and all(len(w) >= 3 for w in words) and not any(w in NOT_NAMES for w in words) and run not in found:
                found.append(run)
    return found


SCHOOL_WORDS = r"SCHOOL|VIDYALAYA|VIDYALAY|VIDYA|COLLEGE|ACADEMY|PUBLIC|PUB\b|INSTITUTE|CONVENT|MODEL|SR\.?\s*SEC|GURUKUL|SHIKSHA|MAHAVIDYALAYA"


def _clean_school(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9 .,&'()/\-]", " ", value)
    value = re.sub(r"^[\s\d\-–:./]+", "", value)                 # school code in front ("65794 - ")
    value = _clean(value).upper()
    if len(value) < 6 or len(value) > 90 or not re.search(r"[A-Z]{3}", value):
        return ""
    if re.search(r"EXAMINATION|CERTIFICATE|ACHIEVE|SCHOLASTIC|SUBJECT|ROLL|MARKS", value):
        return ""
    return value


def _find_school(text: str) -> str:
    """School name: 'School  65794 - LAXMI PUB SCHOOL ...' or, without a label, a line that starts
    with the school code and contains a word like SCHOOL / VIDYALAYA / COLLEGE."""
    for line in text.splitlines():
        m = re.search(r"(?:Name\s*of\s*(?:the\s*)?(?:School|Institution|College)|School\s*/\s*College|\bSchool|\bInstitution)\b\s*(?:Name)?\W{0,3}(\d{3,6}\W{0,3})?([A-Za-z][^\n]*)", line, re.IGNORECASE)
        if m and (m.group(1) or ":" in line or "-" in line):
            value = _clean_school(m.group(2))
            if value and len(value.split()) >= 2 and re.search(SCHOOL_WORDS, value):
                return value
    for line in text.splitlines():
        m = re.search(r"(?<!\d)\d{4,6}\s*[-–:]?\s*([A-Z][A-Za-z .,&'()/\-]{8,90})", line)
        if m and re.search(SCHOOL_WORDS, m.group(1), re.IGNORECASE):
            value = _clean_school(m.group(1))
            if value:
                return value
    return ""


def parse_marksheet(text: str) -> dict:
    result = {}
    # Lines about the parents must not be mistaken for the candidate's own "Name" line.
    own_lines = "\n".join(l for l in text.splitlines() if not re.search(r"\bther\b|other|ather|acher|guardian|mone\b", l, re.IGNORECASE))
    name = _after_label(own_lines, [r"Name of (?:the )?(?:Candidate|Student)", r"Candidate'?s? Name", r"Student'?s? Name",
                                    r"tify\s*that", r"\bName"])
    father = _after_label(text, [r"F[a-z]{3}er\W{0,3}s?\s*(?:/\s*Guardian\W{0,3}s?)?\s*Name", r"Guardian\W{0,3}s?\s*Name",
                                 r"Name of (?:the )?Father"])
    mother = _after_label(text, [r"Mother\s*\W{0,3}s?\s*Name", r"\bther\W{0,3}s?\s*Name", r"Name of (?:the )?Mother"])

    # UP Board layout has no "Name:" labels. Instead it reads:
    #   (according to the Board's record)-  CANDIDATE
    #   (son/daughter of Mrs.)-             MOTHER
    #   (and Mr.)-                          FATHER
    if not name:
        m = re.search(r"(?i:according\s*to\s*the\s*board'?s\s*record)[ \t]*\)?[ \t]*[-:–]?[ \t]*([^\n]{3,60})", text)
        if m:
            name = _name_only(m.group(1))
    if not mother:
        m = re.search(r"(?i:daughter\s*of\s*mrs)\.?[ \t]*\)?[ \t]*[-:–]?[ \t]*([^\n]{3,60})", text)
        if m:
            mother = _name_only(m.group(1))
    if not father:
        m = re.search(r"(?i:and\s*mr)\.?[ \t]*\)?[ \t]*[-:–]?[ \t]*([^\n]{3,60})", text)
        if m:
            father = _name_only(m.group(1))

    # Fallback when labels are damaged: the names in page order are candidate, mother, father.
    # This is only a GUESS, kept apart from label-based answers; extract_fields() accepts it only
    # when several readings agree on the same three names.
    candidates = _name_candidates(text)
    if len(candidates) >= 3 and not (name and father and mother):
        result["_guess"] = tuple(candidates[:3])
    elif len(candidates) >= 1 and not (name and father and mother):
        result["_guess"] = None

    for key, value in (("name", name), ("father_name", father), ("mother_name", mother)):
        if len(value) >= 3:
            result[key] = value

    dob = _find_dob(text)
    if dob:
        result["dob"] = dob

    for board_name, pattern in BOARDS:
        if re.search(pattern, text, re.IGNORECASE):
            result["board"] = board_name
            break

    roll = _find_roll_no(text)
    if roll:
        result["roll_no"] = roll

    school = _find_school(text)
    if school:
        result["school"] = school

    exam_year = re.search(r"[A-Z]*NATION\w*\W{0,3}(20[0-3]\d)", text, re.IGNORECASE)   # "EXAMINATION, 2023"
    years = re.findall(r"\b(20[0-3]\d)\b", text)
    if exam_year:
        result["year"] = exam_year.group(1)
    elif years:
        result["year"] = max(years)  # the latest year on the page is usually the exam year
    return result


PARSERS = {"aadhaar": parse_aadhaar, "class10": parse_marksheet, "class12": parse_marksheet}


def _agreement(value: str, readings) -> int:
    """How strongly do ALL readings support this value? (counts its words in every reading)"""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", value.upper()) if len(w) >= 3]
    return sum(1 for text, _ in readings for w in words if w in text.upper())


def _merge(allowed, readings, guesses):
    """Combine all readings: the value most readings agree on wins for each field."""
    merged = {}
    for key in allowed:
        candidates = [f[key] for _, f in readings if key in f]
        if not candidates:
            continue
        votes = Counter(candidates)
        # most votes wins; if tied, the value the other readings support most; then the earliest
        merged[key] = max(votes, key=lambda v: (votes[v], _agreement(v, readings), -candidates.index(v)))

    # Safety net for the three people-names: they must be three DIFFERENT people.
    # (A father's name equal to the mother's name means one of them was read from the wrong line.)
    for later, earlier in (("mother_name", "name"), ("father_name", "mother_name"), ("father_name", "name")):
        if later in merged and merged.get(later) == merged.get(earlier):
            del merged[later]

    # Page-order guess (candidate, mother, father) fills only what is still missing, and only when
    # at least two readings agree on the same three names (or there is just one reading).
    if guesses and any(k in allowed and k not in merged for k in ("name", "mother_name", "father_name")):
        triple, count = Counter(guesses).most_common(1)[0]
        if count >= 2 or len(readings) == 1:
            used = set(merged.values())
            spare = [n for n in triple if n not in used]
            for key in ("name", "mother_name", "father_name"):
                if key in allowed and key not in merged and spare:
                    merged[key] = spare.pop(0)
    return merged


def extract_fields(path: Path, doc_type: str):
    """Returns (fields_dict, text_to_show).

    The picture is read several ways. Each reading is parsed, and for every field the
    value that most readings agree on wins. We stop early once every field is found."""
    allowed = [key for key, _ in FIELDS[doc_type]]
    readings = []                       # (text, fields) for each way of reading
    guesses = []                        # page-order guesses of (candidate, mother, father)
    merged = {}
    for text in iter_texts(path):
        parsed = PARSERS[doc_type](text)
        guess = parsed.get("_guess")
        if guess:
            guesses.append(guess)
        found = {k: v for k, v in parsed.items() if k in allowed and v}
        readings.append((text, found))
        merged = _merge(allowed, readings, guesses)
        if len(merged) == len(allowed):
            break
    if not readings:
        return {}, ""
    best_text = max(readings, key=lambda r: (len(r[1]), len(r[0])))[0]   # reading that found the most
    return merged, best_text