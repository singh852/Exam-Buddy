# Exam Buddy — Local Full-Stack MVP

A beginner-friendly local MVP for the Exam Buddy student application-assistance project.

## Included
- Responsive frontend (HTML, CSS, JavaScript)
- FastAPI backend
- SQLite database (created automatically)
- Student registration/login
- Password hashing (PBKDF2 via Python standard library)
- Student profile editing
- Document uploads with file type/size checks
- Optional OCR for image uploads using Tesseract
- Editable OCR text/results before saving
- Create/view/update application-assistance records
- Admin dashboard and status updates
- Basic user ownership checks and authenticated API routes

## JEE documents feature (new)
1. Student creates an application (e.g. "JEE Main") and clicks **Documents & details**.
2. They upload Aadhaar, Class 10 and Class 12 marksheets. Each is read automatically (Tesseract OCR for images, `pypdf` for text PDFs; scanned PDFs are not read yet).
3. The student checks/corrects the details and presses **Confirm**. Status becomes "Ready for Review".
4. Admin opens the application with **View documents** to see the original files and the confirmed details.
Extraction code lives in `extractors.py`; add or change fields in the `FIELDS` dictionary there.

## Important limitations
This is a local educational MVP, not a production-ready service. Before accepting real student information, commission a security/privacy review, configure HTTPS, use managed secrets and private object storage, add robust account recovery/email verification/rate limits/audit logging, and establish retention/deletion policies. OCR is fallible; students must verify every extracted field. Exam Buddy does not submit official JEE applications or bypass CAPTCHA/OTP/payment/declarations.

## Requirements
- Python 3.10+
- Windows, macOS, or Linux
- Optional: Tesseract OCR installed separately for OCR extraction. If it is not installed, uploads and the rest of the app still work; OCR will return a helpful message.

## Run on Windows
1. Extract this ZIP.
2. Open the extracted `exam_buddy` folder in VS Code.
3. Open Terminal in that folder.
4. Run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   python -m uvicorn main:app --reload
   ```

5. Open http://127.0.0.1:8000
6. API documentation: http://127.0.0.1:8000/docs

If `py` is not recognised, try `python` instead.

## Demo admin
- Email: `admin@exambuddy.local`
- Password: `ChangeMe123!`

Change this password and remove/disable demo credentials before any public deployment. Demo admin is created only if that account does not already exist in the database.

## Student testing
Register a new student account from the website, then:
1. Edit profile.
2. Upload a sample image or PDF (PDF storage is supported; built-in OCR currently handles image files only).
3. Try OCR with a clear image containing text.
4. Create an application assistance record.
5. Log out and back in to confirm the records persist.

## Data location
SQLite database: `exam_buddy.db`
Uploads: `uploads/`

Both are created automatically. Do not commit them to a public repository.

## OCR setup on Windows
Install Tesseract OCR separately from a reputable distribution and ensure `tesseract.exe` is on PATH. Then restart the terminal. You can check by running `tesseract --version`. If it is installed in a custom location, set the `TESSERACT_CMD` environment variable to its full path before starting the server.

## Reset local demo data
Stop the server, then delete `exam_buddy.db` and the contents of `uploads/`. Restart the server to create a fresh database and demo admin.
