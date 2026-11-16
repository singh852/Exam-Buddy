// exams.js - the list of exams students can pick, and the documents each one usually needs.
// IMPORTANT: these lists are typical requirements. Every year's official notification can change them,
// so the page always tells the student to check the official notice.
// In each document list, "key" is one of: aadhaar, class10, class12, photo, signature.
// A document with a key can be uploaded on Exam Buddy. A document without a key is "keep ready" only.

const EXAM_CATEGORIES = ["All", "Engineering", "Medical", "Defence", "Govt jobs", "University"];

const D = {
  aadhaar:   {label: "Aadhaar card (or another photo ID)", key: "aadhaar"},
  class10:   {label: "Class 10 marksheet / certificate (proof of date of birth)", key: "class10"},
  class12:   {label: "Class 12 marksheet (or admit card if you are appearing)", key: "class12"},
  photo:     {label: "Passport-size photograph", key: "photo"},
  signature: {label: "Your signature on white paper", key: "signature"},
  category:  {label: "Category certificate (only if you apply under SC / ST / OBC-NCL)"},
  ews:       {label: "EWS certificate (only if you apply under EWS)"},
  pwd:       {label: "Disability certificate (only if you apply under PwD)"},
  domicile:  {label: "Domicile / residence certificate (state exams, if asked)"},
  thumb:     {label: "Left thumb impression on white paper"},
  postcard:  {label: "Postcard-size photograph (4 x 6 inch)"},
  degree:    {label: "Graduation degree / marksheet"},
  mainrank:  {label: "JEE Main roll number / application number"}
};

const EXAMS = [
  // ---------------- Engineering
  {id: "jee-main", name: "JEE Main", category: "Engineering", by: "NTA",
   about: "National entrance for NITs, IIITs and other engineering colleges.",
   docs: ["aadhaar", "class10", "class12", "photo", "signature", "category", "ews", "pwd"]},
  {id: "jee-advanced", name: "JEE Advanced", category: "Engineering", by: "IITs",
   about: "For IIT admission. Only for students who qualified through JEE Main.",
   docs: ["mainrank", "aadhaar", "class10", "class12", "photo", "signature", "category", "ews", "pwd"]},
  {id: "bitsat", name: "BITSAT", category: "Engineering", by: "BITS Pilani",
   about: "Private university exam for BITS campuses.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar"]},
  {id: "viteee", name: "VITEEE", category: "Engineering", by: "VIT",
   about: "Private university exam for VIT campuses.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar"]},
  {id: "srmjeee", name: "SRMJEEE", category: "Engineering", by: "SRM",
   about: "Private university exam for SRM campuses.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar"]},
  {id: "met", name: "MET (Manipal)", category: "Engineering", by: "Manipal",
   about: "Private university exam for Manipal Academy of Higher Education.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar"]},
  {id: "comedk", name: "COMEDK UGET", category: "Engineering", by: "COMEDK",
   about: "Private engineering colleges in Karnataka.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar", "category"]},
  {id: "mht-cet", name: "MHT CET", category: "Engineering", by: "Maharashtra",
   about: "State exam for engineering and pharmacy in Maharashtra.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar", "domicile", "category"]},
  {id: "wbjee", name: "WBJEE", category: "Engineering", by: "West Bengal",
   about: "State engineering exam for West Bengal.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar", "domicile", "category"]},
  {id: "kcet", name: "KCET", category: "Engineering", by: "Karnataka",
   about: "State common entrance for Karnataka.",
   docs: ["class10", "class12", "photo", "signature", "aadhaar", "domicile", "category"]},

  // ---------------- Medical
  {id: "neet-ug", name: "NEET UG", category: "Medical", by: "NTA",
   about: "National entrance for MBBS, BDS and other medical courses.",
   docs: ["aadhaar", "class10", "class12", "photo", "postcard", "signature", "thumb", "category", "ews", "pwd"]},

  // ---------------- Defence
  {id: "nda", name: "NDA / NA", category: "Defence", by: "UPSC",
   about: "Entry to the National Defence Academy and Naval Academy after Class 12.",
   docs: ["aadhaar", "class10", "class12", "photo", "signature", "category"]},

  // ---------------- Govt jobs
  {id: "ssc-cgl", name: "SSC CGL", category: "Govt jobs", by: "SSC",
   about: "Combined Graduate Level exam for central government posts.",
   docs: ["aadhaar", "class10", "degree", "photo", "signature", "category", "ews", "pwd"]},
  {id: "ssc-chsl", name: "SSC CHSL", category: "Govt jobs", by: "SSC",
   about: "Combined Higher Secondary Level exam (Class 12 pass).",
   docs: ["aadhaar", "class10", "class12", "photo", "signature", "category", "ews", "pwd"]},
  {id: "ssc-mts", name: "SSC MTS", category: "Govt jobs", by: "SSC",
   about: "Multi Tasking Staff exam (Class 10 pass).",
   docs: ["aadhaar", "class10", "photo", "signature", "category", "ews", "pwd"]},
  {id: "ssc-gd", name: "SSC GD Constable", category: "Govt jobs", by: "SSC",
   about: "Constable recruitment for central armed police forces (Class 10 pass).",
   docs: ["aadhaar", "class10", "photo", "signature", "category", "ews"]},

  // ---------------- University
  {id: "cuet-ug", name: "CUET UG", category: "University", by: "NTA",
   about: "Common entrance for central and many other universities.",
   docs: ["aadhaar", "class10", "class12", "photo", "signature", "category", "ews", "pwd"]}
];

