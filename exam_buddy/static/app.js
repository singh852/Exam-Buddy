const API = "";
let token = sessionStorage.getItem("eb_token") || "";
let currentUser = null;
let currentProfile = {};
let authMode = "login";
let toastTimer;

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", "Bearer " + token);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(API + path, {...options, headers});
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) {
    if (response.status === 401 && token) {
      token = ""; sessionStorage.removeItem("eb_token");
    }
    throw new Error(data.detail || "Something went wrong. Please try again.");
  }
  return data;
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function showOnly(id) {
  ["home-view","auth-view","dashboard-view"].forEach(x => document.getElementById(x).classList.toggle("hidden", x !== id));
  document.getElementById("site-footer").classList.toggle("hidden", id === "dashboard-view");
  document.getElementById("nav-links").classList.toggle("hidden", id !== "home-view");
  document.getElementById("top-actions").classList.toggle("hidden", id === "dashboard-view");
}
function showHome() { showOnly("home-view"); window.scrollTo({top:0,behavior:"smooth"}); }
function openAuth(mode) {
  authMode = mode;
  showOnly("auth-view");
  document.getElementById("auth-error").textContent = "";
  document.getElementById("auth-form").reset();
  const isRegister = mode === "register";
  document.getElementById("name-label").classList.toggle("hidden", !isRegister);
  document.getElementById("consent-label").classList.toggle("hidden", !isRegister);
  document.getElementById("auth-name").required = isRegister;
  document.getElementById("auth-title").textContent = isRegister ? "Create your account" : "Welcome back";
  document.getElementById("auth-subtitle").textContent = isRegister ? "Start organising your exam preparation." : "Enter your details to continue.";
  document.getElementById("auth-submit").innerHTML = isRegister ? "Create account <span>→</span>" : "Log in <span>→</span>";
  document.getElementById("login-tab").classList.toggle("active", !isRegister);
  document.getElementById("register-tab").classList.toggle("active", isRegister);
  document.getElementById("auth-password").autocomplete = isRegister ? "new-password" : "current-password";
  window.scrollTo({top:0,behavior:"smooth"});
}
async function submitAuth(event) {
  event.preventDefault();
  const error = document.getElementById("auth-error");
  const button = document.getElementById("auth-submit");
  error.textContent = "";
  button.disabled = true;
  try {
    if (authMode === "register") {
      await api("/api/auth/register", {method:"POST", body:JSON.stringify({
        name:document.getElementById("auth-name").value.trim(),
        email:document.getElementById("auth-email").value.trim(),
        password:document.getElementById("auth-password").value,
        consent:document.getElementById("auth-consent").checked
      })});
      authMode = "login";
      document.getElementById("consent-label").classList.add("hidden");
      document.getElementById("auth-password").value = "";
      document.getElementById("auth-title").textContent = "Account created";
      document.getElementById("auth-subtitle").textContent = "Now log in with your new account.";
      document.getElementById("name-label").classList.add("hidden");
      document.getElementById("auth-name").required = false;
      document.getElementById("login-tab").classList.add("active");
      document.getElementById("register-tab").classList.remove("active");
      document.getElementById("auth-submit").innerHTML = "Log in <span>→</span>";
      error.className = "form-error";
      error.style.color = "#21865e";
      error.textContent = "Account created successfully. Please log in.";
    } else {
      const data = await api("/api/auth/login", {method:"POST", body:JSON.stringify({
        email:document.getElementById("auth-email").value.trim(),
        password:document.getElementById("auth-password").value
      })});
      token = data.token; currentUser = data.user;
      sessionStorage.setItem("eb_token", token);
      await enterDashboard();
    }
  } catch (e) { error.style.color = ""; error.textContent = e.message; }
  finally { button.disabled = false; }
}
async function enterDashboard() {
  try {
    const data = await api("/api/me");
    currentUser = data.user; currentProfile = data.profile || {};
    showOnly("dashboard-view");
    const initials = (currentUser.name || "S").trim().slice(0,1).toUpperCase();
    document.getElementById("user-avatar").textContent = initials;
    document.getElementById("header-avatar").textContent = initials;
    document.getElementById("sidebar-name").textContent = currentUser.name;
    document.getElementById("sidebar-role").textContent = currentUser.role === "admin" ? "Administrator" : "Student account";
    document.getElementById("admin-nav").classList.toggle("hidden", currentUser.role !== "admin");
    document.getElementById("docs-nav").classList.toggle("hidden", currentUser.role === "admin");
    await showDashboard("overview");
  } catch (e) { token = ""; sessionStorage.removeItem("eb_token"); showHome(); }
}
async function logout() {
  try { if (token) await api("/api/auth/logout", {method:"POST"}); } catch (_) {}
  token = ""; currentUser = null; sessionStorage.removeItem("eb_token"); showHome();
}
const pageMeta = {
  overview:["Overview","A clear view of your next steps."],
  profile:["My profile","Keep your basic details accurate."],
  documents:["Documents","Upload, organise, and review your files."],
  applications:["Applications","Prepare and track your application assistance."],
  support:["Help & support","Ask a question or check your requests."],
  admin:["Admin panel","Manage authorised records and support requests."],
  details:["Documents & details","Upload your documents and check the details we read from them."]
};
async function showDashboard(page) {
  if (!currentUser) return openAuth("login");
  document.querySelectorAll(".dash-page").forEach(el => el.classList.add("hidden"));
  document.getElementById("page-" + page)?.classList.remove("hidden");
  document.querySelectorAll(".side-link[data-page]").forEach(el => el.classList.toggle("active", el.dataset.page === page || (page === "details" && currentUser.role !== "admin" && el.dataset.page === "documents")));
  const meta = pageMeta[page] || pageMeta.overview;
  document.getElementById("dash-title").textContent = meta[0];
  document.getElementById("dash-subtitle").textContent = meta[1];
  hideToast();
  try {
    if (page === "overview") await loadOverview();
    if (page === "profile") fillProfile();
    if (page === "documents") await loadDocuments();
    if (page === "applications") { renderExamPicker(); await loadApplications(); }
    if (page === "details") await loadDetails();
    if (page === "support") await loadSupport();
    if (page === "admin") {
      if (currentUser.role !== "admin") throw new Error("Administrator access required.");
      await loadAdmin();
    }
  } catch(e) { showToast(e.message, true); }
  window.scrollTo({top:0,behavior:"smooth"});
}
function showToast(message, isError=false) {
  const el = document.getElementById("toast");
  el.textContent = message; el.classList.remove("hidden","error");
  if (isError) el.classList.add("error");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 5000);
}
function hideToast() { document.getElementById("toast").classList.add("hidden"); }
async function openPrivacy() {
  try { const info = await fetch("/api/privacy").then(r => r.json()); document.getElementById("retention-days").textContent = info.retention_days; } catch (_) {}
  document.getElementById("privacy-modal").classList.remove("hidden");
}
function closePrivacy() { document.getElementById("privacy-modal").classList.add("hidden"); }
async function deleteMyData() {
  if (!confirm("This permanently deletes ALL your uploaded documents, extracted details and application records. Continue?")) return;
  if (!confirm("Last check: this cannot be undone. Delete everything?")) return;
  try { const d = await api("/api/me/data", {method:"DELETE"}); showToast(d.message); showDashboard("overview"); }
  catch(e) { showToast(e.message, true); }
}
async function loadOverview() {
  const [docs, apps] = await Promise.all([api("/api/documents"),api("/api/applications")]);
  document.getElementById("welcome-name").textContent = `Welcome back, ${currentUser.name.split(" ")[0]}!`;
  document.getElementById("metric-documents").textContent = docs.length;
  document.getElementById("metric-apps").textContent = apps.length;
  document.getElementById("metric-pending").textContent = apps.filter(a => !["Completed","Cancelled"].includes(a.status)).length;
  const done = apps.filter(a => a.status === "Completed");
  document.getElementById("metric-completed").textContent = done.length;
  const names = [...new Set(done.map(a => a.exam_name))];
  document.getElementById("metric-completed-names").textContent = names.length ? names.join(", ") : "No exam completed yet";
  document.getElementById("metric-pending").nextElementSibling.textContent = (() => {
    const open = [...new Set(apps.filter(a => !["Completed","Cancelled"].includes(a.status)).map(a => a.exam_name))];
    return open.length ? open.join(", ") : "Not yet completed";
  })();
}
function fillProfile() {
  document.getElementById("profile-name").value = currentUser.name || "";
  document.getElementById("profile-email").value = currentUser.email || "";
  document.getElementById("profile-phone").value = currentProfile.phone || "";
  document.getElementById("profile-city").value = currentProfile.city || "";
  document.getElementById("profile-dob").value = currentProfile.date_of_birth || "";
}
async function saveProfile(event) {
  event.preventDefault();
  try {
    await api("/api/profile",{method:"PUT",body:JSON.stringify({
      phone:document.getElementById("profile-phone").value.trim(),
      city:document.getElementById("profile-city").value.trim(),
      date_of_birth:document.getElementById("profile-dob").value
    })});
    currentProfile = {phone:document.getElementById("profile-phone").value.trim(),city:document.getElementById("profile-city").value.trim(),date_of_birth:document.getElementById("profile-dob").value};
    showToast("Profile saved successfully.");
  } catch(e) { showToast(e.message,true); }
}
async function uploadDocument(event) {
  event.preventDefault();
  const file = document.getElementById("document-file").files[0];
  const err = document.getElementById("upload-error");
  err.textContent = "";
  if (!file) return;
  if (file.size > 8*1024*1024) { err.textContent = "File exceeds 8 MB."; return; }
  const button = event.submitter; if(button) button.disabled = true;
  try {
    const form = new FormData(); form.append("file",file);
    const data = await api("/api/documents",{method:"POST",body:form});
    document.getElementById("ocr-text").value = data.document.extracted_text || "";
    document.getElementById("upload-form").reset();
    await loadDocuments();
    showToast(data.message);
  } catch(e) { err.textContent = e.message; }
  finally { if(button) button.disabled = false; }
}
async function loadDocuments() {
  const docs = await api("/api/documents");
  const el = document.getElementById("document-list");
  if (!docs.length) { el.innerHTML = emptyState("No documents yet","Upload a test image or PDF to get started."); return; }
  el.innerHTML = docs.map(d => `<article class="record-card"><div class="record-symbol">▤</div><div class="record-main"><strong>${escapeHtml(d.original_name)}</strong><p>${escapeHtml(d.file_type.toUpperCase())} · ${Math.ceil(d.size_bytes/1024)} KB</p><div class="record-meta">${new Date(d.created_at).toLocaleString()} · ${d.extracted_text ? "OCR text extracted — review required" : "Stored; OCR text not available"}</div></div><div class="record-actions"><button class="btn btn-outline btn-sm" onclick="viewOcr(${d.id})">View text</button><button class="btn btn-outline btn-sm" onclick="deleteDocument(${d.id})">Delete</button></div></article>`).join("");
}
async function viewOcr(id) {
  try { const docs = await api("/api/documents"); const d = docs.find(x=>x.id===id); if(!d) throw new Error("Document not found."); document.getElementById("ocr-text").value = d.extracted_text || "No OCR text available for this file."; document.querySelector(".ocr-panel").scrollIntoView({behavior:"smooth"}); }
  catch(e) { showToast(e.message,true); }
}
async function deleteDocument(id) {
  if (!confirm("Delete this document from your local Exam Buddy workspace?")) return;
  try { const d=await api(`/api/documents/${id}`,{method:"DELETE"}); await loadDocuments(); showToast(d.message); }
  catch(e) { showToast(e.message,true); }
}
async function copyOcr() {
  const text = document.getElementById("ocr-text").value;
  try { await navigator.clipboard.writeText(text); showToast("Text copied."); }
  catch(_) { document.getElementById("ocr-text").select(); document.execCommand("copy"); showToast("Text copied if clipboard permission was available."); }
}
async function createApplication(event) {
  event.preventDefault();
  try {
    const wanted = document.getElementById("exam-name").value.trim().toLowerCase();
    const mine = await api("/api/applications");
    const same = mine.find(a => a.user_id === currentUser.id && a.exam_name.toLowerCase() === wanted && !["Completed","Cancelled"].includes(a.status));
    if (same) { showToast("You already have a record for this exam. Opening it."); openDetails(same.id); return; }
    await api("/api/applications",{method:"POST",body:JSON.stringify({
      exam_name:document.getElementById("exam-name").value.trim(),
      exam_session:document.getElementById("exam-session").value.trim(),
      notes:document.getElementById("exam-notes").value.trim()
    })});
    document.getElementById("exam-name").value=""; document.getElementById("exam-session").value=""; document.getElementById("exam-notes").value="";
    document.getElementById("exam-docs").innerHTML = "";
    document.querySelectorAll(".exam-card").forEach(el => el.classList.remove("picked"));
    await loadApplications(); showToast("Application record created. Press 'Documents & details' to upload your documents.");
  } catch(e) { showToast(e.message,true); }
}
function statusClass(status) { return status.toLowerCase().replaceAll(" ","-"); }
function statusOptions(current) {
  return ["Not Started","Documents Verified","In Progress","Needs Correction","Ready for Review","Filled","Awaiting OTP","Completed","Cancelled"].map(s=>`<option ${s===current?"selected":""}>${s}</option>`).join("");
}
async function loadApplications() {
  const apps = await api("/api/applications");
  const el = document.getElementById("application-list");
  if (!apps.length) { el.innerHTML = emptyState("No application records yet","Create a record above to start tracking your preparation."); return; }
  el.innerHTML = apps.map(a=>`<article class="record-card"><div class="record-symbol">✓</div><div class="record-main"><strong>${escapeHtml(a.exam_name)}${a.exam_session ? " · "+escapeHtml(a.exam_session):""}</strong><p>${escapeHtml(a.notes || "No notes added.")}</p><div class="record-meta">Updated ${new Date(a.updated_at).toLocaleString()}</div></div><div class="record-actions"><span class="status-pill ${statusClass(a.status)}">${escapeHtml(a.status)}</span><button class="btn btn-primary btn-sm" onclick="openDetails(${a.id})">Documents & details</button></div></article>`).join("");
}
async function saveApplication(id) {
  const status = document.getElementById(`status-${id}`).value;
  try { await api(`/api/applications/${id}`,{method:"PATCH",body:JSON.stringify({status})}); await loadApplications(); showToast("Application status updated."); }
  catch(e) { showToast(e.message,true); }
}
async function submitSupport(event) {
  event.preventDefault();
  try {
    await api("/api/support",{method:"POST",body:JSON.stringify({
      subject:document.getElementById("support-subject").value.trim(),
      message:document.getElementById("support-message").value.trim()
    })});
    document.getElementById("support-subject").value=""; document.getElementById("support-message").value="";
    await loadSupport(); showToast("Support request submitted.");
  } catch(e) { showToast(e.message,true); }
}
async function loadSupport() {
  const requests = await api("/api/support");
  const el = document.getElementById("support-list");
  if (!requests.length) { el.innerHTML = emptyState("No support requests","Any request you submit will appear here."); return; }
  el.innerHTML = requests.map(s=>`<article class="record-card"><div class="record-symbol">♡</div><div class="record-main"><strong>${escapeHtml(s.subject)}</strong><p>${escapeHtml(s.message)}</p><div class="record-meta">${new Date(s.created_at).toLocaleString()}</div></div><span class="status-pill ${statusClass(s.status)}">${escapeHtml(s.status)}</span></article>`).join("");
}
function emptyState(title, text) { return `<div class="empty-state"><strong>${escapeHtml(title)}</strong>${escapeHtml(text)}</div>`; }
async function loadAdmin() {
  const [summary,users,apps,support] = await Promise.all([api("/api/admin/summary"),api("/api/admin/users"),api("/api/applications"),api("/api/support")]);
  document.getElementById("admin-metrics").innerHTML = [
    ["Students",summary.students],["Applications",summary.applications],["Pending",summary.pending_applications],["Open support",summary.open_support_requests]
  ].map(([label,n])=>`<div class="admin-metric"><span>${label}</span><strong>${n}</strong></div>`).join("");
  document.getElementById("admin-users").innerHTML = users.length ? `<table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Applications</th><th>Joined</th></tr></thead><tbody>${users.map(u=>`<tr><td>${escapeHtml(u.name)}</td><td>${escapeHtml(u.email)}</td><td>${escapeHtml(u.role)}</td><td>${u.application_count}</td><td>${new Date(u.created_at).toLocaleDateString()}</td></tr>`).join("")}</tbody></table>` : emptyState("No users","Accounts will appear here.");
  adminAppList = apps;
  const filter = document.getElementById("admin-filter");
  if (!filter.options.length) filter.innerHTML = '<option value="">All statuses</option>' + ["Not Started","Documents Verified","In Progress","Needs Correction","Ready for Review","Filled","Awaiting OTP","Completed","Cancelled"].map(x => `<option>${x}</option>`).join("");
  renderAdminApps();
  try { renderActivity(await api("/api/admin/activity")); } catch (_) {}
  document.getElementById("admin-support").innerHTML = support.length ? support.map(s=>`<article class="record-card"><div class="record-symbol">♡</div><div class="record-main"><strong>${escapeHtml(s.subject)} · ${escapeHtml(s.student_name || "Student")}</strong><p>${escapeHtml(s.message)}</p><div class="record-meta">${escapeHtml(s.student_email || "")}</div></div><div class="record-actions"><span class="status-pill ${statusClass(s.status)}">${escapeHtml(s.status)}</span><select id="support-status-${s.id}"><option ${s.status==="Open"?"selected":""}>Open</option><option ${s.status==="In Progress"?"selected":""}>In Progress</option><option ${s.status==="Resolved"?"selected":""}>Resolved</option></select><button class="btn btn-outline btn-sm" onclick="adminSaveSupport(${s.id})">Update</button></div></article>`).join("") : emptyState("Inbox is clear","Support requests will appear here.");
}
let adminAppList = [];
function renderAdminApps() {
  const q = (document.getElementById("admin-search").value || "").trim().toLowerCase();
  const status = document.getElementById("admin-filter").value;
  const apps = adminAppList.filter(a => (!status || a.status === status) &&
    (!q || (a.exam_name + " " + (a.student_name || "") + " " + (a.student_email || "")).toLowerCase().includes(q)));
  document.getElementById("admin-applications").innerHTML = apps.length ? apps.map(a=>`<article class="record-card"><div class="record-symbol">✓</div><div class="record-main"><strong>${escapeHtml(a.exam_name)} · ${escapeHtml(a.student_name || "Student")}</strong><p>${escapeHtml(a.student_email || "")} · ${escapeHtml(a.exam_session || "No session specified")}</p><div class="record-meta">${escapeHtml(a.notes || "No notes")}</div></div><div class="record-actions"><span class="status-pill ${statusClass(a.status)}">${escapeHtml(a.status)}</span><select id="admin-status-${a.id}">${statusOptions(a.status)}</select><button class="btn btn-outline btn-sm" onclick="adminSaveApplication(${a.id})">Update</button><button class="btn btn-outline btn-sm" onclick="requestDocument(${a.id})">Request document</button><button class="btn btn-primary btn-sm" onclick="openDetails(${a.id})">View documents</button></div></article>`).join("") : emptyState("No matching records","Change the search or the status filter.");
}
async function requestDocument(id) {
  const message = prompt("What should the student upload or fix? (for example: Class 12 marksheet is blurry, please upload again)");
  if (!message || !message.trim()) return;
  const app = adminAppList.find(a => a.id === id);
  const notes = ((app && app.notes) ? app.notes + "\n" : "") + "Admin request: " + message.trim();
  try { await api(`/api/applications/${id}`, {method:"PATCH", body:JSON.stringify({status:"Needs Correction", notes})}); await loadAdmin(); showToast("Request sent. The student sees it in their notes and the status is Needs Correction."); }
  catch(e) { showToast(e.message, true); }
}
const ACTION_NAMES = {open_application:"Opened application", open_file:"Opened a document", set_status:"Changed status", form_open:"Opened a form", form_fill:"Filled a form page", reveal_aadhaar:"Showed full Aadhaar", delete_my_data:"Student deleted data", auto_delete:"Auto-deleted old documents"};
function renderActivity(rows) {
  document.getElementById("admin-activity").innerHTML = rows.length ? `<table><thead><tr><th>When</th><th>Who</th><th>Did</th><th>Student / exam</th><th>Detail</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${new Date(r.at).toLocaleString()}</td><td>${escapeHtml(r.actor_name || "")}</td><td>${escapeHtml(ACTION_NAMES[r.action] || r.action)}</td><td>${escapeHtml((r.student_name || "") + (r.exam_name ? " · " + r.exam_name : ""))}</td><td>${escapeHtml(r.detail || "")}</td></tr>`).join("")}</tbody></table>` : emptyState("No activity yet","Actions by staff will be listed here.");
}
async function revealAadhaar(id) {
  try { const d = await api(`/api/admin/applications/${id}/aadhaar`); document.getElementById("aadhaar-full").textContent = d.aadhaar_number || "(none)"; }
  catch(e) { showToast(e.message, true); }
}
function adminHelpers(data) {
  const exam = data.application.exam_name;
  const msg = `Hello! We are filling your ${exam} form. The exam website has just sent an OTP to your mobile number / email. Please send us that OTP within 10 minutes so we can continue. Only share it with us for this application, and never with anyone else.`;
  return `<div class="summary-card"><h4>Messages and status</h4><p class="muted tiny">When the exam site asks for an OTP, set the status to "Awaiting OTP" and send the student this message.</p><textarea id="otp-msg" rows="3" readonly>${escapeHtml(msg)}</textarea><div class="inline-actions"><button class="btn btn-outline btn-sm" onclick="copyValue(document.getElementById('otp-msg').value, 'OTP message')">Copy OTP message</button><select id="detail-status">${statusOptions(data.application.status)}</select><button class="btn btn-primary btn-sm" onclick="setStatusFromDetails(${data.application.id})">Set status</button></div></div>`;
}
async function setStatusFromDetails(id) {
  try { await api(`/api/applications/${id}`, {method:"PATCH", body:JSON.stringify({status:document.getElementById("detail-status").value})}); showToast("Status updated."); }
  catch(e) { showToast(e.message, true); }
}
async function adminSaveApplication(id) {
  const status = document.getElementById(`admin-status-${id}`).value;
  try { await api(`/api/applications/${id}`,{method:"PATCH",body:JSON.stringify({status})}); await loadAdmin(); showToast("Application status updated."); }
  catch(e) { showToast(e.message,true); }
}
async function adminSaveSupport(id) {
  const status = document.getElementById(`support-status-${id}`).value;
  try { await api(`/api/admin/support/${id}?status=${encodeURIComponent(status)}`,{method:"PATCH"}); await loadAdmin(); showToast("Support request updated."); }
  catch(e) { showToast(e.message,true); }
}
// ---------------------------------------------------------------- JEE documents + review screen
let currentAppId = null;
const DOC_TITLES = {
  aadhaar:["Aadhaar card","Front side with your name, date of birth and gender."],
  class10:["Class 10 marksheet","Clear photo or PDF of the full marksheet."],
  class12:["Class 12 marksheet","Clear photo or PDF of the full marksheet."]
};
// Sidebar "Documents": open (or create) the student's JEE Main application and show the upload screen.
async function openJee() {
  if (currentUser.role === "admin") return showDashboard("admin");
  try {
    const apps = await api("/api/applications");
    let jee = apps.find(a => a.exam_name === "JEE Main" && a.user_id === currentUser.id);
    if (!jee) jee = await api("/api/applications", {method:"POST", body:JSON.stringify({exam_name:"JEE Main", exam_session:"", notes:""})});
    openDetails(jee.id);
  } catch(e) { showToast(e.message, true); }
}
function openDetails(id) { currentAppId = id; showDashboard("details"); }

async function viewFile(docId) {
  try {
    const response = await fetch(`/api/documents/${docId}/file`, {headers:{Authorization:"Bearer "+token}});
    if (!response.ok) throw new Error("Could not open the file.");
    const blob = await response.blob();
    window.open(URL.createObjectURL(blob), "_blank");
  } catch(e) { showToast(e.message, true); }
}

async function copyValue(text, label) {
  if (!text) { showToast("Nothing to copy yet.", true); return; }
  try { await navigator.clipboard.writeText(text); }
  catch(_) { const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
  showToast(`${label} copied.`);
}
function copyField(button) { copyValue(button.parentElement.querySelector("input, select").value, button.dataset.label); }

// Combines the details from all documents into one list (Aadhaar first, then Class 12, then Class 10 where it makes sense).
function buildSummary(fields) {
  const pick = (key, order) => { for (const t of order) { const v = (fields[t] || {})[key]; if (v) return [v, t]; } return ["", ""]; };
  const docName = {aadhaar:"Aadhaar", class10:"Class 10", class12:"Class 12", extra:"Extra details"};
  const rows = [
    ["Name", ...pick("name", ["aadhaar","class10","class12"])],
    ["Date of birth", ...pick("dob", ["aadhaar","class10","class12"])],
    ["Gender", ...pick("gender", ["aadhaar"])],
    ["Father's name", ...pick("father_name", ["class12","class10"])],
    ["Mother's name", ...pick("mother_name", ["class12","class10"])],
    ["Aadhaar number", ...pick("aadhaar_number", ["aadhaar"])],
    ["Mobile", ...pick("phone", ["extra"])],
    ["Category", ...pick("category", ["extra"])],
    ["Address", ...pick("address", ["extra"])],
    ["City", ...pick("city", ["extra"])],
    ["State", ...pick("state", ["extra"])],
    ["Pincode", ...pick("pincode", ["extra"])]
  ];
  const warnings = [];
  for (const [key, label] of [["name","Name"],["dob","Date of birth"]]) {
    const seen = ["aadhaar","class10","class12"].map(t => [t, String((fields[t] || {})[key] || "").replace(/\s+/g," ").trim().toUpperCase()]).filter(x => x[1]);
    if (new Set(seen.map(x => x[1])).size > 1) warnings.push(`${label} is different across your documents: ` + seen.map(x => `${docName[x[0]]} = ${x[1]}`).join(", ") + ". Please check.");
  }
  let html = `<div class="summary-card"><h4>Candidate details (filled automatically)</h4><p class="muted tiny">Combined from your documents. Use Copy to paste a value into the official form.</p>`;
  html += warnings.map(w => `<p class="form-error">⚠ ${escapeHtml(w)}</p>`).join("");
  html += rows.map(([label, value, source]) => `<div class="summary-row"><span class="summary-label">${label}</span><span class="summary-value">${value ? escapeHtml(value) : "<i>not found yet</i>"}</span><small class="muted">${source ? "from " + docName[source] : ""}</small><button class="btn btn-outline btn-sm" data-label="${escapeHtml(label)}" data-value="${escapeHtml(value)}" onclick="copyValue(this.dataset.value, this.dataset.label)">Copy</button></div>`).join("");
  return html + `</div>`;
}

async function loadDetails() {
  const box = document.getElementById("details-body");
  if (!currentAppId) { box.innerHTML = emptyState("No application selected","Open one from the Applications page."); return; }
  const data = await api(`/api/applications/${currentAppId}/details`);
  const isAdmin = currentUser.role === "admin";
  document.getElementById("details-title").textContent = data.application.exam_name + " — documents & details";
  const status = data.confirmed ? "✓ You confirmed these details." : "Check every detail below against your original document, then press Confirm.";
  let html = `<p class="muted">${isAdmin ? "Student's confirmed details (read only)." : escapeHtml(status)}</p>`;
  const exam = findExam(data.application.exam_name);
  const needed = uploadTypesFor(data.application.exam_name);
  if (exam) html += `<div class="docs-box"><h4>Documents for ${escapeHtml(exam.name)}</h4>${docChecklistHtml(exam, data.documents)}<p class="muted tiny">Usual list only. Check the official notification for exact rules.</p></div>`;
  if ((data.warnings || []).length) html += `<div class="warn-box"><strong>Please check these before continuing</strong><ul>${data.warnings.map(w => `<li>${escapeHtml(w.text)}</li>`).join("")}</ul></div>`;
  if (data.masked) html += `<p class="muted tiny">The Aadhaar number is hidden (XXXX XXXX last-4). <button class="btn btn-outline btn-sm" onclick="revealAadhaar(${data.application.id})">Show full number (logged)</button> <span id="aadhaar-full"></span></p>`;
  html += buildSummary(data.fields);
  if (isAdmin) html += adminHelpers(data);
  if (isAdmin) html += formFillerPanel(data.application.id);
  for (const type of ["aadhaar","class10","class12"].filter(t => needed.includes(t))) {
    const [title, hint] = DOC_TITLES[type];
    const doc = data.documents.find(d => d.doc_type === type);
    const values = data.fields[type] || {};
    html += `<div class="doc-slot"><h4>${title}</h4><p class="muted tiny">${hint}</p>`;
    if (doc) html += `<p>📄 ${escapeHtml(doc.original_name)} <button class="btn btn-outline btn-sm" onclick="viewFile(${doc.id})">Open file</button></p>`;
    if (!isAdmin) html += `<div class="inline-actions"><input type="file" id="file-${type}" accept=".png,.jpg,.jpeg,.webp,.pdf"><button class="btn btn-primary btn-sm" onclick="uploadSlot('${type}')">${doc ? "Replace" : "Upload"}</button></div>`;
    if (doc) {
      html += `<details class="text-box" open><summary>Extracted text (full)</summary><textarea id="text-${type}" rows="8" readonly placeholder="No text could be read from this file.">${escapeHtml(doc.extracted_text || "")}</textarea><div class="inline-actions"><button class="btn btn-outline btn-sm" onclick="copyDocText('${type}')">Copy extracted text</button><span class="muted tiny">OCR can make mistakes. Always check against your original.</span></div></details>`;
      html += `<div class="form-grid">` + data.field_defs[type].map(f =>
        `<label>${escapeHtml(f.label)}<div class="field-row"><input data-doc="${type}" data-key="${f.key}" value="${escapeHtml(values[f.key] || "")}" maxlength="100" ${isAdmin ? "readonly" : ""}><button type="button" class="btn btn-outline btn-sm" data-label="${escapeHtml(f.label)}" onclick="copyField(this)">Copy</button></div></label>`
      ).join("") + `</div>`;
    }
    html += `</div>`;
  }
  html += extraSection(data, isAdmin);
  if (!isAdmin) html += `<div class="form-actions"><button class="btn btn-outline" onclick="saveDetails(false)">Save draft</button><button class="btn btn-primary" onclick="saveDetails(true)">Confirm details ✓</button></div>`;
  box.innerHTML = html;
}

// ---------------------------------------------------------------- extra details + photo/signature
const FILE_TITLES = {
  photo:["Passport-size photo","Clear, recent colour photo (JPG or PNG)."],
  signature:["Signature","Signature on plain white paper (JPG or PNG)."]
};
function fileLine(doc) {
  return doc ? `📄 ${escapeHtml(doc.original_name)} <button class="btn btn-outline btn-sm" onclick="viewFile(${doc.id})">Open file</button>` : `<span class="muted tiny">Nothing uploaded yet.</span>`;
}
function extraSection(data, isAdmin) {
  const values = data.fields.extra || {};
  let html = `<div class="doc-slot"><h4>Extra details</h4><p class="muted tiny">Most exam forms ask for these, and they are not on your documents. ${isAdmin ? "" : "Type them in yourself."}</p><div class="form-grid">`;
  html += (data.extra_defs || []).map(f => {
    const value = values[f.key] || "";
    const control = f.options
      ? `<select data-doc="extra" data-key="${f.key}" ${isAdmin ? "disabled" : ""}>${f.options.map(o => `<option value="${escapeHtml(o)}" ${o === value ? "selected" : ""}>${o || "— choose —"}</option>`).join("")}</select>`
      : `<input data-doc="extra" data-key="${f.key}" value="${escapeHtml(value)}" maxlength="300" ${isAdmin ? "readonly" : ""}>`;
    return `<label>${escapeHtml(f.label)}<div class="field-row">${control}<button type="button" class="btn btn-outline btn-sm" data-label="${escapeHtml(f.label)}" onclick="copyField(this)">Copy</button></div></label>`;
  }).join("");
  html += `</div></div>`;
  for (const type of ["photo","signature"].filter(t => uploadTypesFor(data.application.exam_name).includes(t))) {
    const [title, hint] = FILE_TITLES[type];
    const doc = data.documents.find(d => d.doc_type === type);
    html += `<div class="doc-slot"><h4>${title}</h4><p class="muted tiny">${hint}</p><p id="fileline-${type}">${fileLine(doc)}</p>`;
    if (!isAdmin) html += `<div class="inline-actions"><input type="file" id="file-${type}" accept=".png,.jpg,.jpeg,.webp"><button class="btn btn-primary btn-sm" onclick="uploadSlot('${type}')">${doc ? "Replace" : "Upload"}</button></div>`;
    html += `</div>`;
  }
  return html;
}

async function copyDocText(type) {
  const box = document.getElementById("text-" + type);
  if (!box || !box.value) { showToast("There is no extracted text to copy.", true); return; }
  try { await navigator.clipboard.writeText(box.value); showToast("Extracted text copied."); }
  catch(_) { box.select(); document.execCommand("copy"); showToast("Extracted text copied."); }
}

async function uploadSlot(type) {
  const file = document.getElementById("file-"+type).files[0];
  if (!file) { showToast("Choose a file first.", true); return; }
  if (file.size > 8*1024*1024) { showToast("File exceeds 8 MB.", true); return; }
  showToast("Reading your document… this can take a few seconds.");
  try {
    const form = new FormData();
    form.append("file", file); form.append("doc_type", type); form.append("application_id", currentAppId);
    const data = await api("/api/documents", {method:"POST", body:form});
    if (type === "photo" || type === "signature") {
      document.getElementById("fileline-" + type).innerHTML = fileLine({id: data.document.id, original_name: data.document.original_name});
      showToast(data.message);
    } else { await loadDetails(); showToast(data.message); }
  } catch(e) { showToast(e.message, true); }
}

async function saveDetails(confirmed) {
  const fields = {};
  document.querySelectorAll("#details-body [data-doc]").forEach(input => {
    (fields[input.dataset.doc] ||= {})[input.dataset.key] = input.value.trim();
  });
  if (confirmed && !confirm("Have you checked every detail against your original documents?")) return;
  try {
    const data = await api(`/api/applications/${currentAppId}/fields`, {method:"PUT", body:JSON.stringify({fields, confirmed})});
    await loadDetails(); showToast(data.message);
  } catch(e) { showToast(e.message, true); }
}

// ---------------------------------------------------------------- fill an online form (admin only)
function formFillerPanel(appId) {
  return `<div class="summary-card" id="form-filler"><h4>Fill an online form (Google Forms)</h4>
    <p class="muted tiny">Paste the form link. A browser window opens on THIS computer and the student's confirmed details are typed in. You check everything and press Submit yourself. Nothing is submitted, ticked or uploaded automatically.</p>
    <div class="inline-actions"><input id="form-url" class="grow" placeholder="https://docs.google.com/forms/d/e/.../viewform"><button class="btn btn-primary btn-sm" onclick="openForm(${appId})">Open form &amp; fill</button></div>
    <label class="tiny"><input type="checkbox" id="form-unconfirmed"> Fill even if the student has not confirmed their details</label>
    <div class="inline-actions"><button class="btn btn-outline btn-sm" onclick="fillAgain(${appId})">Fill this page again (use after pressing Next)</button><button class="btn btn-outline btn-sm" onclick="testBrowser()">Test browser</button><button class="btn btn-outline btn-sm" onclick="closeForm()">Close form window</button></div>
    <div id="form-report"></div></div>`;
}
function renderFormReport(r) {
  const li = (item, text) => `<li><b>${escapeHtml(item.label)}</b> — ${text}</li>`;
  document.getElementById("form-report").innerHTML =
    `<p><b>${escapeHtml(r.mode)}</b>${r.title ? ": " + escapeHtml(r.title) : ""}</p>
     <p>✅ ${r.filled.length} filled &nbsp;·&nbsp; ⚠ ${r.unsure.length} need you (yellow in the form) &nbsp;·&nbsp; ✋ ${r.left.length} left for you</p>
     <ul class="report-list">` +
    r.filled.map(i => li(i, `<span class="ok">${escapeHtml(i.value)}</span>`)).join("") +
    r.unsure.map(i => li(i, `<span class="warn">${escapeHtml(i.reason)}</span>`)).join("") +
    r.left.map(i => li(i, escapeHtml(i.reason))).join("") + `</ul>`;
}
function formStatus(html, isError=false) {
  const box = document.getElementById("form-report");
  if (box) box.innerHTML = `<p class="${isError ? "form-error" : "muted"}" style="font-size:14px">${html}</p>`;
}
async function runFormAction(path, body, busyText) {
  formStatus("⏳ " + escapeHtml(busyText));                       // stays on screen (not a vanishing pop-up)
  try { renderFormReport(await api(path, {method:"POST", body:JSON.stringify(body)})); }
  catch(e) { formStatus("❌ " + escapeHtml(e.message) + "<br>Press <b>Test browser</b> above to find the cause, and look at the black terminal window for red text.", true); }
}
async function testBrowser() {
  formStatus("⏳ Testing whether a browser window can start… (it may open and close by itself)");
  try { const d = await api("/api/admin/form/check", {method:"POST"}); formStatus("✅ " + escapeHtml(d.message)); }
  catch(e) { formStatus("❌ " + escapeHtml(e.message), true); }
}
function openForm(appId) {
  const url = document.getElementById("form-url").value.trim();
  if (!url) { showToast("Paste the form link first.", true); return; }
  runFormAction("/api/admin/form/open", {application_id: appId, url, allow_unconfirmed: document.getElementById("form-unconfirmed").checked}, "Opening the form… a browser window will appear.");
}
function fillAgain(appId) {
  runFormAction("/api/admin/form/fill", {application_id: appId, allow_unconfirmed: document.getElementById("form-unconfirmed").checked}, "Filling the page…");
}
async function closeForm() {
  try { const d = await api("/api/admin/form/close", {method:"POST"}); showToast(d.message); } catch(e) { showToast(e.message, true); }
}

window.addEventListener("DOMContentLoaded", async () => {
  if (token) await enterDashboard();
  else showHome();
});
