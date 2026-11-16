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
    ],
    "class12": [
        ("name", "Candidate name"),
        ("father_name", "Father's name"),
        ("mother_name", "Mother's name"),
        ("dob", "Date of birth (DD/MM/YYYY)"),
        ("board", "Board"),
        ("roll_no", "Roll number"),
        ("year", "Year of passing"),
    ],
}
DOC_TYPES = set(FIELDS.keys())


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
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if len(text) >= MIN_PDF_TEXT:                 # real text inside the PDF
                yield text
                return
            pictures = _pdf_page_pictures(path)           # scanned PDF -> OCR each page
            for prepare in PREPARERS:
                joined = "\n\n".join(_ocr(prepare(p)) for p in pictures).strip()
                if joined:
                    yield joined
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
def parse_aadhaar(text: str) -> dict:
    result = {}

    # Aadhaar number = 12 digits in groups of 4. OCR often adds extra spaces, so allow several.
    # The 16-digit "VID" line is removed first so we never mistake it for the Aadhaar number.
    without_vid = re.sub(r"VID[^\n]*", "", text, flags=re.IGNORECASE)
    m = re.search(r"(?<!\d)(\d{4})[ \t\-]{1,4}(\d{4})[ \t\-]{1,4}(\d{4})(?![ \t\-]*\d)", without_vid)
    if m:
        result["aadhaar_number"] = f"{m.group(1)} {m.group(2)} {m.group(3)}"

    date = re.search(r"(?<!\d)(\d{2})\s*[/\-.]\s*(\d{2})\s*[/\-.]\s*(\d{4})(?!\d)", text)
    if date:
        result["dob"] = f"{date.group(1)}/{date.group(2)}/{date.group(3)}"

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
                  "dob", "birth", "male", "address", "enrolment", "download", "vid")
    if anchor:
        for j in range(anchor - 1, max(anchor - 4, -1), -1):
            candidate = lines[j]
            if re.fullmatch(r"[A-Za-z][A-Za-z .']{2,60}", candidate) and not any(w in candidate.lower() for w in skip_words):
                result["name"] = _clean(candidate).upper()
                break
    return result


# ---------------------------------------------------------------- marksheets
BOARDS = [
    ("CBSE", r"central board of secondary education|\bCBSE\b"),
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
    return ""


def parse_marksheet(text: str) -> dict:
    result = {}
    name = _after_label(text, [r"Name of (?:the )?(?:Candidate|Student)", r"Candidate'?s? Name", r"Student'?s? Name", r"\bName"])
    father = _after_label(text, [r"Father'?s? Name", r"Name of (?:the )?Father"])
    mother = _after_label(text, [r"Mother'?s? Name", r"Name of (?:the )?Mother"])

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

    years = re.findall(r"\b(20[0-3]\d)\b", text)
    if years:
        result["year"] = max(years)  # the latest year on the page is usually the exam year
    return result


PARSERS = {"aadhaar": parse_aadhaar, "class10": parse_marksheet, "class12": parse_marksheet}


def _agreement(value: str, readings) -> int:
    """How strongly do ALL readings support this value? (counts its words in every reading)"""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", value.upper()) if len(w) >= 3]
    return sum(1 for text, _ in readings for w in words if w in text.upper())


def extract_fields(path: Path, doc_type: str):
    """Returns (fields_dict, text_to_show).

    The picture is read several ways. Each reading is parsed, and for every field the
    value that most readings agree on wins. We stop early once every field is found."""
    allowed = [key for key, _ in FIELDS[doc_type]]
    readings = []                       # (text, fields) for each way of reading
    merged = {}
    for text in iter_texts(path):
        found = {k: v for k, v in PARSERS[doc_type](text).items() if k in allowed and v}
        readings.append((text, found))
        merged = {}
        for key in allowed:
            candidates = [f[key] for _, f in readings if key in f]
            if not candidates:
                continue
            votes = Counter(candidates)
            # most votes wins; if tied, the value the other readings support most; then the earliest
            merged[key] = max(votes, key=lambda v: (votes[v], _agreement(v, readings), -candidates.index(v)))
        if len(merged) == len(allowed):
            break
    if not readings:
        return {}, ""
    best_text = max(readings, key=lambda r: (len(r[1]), len(r[0])))[0]   # reading that found the most
    return merged, best_text