// The rest of the app asks: which exam is this, and which uploads does it use?
function findExam(name) {
  const n = (name || "").trim().toLowerCase();
  return EXAMS.find(e => e.name.toLowerCase() === n) || null;
}
// For an exam on our list, only the uploads it needs; for a custom exam, everything.
function uploadTypesFor(name) {
  const exam = findExam(name);
  if (!exam) return ["aadhaar", "class10", "class12", "photo", "signature"];
  return exam.docs.map(k => D[k].key).filter(Boolean);
}

// ---------------------------------------------------------------- the exam picker (Applications page)
let examFilter = "All";
let examSearch = "";

function renderExamPicker() {
  const box = document.getElementById("exam-picker");
  if (!box) return;
  const chips = EXAM_CATEGORIES.map(c => `<button type="button" class="chip ${c === examFilter ? "on" : ""}" onclick="setExamFilter('${c}')">${c}</button>`).join("");
  const shown = EXAMS.filter(e => (examFilter === "All" || e.category === examFilter) &&
    (!examSearch || (e.name + " " + e.by + " " + e.category).toLowerCase().includes(examSearch)));
  const cards = shown.map(e => `<button type="button" class="exam-card" onclick="pickExam('${e.id}')"><strong>${escapeHtml(e.name)}</strong><small>${escapeHtml(e.by)} · ${escapeHtml(e.category)}</small></button>`).join("")
    || `<p class="muted tiny">No exam matches. Use "Other exam" below to type its name.</p>`;
  box.innerHTML = `<div class="exam-tools"><input id="exam-search" type="search" placeholder="Search exams (NEET, SSC, NDA...)" value="${escapeHtml(examSearch)}" oninput="setExamSearch(this.value)"></div>
    <div class="chip-row">${chips}</div>
    <div class="exam-grid">${cards}<button type="button" class="exam-card other" onclick="pickExam('')"><strong>Other exam</strong><small>Type any exam name</small></button></div>
    <div id="exam-docs"></div>`;
}
function setExamFilter(c) { examFilter = c; renderExamPicker(); }
function setExamSearch(v) {
  examSearch = v.trim().toLowerCase(); renderExamPicker();
  const input = document.getElementById("exam-search"); input.focus(); input.setSelectionRange(v.length, v.length);
}
function pickExam(id) {
  const exam = EXAMS.find(e => e.id === id);
  const nameBox = document.getElementById("exam-name");
  nameBox.value = exam ? exam.name : "";
  document.querySelectorAll(".exam-card").forEach(el => el.classList.toggle("picked", exam && el.querySelector("strong").textContent === exam.name));
  const target = document.getElementById("exam-docs");
  if (!exam) {
    target.innerHTML = `<div class="docs-box"><p class="muted tiny">Type the exam name in the box below. For an exam that is not on our list, keep your Aadhaar, Class 10 and Class 12 marksheets, a photo and a signature ready.</p></div>`;
    nameBox.focus(); return;
  }
  target.innerHTML = `<div class="docs-box"><h4>${escapeHtml(exam.name)}: documents you need</h4><p class="muted tiny">${escapeHtml(exam.about)}</p>${docChecklistHtml(exam, null)}<p class="muted tiny">This is the usual list. Always check the official notification for this year's exact rules.</p></div>`;
  document.getElementById("exam-session").focus();
}

// A list of the documents an exam needs. "documents" (optional) = the student's uploaded files, to tick them.
function docChecklistHtml(exam, documents) {
  return `<ul class="doc-checklist">` + exam.docs.map(k => {
    const d = D[k];
    let mark = "•", note = "";
    if (d.key) {
      if (documents) {
        const done = documents.some(x => x.doc_type === d.key);
        mark = done ? "✅" : "⬜";
        note = done ? `<small class="muted"> uploaded</small>` : `<small class="muted"> upload below</small>`;
      } else note = `<small class="muted"> you can upload this here</small>`;
    } else note = `<small class="muted"> keep ready (not uploaded here)</small>`;
    return `<li><span class="mk">${mark}</span> ${escapeHtml(d.label)}${note}</li>`;
  }).join("") + `</ul>`;
}
