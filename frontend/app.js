const API_BASE = window.location.origin;

// ── i18n ──────────────────────────────────────────────────────────────────────
const LANG_DICT = {
  el: {
    login_title: "Σύνδεση οδηγού",
    login_subtitle: "Passwordless login με κινητό",
    phone_label: "Κινητό τηλέφωνο",
    email_label: "Email (προαιρετικό)",
    name_label: "Όνομα (προαιρετικό)",
    org_label: "Φορέας (προαιρετικό)",
    send_code: "Αποστολή κωδικού",
    code_label: "Κωδικός 6 ψηφίων",
    verify_btn: "Επιβεβαίωση",
    col_name: "Όνομα / Τηλέφωνο",
    col_status: "Κατάσταση",
    col_created: "Εγγραφή",
    col_last_login: "Τελ. Σύνδεση",
    col_kyc: "KYC",
    col_actions: "Ενέργειες",
    approve: "APPROVE",
    delete_btn: "Διαγραφή",
    kyc_verified: "KYC ✓",
    kyc_pending: "Verify KYC",
    kyc_mark_ok: "✓ Mark OK",
    no_data: "Χωρίς δεδομένα",
    save: "Αποθήκευση",
    marketplace_title: "Marketplace δρομολογίων",
    marketplace_desc: "Εμφανίσου στους φορείς ως ελεύθερος οδηγός και ανάλαβε ανοιχτά δρομολόγια.",
    marketplace_optin: "Είμαι διαθέσιμος στο marketplace",
    marketplace_city: "Πόλη σου",
    marketplace_open_jobs: "Ανοιχτά δρομολόγια:",
    marketplace_claim: "Ανάληψη",
    marketplace_claimed: "Στάλθηκε αίτηση",
    marketplace_no_jobs: "Δεν υπάρχουν ανοιχτά δρομολόγια.",
  },
  de: {
    login_title: "Fahrer-Anmeldung",
    login_subtitle: "Passwortfreie Anmeldung per Handy",
    phone_label: "Handynummer",
    email_label: "E-Mail (optional)",
    name_label: "Name (optional)",
    org_label: "Organisation (optional)",
    send_code: "Code senden",
    code_label: "6-stelliger Code",
    verify_btn: "Bestätigen",
    col_name: "Name / Telefon",
    col_status: "Status",
    col_created: "Registriert",
    col_last_login: "Letzter Login",
    col_kyc: "KYC",
    col_actions: "Aktionen",
    approve: "GENEHMIGEN",
    delete_btn: "Löschen",
    kyc_verified: "KYC ✓",
    kyc_pending: "KYC prüfen",
    kyc_mark_ok: "✓ Bestätigen",
    no_data: "Keine Daten",
    save: "Speichern",
    marketplace_title: "Auftrag-Marktplatz",
    marketplace_desc: "Erscheine bei Organisationen als freier Fahrer und übernimm offene Aufträge.",
    marketplace_optin: "Ich bin verfügbar im Marktplatz",
    marketplace_city: "Deine Stadt",
    marketplace_open_jobs: "Offene Aufträge:",
    marketplace_claim: "Übernehmen",
    marketplace_claimed: "Anfrage gesendet",
    marketplace_no_jobs: "Keine offenen Aufträge.",
  },
};
function getLang() { return localStorage.getItem("lang") || "el"; }
function t(key) { return (LANG_DICT[getLang()] || LANG_DICT.el)[key] || key; }
function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (el.tagName === "BUTTON" || el.tagName === "LABEL" || el.tagName === "DIV" || el.tagName === "SPAN") {
      el.textContent = t(key);
    }
  });
  const btn = document.getElementById("btnLangToggle");
  if (btn) btn.textContent = getLang() === "el" ? "DE" : "EL";
}
function toggleLang() {
  localStorage.setItem("lang", getLang() === "el" ? "de" : "el");
  applyLang();
}

let requestCodeCooldownTimer = null;
let requestCodeCooldownLeft = 0;
let mediaRecorder = null;
let mediaChunks = [];
let mediaStopTimeout = null;
let operatorMap = null;
let operatorMarkers = [];
let tripActive = false;
let cbInboxTimer = null;
let autoGpsWatchId = null;
let autoGpsSendTimer = null;
let lastGpsPoint = null;
const DEFAULT_FAVICON = "https://thronoschain.org/thronos-coin.png";

function $(id) { return document.getElementById(id); }
function isOperatorMode() { return window.location.pathname.startsWith('/operator') || window.location.pathname.startsWith('/school'); }
function isSchoolMode() { return window.location.pathname.startsWith('/school'); }

function toast(msg) { alert(msg); }

function setFavicon(url) {
  let link = document.getElementById("favicon") || document.querySelector("link[rel~='icon']");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    link.id = "favicon";
    document.head.appendChild(link);
  }
  link.href = url || DEFAULT_FAVICON;
}

async function applyBranding() {
  const qpGroup = new URLSearchParams(window.location.search).get("group_tag");
  let groupTag = qpGroup || null;
  if (!groupTag && getToken()) {
    try {
      const meResp = await apiFetch('/api/me', { skipUnauthorizedRedirect: true });
      if (meResp.ok) {
        const me = await meResp.json();
        groupTag = me.group_tag || null;
      }
    } catch (_) {}
  }

  const qs = groupTag ? `?group_tag=${encodeURIComponent(groupTag)}` : '';
  try {
    const resp = await fetch(`${API_BASE}/api/branding${qs}`);
    if (!resp.ok) return;
    const b = await resp.json();
    document.title = b.title || b.app_name || 'Thronos Driver';
    setFavicon(b.favicon_url);
    if (b.primary_color) document.documentElement.style.setProperty('--accent', b.primary_color);
  } catch (_) {}
}



async function loadOrganizations() {
  const sel = $("loginOrganization");
  if (!sel) return;
  try {
    const resp = await fetch(`${API_BASE}/api/organizations?status=active`);
    if (!resp.ok) return;
    const items = await resp.json();
    sel.innerHTML = '<option value="">— Ελεύθερος επαγγελματίας —</option>' + (items || []).map(o => { const label = (o.type === "transport" ? "Μεταφορική" : (o.type === "school" ? "Σχολή" : (o.type === "drone" ? "Drone" : "Taxi"))); return `<option value="${o.id}" data-group="${o.default_group_tag || ""}" data-type="${o.type || "taxi"}">${o.name} (${label})</option>`; }).join('');
    const opSel = $("operatorOrgSelect");
    if (opSel) {
      opSel.innerHTML = '<option value="">Επιλογή οργανισμού</option>' + (items || []).map(o => { const label = (o.type === "transport" ? "Μεταφορική" : (o.type === "school" ? "Σχολή" : (o.type === "drone" ? "Drone" : "Taxi"))); return `<option value="${o.id}" data-group="${o.default_group_tag || ""}">${o.name} (${label})</option>`; }).join('');
    }
  } catch (_) {}
}

function openRequestOrgModal() {
  if ($("requestOrgModal")) $("requestOrgModal").style.display = "block";
  if ($("loginScreen")) $("loginScreen").style.display = "none";
}

function closeRequestOrgModal() {
  if ($("requestOrgModal")) $("requestOrgModal").style.display = "none";
  if ($("loginScreen") && !getToken()) $("loginScreen").style.display = "block";
}

async function submitOrganizationRequest() {
  const payload = {
    name: $("orgReqName")?.value.trim(),
    city: $("orgReqCity")?.value.trim() || null,
    contact_email: $("orgReqEmail")?.value.trim() || null,
    type: $("orgReqType")?.value || "taxi",
  };
  const resp = await fetch(`${API_BASE}/api/organizations/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  $("orgReqMsg").textContent = resp.ok ? "Το αίτημα καταχωρήθηκε." : "Αποτυχία αιτήματος.";
}

function updateRequestCodeButton() {
  const btn = $("btnSendCode");
  if (!btn) return;
  if (requestCodeCooldownLeft > 0) {
    btn.disabled = true;
    btn.textContent = `Αποστολή ξανά σε ${requestCodeCooldownLeft}s`;
  } else {
    btn.disabled = false;
    btn.textContent = "Αποστολή κωδικού";
  }
}

function startRequestCodeCooldown(seconds) {
  if (requestCodeCooldownTimer) clearInterval(requestCodeCooldownTimer);
  requestCodeCooldownLeft = Math.max(0, Number(seconds) || 0);
  updateRequestCodeButton();
  if (requestCodeCooldownLeft <= 0) return;
  requestCodeCooldownTimer = setInterval(() => {
    requestCodeCooldownLeft = Math.max(0, requestCodeCooldownLeft - 1);
    updateRequestCodeButton();
    if (requestCodeCooldownLeft === 0) {
      clearInterval(requestCodeCooldownTimer);
      requestCodeCooldownTimer = null;
    }
  }, 1000);
}

function getToken() { return localStorage.getItem("driverSessionToken"); }
function setSession(data) {
  localStorage.setItem("driverSessionToken", data.session_token);
  localStorage.setItem("driverProfile", JSON.stringify(data.driver));
}
function clearSession() {
  localStorage.removeItem("driverSessionToken");
  localStorage.removeItem("driverProfile");
  localStorage.removeItem("current_trip_id");
}

async function apiFetch(path, options = {}) {
  const { skipUnauthorizedRedirect = false, ...fetchOptions } = options;
  const headers = { ...(fetchOptions.headers || {}) };
  if (!(fetchOptions.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  if (resp.status === 401 && !skipUnauthorizedRedirect && !isOperatorMode()) {
    clearSession();
    renderAuthState();
    throw new Error("Unauthorized");
  }
  return resp;
}

function renderAuthState() {
  if (isOperatorMode()) {
    $("loginScreen").style.display = "none";
    $("dashboardScreen").style.display = "none";
    $("profileScreen").style.display = "none";
    $("operatorScreen").style.display = "block";
    $("operatorTitle").textContent = isSchoolMode() ? "Driving School Dashboard" : "Operator Dashboard";
    $("operatorTableTitle").textContent = isSchoolMode() ? "Μαθήματα / Instructors" : "Drivers";
    return;
  }

  const hasToken = !!getToken();
  $("loginScreen").style.display = hasToken ? "none" : "block";
  const sendBtn = $("btnSendCode"); if (sendBtn) sendBtn.style.display = hasToken ? "none" : "inline-flex";
  $("dashboardScreen").style.display = hasToken ? "block" : "none";
  if ($("requestOrgModal")) $("requestOrgModal").style.display = "none";
  $("profileScreen").style.display = "none";
  $("operatorScreen").style.display = "none";
  if (hasToken) updateHeaderProfile();
}


function renderCbInbox(items) {
  let box = document.getElementById('cbInbox');
  if (!box) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<div class="card-header"><div class="card-title">Inbox από Κέντρο</div></div><div id="cbInbox" class="small-text">-</div>';
    document.getElementById('dashboardScreen')?.appendChild(card);
    box = document.getElementById('cbInbox');
  }
  box.innerHTML = (items || []).map(i => {
    const audioUrl = i.audio_url || `/api/v1/voice-messages/${i.id}/download`;
    return `<div style="margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08);">
      <div>${i.note || 'Voice message'} · ${i.created_at || ''}</div>
      <audio controls preload="none" src="${audioUrl}" style="width:100%; margin:6px 0;"></audio>
      <button data-ack="${i.id}" class="outline">Ack</button>
    </div>`;
  }).join('') || 'No messages';
  box.querySelectorAll('button[data-ack]').forEach(b => b.onclick = async () => {
    await apiFetch(`/api/v1/voice-messages/${b.getAttribute('data-ack')}/ack`, { method: 'POST' });
    b.disabled = true;
    b.textContent = 'Acked';
  });
}

async function pollCbInbox() {
  if (!getToken()) return;
  const resp = await apiFetch('/api/v1/voice-messages/inbox', { skipUnauthorizedRedirect: true });
  if (!resp.ok) return;
  const data = await resp.json();
  renderCbInbox(data.items || []);
}

function startCbInboxPolling() {
  if (cbInboxTimer) clearInterval(cbInboxTimer);
  pollCbInbox();
  cbInboxTimer = setInterval(pollCbInbox, 12000);
}

function updateHeaderProfile() {
  const driver = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  $("loggedInAs").textContent = `Συνδεδεμένος ως: ${driver.name || driver.phone} (${driver.role || "taxi"})`;
}

async function requestCode() {
  const payload = {
    phone: $("loginPhone").value.trim(),
    email: $("loginEmail").value.trim() || null,
    name: $("loginName").value.trim() || null,
    role: $("loginOrganization")?.selectedOptions?.[0]?.getAttribute("data-type") || "taxi",
    organization_id: $("loginOrganization")?.value ? Number($("loginOrganization").value) : null,
  };

  const resp = await apiFetch("/api/auth/request-code", { method: "POST", body: JSON.stringify(payload), skipUnauthorizedRedirect: true });
  if (resp.status === 429) {
    const data = await resp.json();
    const retryAfter = Number(data.retry_after || 120);
    startRequestCodeCooldown(retryAfter);
    $("authMessage").textContent = `Περίμενε ${retryAfter}s πριν ζητήσεις νέο κωδικό.`;
    return;
  }
  if (!resp.ok) {
    $("authMessage").textContent = "Αποτυχία αποστολής κωδικού.";
    return;
  }

  const data = await resp.json();
  $("codeWrap").style.display = "block";
  $("authMessage").textContent = `Στάλθηκε 6-ψήφιος κωδικός (${data.delivery}) στο ${data.masked}.`;
  startRequestCodeCooldown(120);
}

async function verifyCode() {
  const payload = { phone: $("loginPhone").value.trim(), code: $("loginCode").value.trim() };
  const resp = await apiFetch("/api/auth/verify-code", { method: "POST", body: JSON.stringify(payload), skipUnauthorizedRedirect: true });
  if (!resp.ok) {
    $("authMessage").textContent = "Λάθος ή ληγμένος κωδικός.";
    return;
  }
  const data = await resp.json();
  setSession(data);
  await enrichDriverProfile();
  renderAuthState();
  afterLoginSetup();
  startCbInboxPolling();
}

async function enrichDriverProfile() {
  try {
    const resp = await apiFetch("/api/me", { skipUnauthorizedRedirect: true });
    if (!resp.ok) return;
    const me = await resp.json();
    const profile = JSON.parse(localStorage.getItem("driverProfile") || "{}");
    profile.org_type = me.org_type || null;
    profile.org_name = me.org_name || null;
    profile.organization_id = me.organization_id || null;
    profile.marketplace_opt_in = !!me.marketplace_opt_in;
    profile.city = me.city || null;
    localStorage.setItem("driverProfile", JSON.stringify(profile));
  } catch (_) {}
}

function afterLoginSetup() {
  const profile = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  const studentsCard = $("studentsCard");
  if (studentsCard) {
    if (profile.role === "school") {
      studentsCard.style.display = "block";
      loadStudents();
    } else {
      studentsCard.style.display = "none";
    }
  }
  // Marketplace card: visible for taxi free professionals (no organization)
  const mkCard = $("marketplaceCard");
  if (mkCard) {
    const isFreePro = !profile.organization_id && (profile.role === "taxi" || !profile.role);
    mkCard.style.display = isFreePro ? "block" : "none";
    if (isFreePro) {
      if ($("marketplaceOptIn")) $("marketplaceOptIn").checked = !!profile.marketplace_opt_in;
      if ($("marketplaceCity")) $("marketplaceCity").value = profile.city || "";
      loadMarketplace();
    }
  }
}

async function loadStudents() {
  try {
    const resp = await apiFetch("/api/school/students", { skipUnauthorizedRedirect: true });
    if (!resp.ok) return;
    const data = await resp.json();
    const list = $("studentsList");
    if (!list) return;
    if (!data.students || !data.students.length) {
      list.textContent = "Δεν έχεις μαθητές ακόμα. Πρόσθεσε με το κινητό τους.";
      return;
    }
    list.innerHTML = data.students.map(s =>
      `<div style="margin:6px 0;padding:8px;background:rgba(255,255,255,0.05);border-radius:6px;">
        <strong>${s.name || s.phone}</strong> — ${s.phone}
        ${s.approved ? '<span style="color:var(--accent);margin-left:6px;">✓ Εγκεκριμένος</span>' : '<span style="opacity:0.6;margin-left:6px;">Αναμονή</span>'}
        ${s.total_trips ? ` &nbsp;|&nbsp; ${s.total_trips} δρομολόγια` : ''}
        ${s.score != null ? ` &nbsp;|&nbsp; Score: <strong>${s.score}</strong>/100` : ''}
      </div>`
    ).join('');
  } catch (_) {}
}

async function loadMarketplace() {
  const list = $("marketplaceList");
  if (!list) return;
  list.textContent = "…";
  try {
    const resp = await apiFetch("/api/driver/marketplace/assignments", { skipUnauthorizedRedirect: true });
    if (!resp.ok) { list.textContent = t("marketplace_no_jobs"); return; }
    const items = await resp.json();
    if (!items.length) { list.textContent = t("marketplace_no_jobs"); return; }
    list.innerHTML = items.map(a => {
      const from = a.origin_city || "?";
      const to = a.dest_city || "?";
      const when = a.depart_at ? new Date(a.depart_at).toLocaleString("el-GR", { dateStyle: "short", timeStyle: "short" }) : "—";
      return `<div style="padding:8px;margin:5px 0;background:rgba(255,255,255,0.05);border-radius:6px;">
        <div><strong>${from}</strong> → <strong>${to}</strong> &nbsp;|&nbsp; ${when}</div>
        ${a.notes ? `<div class="small-text" style="margin-top:2px;opacity:0.7;">${a.notes}</div>` : ""}
        <button class="outline" style="margin-top:6px;font-size:12px;padding:4px 10px;"
          onclick="claimAssignment(${a.id}, this)">${t("marketplace_claim")}</button>
      </div>`;
    }).join("");
  } catch (_) { list.textContent = t("marketplace_no_jobs"); }
}

async function claimAssignment(assignmentId, btn) {
  btn.disabled = true;
  btn.textContent = "…";
  const resp = await apiFetch(`/api/driver/assignments/${assignmentId}/claim`, { method: "POST" });
  if (resp.ok) {
    btn.textContent = t("marketplace_claimed");
    toast(t("marketplace_claimed"));
  } else {
    const err = await resp.json().catch(() => ({}));
    toast(err.detail || "Αποτυχία.");
    btn.disabled = false;
    btn.textContent = t("marketplace_claim");
  }
}

async function saveMarketplaceOptIn() {
  const opt_in = $("marketplaceOptIn")?.checked ?? false;
  const city = $("marketplaceCity")?.value.trim() || null;
  const msg = $("marketplaceSaveMsg");
  const resp = await apiFetch("/api/me/marketplace", {
    method: "POST",
    body: JSON.stringify({ opt_in, city }),
  });
  if (resp.ok) {
    if (msg) { msg.textContent = "✓ Αποθηκεύτηκε"; setTimeout(() => { if (msg) msg.textContent = ""; }, 2000); }
    // refresh marketplace list if opted in
    if (opt_in) loadMarketplace();
  } else {
    if (msg) msg.textContent = "Σφάλμα αποθήκευσης.";
  }
}

async function addStudent() {
  const phone = $("studentPhone")?.value.trim();
  const name = $("studentName")?.value.trim() || null;
  if (!phone) return toast("Εισήγαγε κινητό μαθητή.");
  const resp = await apiFetch("/api/school/students", {
    method: "POST",
    body: JSON.stringify({ phone, name }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    return toast(err.detail || "Αποτυχία προσθήκης μαθητή.");
  }
  if ($("studentPhone")) $("studentPhone").value = "";
  if ($("studentName")) $("studentName").value = "";
  await loadStudents();
}

async function loadNearbyOrgs() {
  const city = $("profileCity")?.value.trim() || null;
  const qs = "?type=taxi" + (city ? `&city=${encodeURIComponent(city)}` : "");
  try {
    const resp = await fetch(`${API_BASE}/api/organizations/nearby${qs}`);
    if (!resp.ok) return;
    const items = await resp.json();
    const sel = $("profileOrgSelect");
    if (!sel) return;
    sel.innerHTML = '<option value="">— Χωρίς φορέα —</option>' +
      (items || []).map(o => `<option value="${o.id}">${o.name}</option>`).join('');
    const wrap = $("nearbyOrgsWrap");
    if (wrap) wrap.style.display = items.length ? "block" : "none";
    if ($("orgPickerMsg")) $("orgPickerMsg").textContent = items.length
      ? `Βρέθηκαν ${items.length} φορείς Taxi.`
      : "Δεν βρέθηκαν ενεργοί φορείς.";
  } catch (_) {}
}

async function joinOrg() {
  const orgId = Number($("profileOrgSelect")?.value);
  if (!orgId) return toast("Επίλεξε φορέα από τη λίστα.");
  const resp = await apiFetch(`/api/organizations/${orgId}/join`, { method: "POST" });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    return toast(err.detail || "Αποτυχία αίτησης ένταξης.");
  }
  await enrichDriverProfile();
  if ($("orgPickerMsg")) $("orgPickerMsg").textContent = "Αίτηση ένταξης υποβλήθηκε. Αναμονή έγκρισης από τον φορέα.";
  if ($("nearbyOrgsWrap")) $("nearbyOrgsWrap").style.display = "none";
}

async function startTrip() {
  const payload = { origin: $("tripOrigin").value.trim() || null, destination: $("tripDestination").value.trim() || null, notes: null };
  const resp = await apiFetch("/api/v1/trips/start", { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) return toast("Σφάλμα εκκίνησης δρομολογίου.");
  const data = await resp.json();
  localStorage.setItem("current_trip_id", String(data.id));
  tripActive = true;
  $("tripStatus").textContent = `Trip #${data.id} ενεργό`;
}

async function finishTrip() {
  const tripId = localStorage.getItem("current_trip_id");
  if (!tripId) return toast("Δεν υπάρχει ενεργό δρομολόγιο.");
  const payload = { notes: $("tripNotes").value.trim() || null, distance_km: null, avg_speed_kmh: null, safety_score: null };
  const resp = await apiFetch(`/api/v1/trips/${tripId}/finish`, { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) return toast("Σφάλμα ολοκλήρωσης δρομολογίου.");
  const data = await resp.json();
  $("tripStatus").textContent = `Trip #${data.id} ολοκληρώθηκε`;
  localStorage.removeItem("current_trip_id");
  tripActive = false;
  stopAutoGps();
}

async function sendTelemetry() {
  const tripId = localStorage.getItem("current_trip_id");
  const payload = {
    trip_id: tripId ? Number(tripId) : null,
    latitude: $("gpsLat").value ? Number($("gpsLat").value) : null,
    longitude: $("gpsLng").value ? Number($("gpsLng").value) : null,
    speed_kmh: $("speed").value ? Number($("speed").value) : null,
    accel: null,
    brake_hard: $("brakeHard").checked,
    accel_hard: $("accelHard").checked,
    cornering_hard: $("cornerHard").checked,
    road_type: null,
    weather: $("weather").value || null,
    raw_notes: $("telemetryNotes").value.trim() || null,
  };
  const resp = await apiFetch("/api/v1/telemetry", { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) return toast("Σφάλμα αποστολής telemetry.");
  $("telemetryNotes").value = "";
}


async function sendTelemetrySnapshot() {
  if (!tripActive) return;
  await sendTelemetry();
}

async function startVoiceRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    return toast("Η συσκευή δεν υποστηρίζει εγγραφή ήχου.");
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = (e) => { if (e.data?.size) mediaChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (mediaStopTimeout) clearTimeout(mediaStopTimeout);
      await uploadVoice();
    };
    mediaRecorder.start();
    $("voiceStatus").textContent = "Γίνεται εγγραφή... (max 30s)";
    $("btnVoiceRecord").disabled = true;
    $("btnVoiceStop").disabled = false;
    mediaStopTimeout = setTimeout(() => { if (mediaRecorder?.state === "recording") mediaRecorder.stop(); }, 30000);
  } catch (err) {
    console.error(err);
    toast("Αδυναμία πρόσβασης στο μικρόφωνο.");
  }
  $("telemetryNotes").value = "";
}

async function stopVoiceRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
  $("btnVoiceStop").disabled = true;
}

async function uploadVoice() {
  try {
    const blob = new Blob(mediaChunks, { type: "audio/webm" });
    const form = new FormData();
    form.append("file", blob, `voice-${Date.now()}.webm`);
    const tripId = localStorage.getItem("current_trip_id");
    if (tripId) form.append("trip_id", tripId);
    form.append("target", "center");
    const resp = await apiFetch("/api/v1/voice-messages/send", { method: "POST", body: form });
    if (!resp.ok) throw new Error("upload failed");
    $("voiceStatus").textContent = "Το φωνητικό μήνυμα στάλθηκε.";
    toast("Voice sent");
  } catch (err) {
    console.error(err);
    $("voiceStatus").textContent = "Αποτυχία αποστολής voice.";
    toast("Voice upload error");
  } finally {
    $("btnVoiceRecord").disabled = false;
    $("btnVoiceStop").disabled = true;
  }
}

async function openProfile() {
  $("dashboardScreen").style.display = "none";
  $("profileScreen").style.display = "block";
  // Refresh org info before showing
  await enrichDriverProfile();
  const driver = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  $("profilePhone").value = driver.phone || "";
  $("profileName").value = driver.name || "";
  $("profileRole").value = driver.role || "taxi";

  const orgLocked = $("orgLockedSection");
  const orgPicker = $("orgPickerSection");
  const orgType = driver.org_type;
  const lockedTypes = ["school", "transport", "drone"];

  if (driver.organization_id && lockedTypes.includes(orgType)) {
    // Non-taxi org member: read-only, cannot change
    if (orgLocked) orgLocked.style.display = "block";
    if (orgPicker) orgPicker.style.display = "none";
    if ($("profileOrgName")) $("profileOrgName").value = driver.org_name || `Φορέας #${driver.organization_id}`;
    const roleLabel = orgType === "school" ? "Σχολή Οδήγησης" : orgType === "transport" ? "Μεταφορική" : "Drone";
    if ($("profileOrgStatus")) $("profileOrgStatus").textContent =
      `${roleLabel} · ${driver.approved ? "✓ Εγκεκριμένος" : "⏳ Αναμονή έγκρισης"}`;
  } else {
    // Taxi or free professional: show org picker
    if (orgLocked) orgLocked.style.display = "none";
    if (orgPicker) orgPicker.style.display = "block";
    if (driver.organization_id && orgType === "taxi") {
      if ($("orgPickerMsg")) $("orgPickerMsg").textContent =
        `Φορέας: ${driver.org_name || "#" + driver.organization_id} · ${driver.approved ? "✓ Εγκεκριμένος" : "⏳ Αναμονή έγκρισης"}`;
    }
  }

  const walletResp = await apiFetch("/api/wallet");
  if (walletResp.ok) {
    const wallet = await walletResp.json();
    $("walletAddress").value = wallet.wallet_address || "";
    $("tokenSymbol").value = wallet.company_token_symbol || "";
  }
}

async function saveWallet() {
  const payload = { wallet_address: $("walletAddress").value.trim(), company_token_symbol: $("tokenSymbol").value.trim() || null };
  const resp = await apiFetch("/api/wallet/link", { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) return ($("walletMessage").textContent = "Αποτυχία αποθήκευσης wallet.");
  const profile = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  profile.name = $("profileName").value.trim() || null;
  localStorage.setItem("driverProfile", JSON.stringify(profile));
  await apiFetch("/api/me", { method: "POST", body: JSON.stringify({ name: profile.name }) });
  $("walletMessage").textContent = "Το wallet αποθηκεύτηκε.";
  updateHeaderProfile();
}

function initOperatorMap() {
  if (!window.L || !$("operatorMap") || operatorMap) return;
  operatorMap = L.map("operatorMap").setView([40.64, 22.94], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap" }).addTo(operatorMap);
}

function kycBadge(driverId, kycStatus) {
  if (kycStatus === "verified") {
    return `<span style="color:var(--accent);font-weight:600;">${t("kyc_verified")}</span>`;
  }
  return `<a href="https://verifyid.thronoschain.org/?driver_id=${driverId}" target="_blank" rel="noopener" style="font-size:10px;opacity:0.8;">${t("kyc_pending")}</a>` +
    ` <button class="outline" style="padding:2px 5px;font-size:10px;" onclick="approveKyc(${driverId})">${t("kyc_mark_ok")}</button>`;
}

async function deleteDriver(driverId) {
  if (!confirm(`${t("delete_btn")} driver #${driverId}?`)) return;
  const token = getOperatorToken();
  const resp = await fetch(`${API_BASE}/api/operator/drivers/${driverId}`, {
    method: "DELETE",
    headers: { "X-Admin-Token": token },
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    return toast(err.detail || "Delete failed");
  }
  await loadOperatorDashboard();
  await loadPendingDrivers();
}

async function approveKyc(driverId) {
  const token = getOperatorToken();
  const resp = await fetch(`${API_BASE}/api/operator/drivers/${driverId}/kyc`, {
    method: "POST",
    headers: { "X-Admin-Token": token, "Content-Type": "application/json" },
    body: JSON.stringify({ status: "verified" }),
  });
  if (!resp.ok) return toast("KYC update failed");
  await loadOperatorDashboard();
}

function renderOperatorData(data) {
  initOperatorMap();
  if (operatorMap) {
    operatorMarkers.forEach((m) => operatorMap.removeLayer(m));
    operatorMarkers = [];
  }

  const rows = (data.drivers || []).map((d) => {
    const tel = d.last_telemetry || {};
    if (operatorMap && tel.lat && tel.lng) {
      const marker = L.marker([tel.lat, tel.lng]).addTo(operatorMap).bindPopup(`${d.name || d.phone} (${d.last_trip_status})`);
      operatorMarkers.push(marker);
    }
    const created = d.created_at ? d.created_at.split("T")[0] : "-";
    const lastLogin = d.last_login_at ? d.last_login_at.split("T")[0] : "-";
    const kyc = kycBadge(d.id, d.kyc_status);
    const approvedBadge = d.approved ? "" : ` <span style="opacity:0.5;font-size:10px;">(pending)</span>`;
    return `<tr>
      <td>${d.name || "-"}${approvedBadge}<br><small style="opacity:0.6">${d.phone || ""}</small></td>
      <td>${d.last_trip_status || "-"}</td>
      <td>${created}</td>
      <td>${lastLogin}</td>
      <td>${kyc}</td>
      <td><button class="outline" style="padding:2px 6px;font-size:10px;color:#ff6b6b;" onclick="deleteDriver(${d.id})">${t("delete_btn")}</button></td>
    </tr>`;
  }).join("");

  $("operatorMeta").textContent = `${isSchoolMode() ? "Active lessons" : "Active drivers"}: ${data.active_drivers || 0}`;
  $("operatorTable").innerHTML = `<table style="width:100%;font-size:12px;border-collapse:collapse;"><thead><tr style="text-align:left;border-bottom:1px solid rgba(255,255,255,0.15);">
    <th style="padding:4px 6px;">${t("col_name")}</th>
    <th style="padding:4px 6px;">${t("col_status")}</th>
    <th style="padding:4px 6px;">${t("col_created")}</th>
    <th style="padding:4px 6px;">${t("col_last_login")}</th>
    <th style="padding:4px 6px;">${t("col_kyc")}</th>
    <th style="padding:4px 6px;">${t("col_actions")}</th>
  </tr></thead><tbody>${rows || `<tr><td colspan="6" style="padding:8px 6px;opacity:0.5;">${t("no_data")}</td></tr>`}</tbody></table>`;
}

function getOperatorToken() {
  return $("operatorAdminToken")?.value.trim() || localStorage.getItem("operator_token") || "";
}

function getOperatorGroupTag() {
  return localStorage.getItem("operator_group_tag") || "";
}

function openOperatorLoginModal() {
  $("operatorLoginModal")?.style && ($("operatorLoginModal").style.display = "block");
}

function closeOperatorLoginModal() {
  $("operatorLoginModal")?.style && ($("operatorLoginModal").style.display = "none");
}

function submitOperatorLogin() {
  const token = $("operatorAdminToken")?.value.trim() || "";
  const group = $("operatorOrgSelect")?.selectedOptions?.[0]?.getAttribute("data-group") || "";
  if (token) localStorage.setItem("operator_token", token);
  localStorage.setItem("operator_group_tag", group || "");
  if ($("operatorAuthState")) $("operatorAuthState").textContent = token ? "Authenticated" : "Not authenticated";
  closeOperatorLoginModal();
}

async function loadOperatorDashboard() {
  const token = getOperatorToken();
  const groupTag = getOperatorGroupTag();
  const qs = new URLSearchParams();
  if (groupTag) qs.set("group_tag", groupTag);
  const resp = await fetch(`${API_BASE}/api/operator/dashboard?${qs.toString()}`, { headers: { "X-Admin-Token": token } });
  if (!resp.ok) return toast("Operator auth/data error");
  const data = await resp.json();
  renderOperatorData(data);
}


async function logout() {
  const token = localStorage.getItem("session_token") || getToken();
  localStorage.removeItem("session_token");
  localStorage.removeItem("me");
  localStorage.removeItem("driverSessionToken");
  localStorage.removeItem("driverProfile");

  try {
    if (token) {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    }
  } catch (e) {
    console.warn("logout failed", e);
  }

  renderAuthState();
  window.location.href = "/app";
}


async function loadOperatorVoice() {
  const token = getOperatorToken();
  const groupTag = getOperatorGroupTag();
  const qs = new URLSearchParams();
  if (groupTag) qs.set('group_tag', groupTag);
  const resp = await fetch(`${API_BASE}/api/v1/voice-messages/operator-inbox?${qs.toString()}`, { headers: { 'X-Admin-Token': token } });
  if (!resp.ok) return;
  const data = await resp.json();
  let host = document.getElementById('operatorVoiceList');
  if (!host) {
    const c=document.createElement('div'); c.className='card'; c.innerHTML='<div class="card-title">Voice/CB</div><div id="operatorVoiceList"></div>';
    document.getElementById('operatorScreen')?.appendChild(c); host=document.getElementById('operatorVoiceList');
  }
  host.innerHTML=(data.items||[]).map(i=>`<div style="margin:8px 0;">#${i.id} driver:${i.driver_id} <audio controls preload="none" src="${i.audio_url || `/api/v1/voice-messages/${i.id}/download`}" style="width:100%;margin:6px 0;"></audio><button data-driver="${i.driver_id}" class="outline">Reply</button></div>`).join('')||'No voice';
  host.querySelectorAll('button[data-driver]').forEach(btn=>btn.onclick=()=>replyOperatorVoice(btn.getAttribute('data-driver')));
}

async function replyOperatorVoice(driverId) {
  const token = getOperatorToken();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks=[];
  const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' });
  rec.ondataavailable=e=>{ if(e.data?.size) chunks.push(e.data); };
  rec.onstop=async()=>{
    stream.getTracks().forEach(t=>t.stop());
    const form=new FormData();
    form.append('file', new Blob(chunks,{type:'audio/webm'}), `reply-${Date.now()}.webm`);
    form.append('note','reply');
    form.append("driver_id", String(driverId));
    form.append("target", "driver");
    const r=await fetch(`${API_BASE}/api/v1/voice-messages/reply-to-driver`, { method:'POST', headers:{'X-Admin-Token':token}, body:form });
    if(r.ok) toast('Reply sent'); else toast('Reply failed');
  };
  rec.start();
  setTimeout(()=>{ if(rec.state==='recording') rec.stop(); }, 5000);
}


function updateAutoGpsStatus(text) {
  if ($("autoGpsStatus")) $("autoGpsStatus").textContent = text;
}

function estimateSpeedKmh(prev, curr) {
  if (!prev || !curr || !prev.ts || !curr.ts) return null;
  const dt = (curr.ts - prev.ts) / 1000;
  if (dt <= 0) return null;
  const R = 6371000;
  const toRad = (v) => (v * Math.PI) / 180;
  const dLat = toRad(curr.lat - prev.lat);
  const dLon = toRad(curr.lng - prev.lng);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(prev.lat)) * Math.cos(toRad(curr.lat)) * Math.sin(dLon / 2) ** 2;
  const d = 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return (d / dt) * 3.6;
}

function startAutoGps() {
  if (!navigator.geolocation) return toast("Geolocation not supported");
  if (!tripActive) return toast("Ξεκίνα πρώτα διαδρομή.");
  if (autoGpsWatchId) return;
  autoGpsWatchId = navigator.geolocation.watchPosition((pos) => {
    const lat = pos.coords.latitude;
    const lng = pos.coords.longitude;
    let speed = pos.coords.speed != null ? Number(pos.coords.speed) * 3.6 : null;
    const nowPoint = { lat, lng, ts: Date.now() };
    if (speed == null) speed = estimateSpeedKmh(lastGpsPoint, nowPoint);
    lastGpsPoint = nowPoint;
    if ($("gpsLat")) $("gpsLat").value = lat.toFixed(6);
    if ($("gpsLng")) $("gpsLng").value = lng.toFixed(6);
    if ($("speed") && speed != null) $("speed").value = speed.toFixed(1);
    updateAutoGpsStatus("Auto GPS: ON");
  }, (err) => {
    updateAutoGpsStatus(`Auto GPS error: ${err.message}`);
  }, { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 });

  if (autoGpsSendTimer) clearInterval(autoGpsSendTimer);
  autoGpsSendTimer = setInterval(() => { sendTelemetrySnapshot().catch(() => {}); }, 8000);
}

function stopAutoGps() {
  if (autoGpsWatchId) navigator.geolocation.clearWatch(autoGpsWatchId);
  if (autoGpsSendTimer) clearInterval(autoGpsSendTimer);
  autoGpsWatchId = null;
  autoGpsSendTimer = null;
  lastGpsPoint = null;
  updateAutoGpsStatus("Auto GPS: OFF");
}

async function loadPendingDrivers() {
  const token = getOperatorToken();
  const groupTag = getOperatorGroupTag();
  const qs = new URLSearchParams();
  if (groupTag) qs.set("group_tag", groupTag);
  const resp = await fetch(`${API_BASE}/api/operator/pending-drivers?${qs.toString()}`, { headers: { "X-Admin-Token": token } });
  if (!resp.ok) return;
  const data = await resp.json();
  const host = $("operatorPendingList");
  if (!host) return;
  const items = data.items || [];
  host.innerHTML = items.map(d => {
    const date = d.created_at ? d.created_at.split("T")[0] : "";
    const kyc = d.kyc_status === "verified" ? ` <span style="color:var(--accent);font-size:10px;">KYC✓</span>` : "";
    return `<div style="margin:8px 0;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
      <span>${d.name || d.phone}${kyc}</span>
      <small style="opacity:0.5;">${d.phone || ""} ${date ? "· " + date : ""}</small>
      <button class="outline" style="padding:2px 8px;font-size:10px;" data-approve="${d.id}">${t("approve")}</button>
      <button class="outline" style="padding:2px 8px;font-size:10px;color:#ff6b6b;" data-del="${d.id}">${t("delete_btn")}</button>
    </div>`;
  }).join("") || "No pending drivers";
  host.querySelectorAll("button[data-approve]").forEach((btn) => btn.onclick = async () => {
    const id = btn.getAttribute("data-approve");
    const r = await fetch(`${API_BASE}/api/operator/drivers/${id}/approve`, { method: "POST", headers: { "X-Admin-Token": token } });
    if (r.ok) { await loadPendingDrivers(); await loadOperatorDashboard(); }
  });
  host.querySelectorAll("button[data-del]").forEach((btn) => btn.onclick = async () => {
    await deleteDriver(btn.getAttribute("data-del"));
  });
}



async function loadPendingClaims() {
  const token = getOperatorToken();
  const resp = await fetch(`${API_BASE}/api/operator/claims/pending`, { headers: { "X-Admin-Token": token } });
  if (!resp.ok) return;
  const data = await resp.json();
  const host = $("operatorClaimsList");
  if (!host) return;
  host.innerHTML = (data.items || []).map(i => `<div style="margin:8px 0;">claim #${i.claim_id} assignment #${i.assignment_id} driver ${i.driver_id} <button class="outline" data-claim="${i.claim_id}">Approve</button></div>`).join("") || "No pending claims";
  host.querySelectorAll("button[data-claim]").forEach((btn) => btn.onclick = async () => {
    const id = btn.getAttribute("data-claim");
    const r = await fetch(`${API_BASE}/api/operator/claims/${id}/approve`, { method: "POST", headers: { "X-Admin-Token": token } });
    if (r.ok) await loadPendingClaims();
  });
}

// ── Billing / trial ──────────────────────────────────────────────────────────

function openPaymentModal() {
  const modal = $("paymentModal");
  if (modal) modal.style.display = "block";
  // Highlight radio selection visually
  document.querySelectorAll("input[name='planPeriod']").forEach(r => {
    r.addEventListener("change", () => {
      $("planMonthly").style.borderColor = r.value === "monthly" ? "var(--accent)" : "rgba(255,255,255,0.15)";
      $("planYearly").style.borderColor  = r.value === "yearly"  ? "var(--accent)" : "rgba(255,255,255,0.15)";
    });
  });
}

function closePaymentModal() {
  const modal = $("paymentModal");
  if (modal) modal.style.display = "none";
}

async function startCheckout() {
  const period = document.querySelector("input[name='planPeriod']:checked")?.value || "monthly";
  const token = getOperatorToken();
  const btn = $("btnGoToStripe");
  const msg = $("checkoutMsg");
  if (btn) btn.disabled = true;
  if (msg) msg.textContent = "Σύνδεση με Stripe…";
  try {
    const resp = await fetch(`${API_BASE}/api/operator/billing/checkout`, {
      method: "POST",
      headers: { "X-Admin-Token": token, "Content-Type": "application/json" },
      body: JSON.stringify({ period }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      if (msg) msg.textContent = data.detail || "Σφάλμα σύνδεσης Stripe.";
      if (btn) btn.disabled = false;
      return;
    }
    if (data.checkout_url) {
      window.location.href = data.checkout_url;
    }
  } catch (e) {
    if (msg) msg.textContent = "Σφάλμα δικτύου. Δοκίμασε ξανά.";
    if (btn) btn.disabled = false;
  }
}

async function loadBillingStatus() {
  const token = getOperatorToken();
  if (!token) return;
  try {
    const resp = await fetch(`${API_BASE}/api/operator/billing`, {
      headers: { "X-Admin-Token": token },
    });
    if (!resp.ok) return;  // global admin or network error — skip
    const b = await resp.json();
    renderTrialBanner(b);
    renderAddons(b);
  } catch (_) {}
}

function renderAddons(b) {
  const card = $("addonsCard");
  if (!card) return;
  card.style.display = "block";

  const ctrl = $("addonMarketplaceCtrl");
  if (!ctrl) return;

  if (b.marketplace_addon) {
    ctrl.innerHTML = `<span style="color:var(--accent);font-weight:600;font-size:13px;">✓ Ενεργό</span>`;
  } else {
    ctrl.innerHTML = `<div class="small-text" style="margin-bottom:6px;opacity:0.7;">+€19/μήνα</div>
      <button class="primary" style="font-size:12px;padding:6px 14px;white-space:nowrap;"
        onclick="startAddonCheckout('marketplace')">Αγορά →</button>`;
  }
}

async function startAddonCheckout(addonType) {
  const token = getOperatorToken();
  const btn = event?.target;
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const resp = await fetch(`${API_BASE}/api/operator/billing/addon`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Token": token },
      body: JSON.stringify({ addon_type: addonType }),
    });
    const data = await resp.json();
    if (resp.ok && data.checkout_url) {
      window.location.href = data.checkout_url;
    } else {
      toast(data.detail || "Σφάλμα Stripe.");
      if (btn) { btn.disabled = false; btn.textContent = "Αγορά →"; }
    }
  } catch (_) {
    toast("Σφάλμα σύνδεσης.");
    if (btn) { btn.disabled = false; btn.textContent = "Αγορά →"; }
  }
}

function renderTrialBanner(b) {
  const banner = $("trialBanner");
  if (!banner) return;

  const days = b.trial_days_remaining;
  const expired = b.trial_expired;
  const active = b.plan_status === "active";

  if (active) {
    banner.style.display = "none";
    return;
  }

  let color, icon, msg, showBtn;
  if (expired) {
    color = "#ff4444";
    icon = "🔴";
    msg = "Η δοκιμαστική περίοδος έληξε. Η πρόσβαση είναι περιορισμένη.";
    showBtn = true;
  } else if (days !== null && days <= 3) {
    color = "#ffaa00";
    icon = "⚠️";
    msg = `Η trial λήγει σε <strong>${days}</strong> ${days === 1 ? "μέρα" : "μέρες"}! Αναβάθμισε πριν χάσεις πρόσβαση.`;
    showBtn = true;
  } else if (days !== null) {
    color = "var(--accent)";
    icon = "🟢";
    msg = `Trial · <strong>${days}</strong> ${days === 1 ? "μέρα" : "μέρες"} απομένουν`;
    showBtn = days <= 7;
  } else {
    banner.style.display = "none";
    return;
  }

  banner.style.display = "block";
  banner.innerHTML = `<div style="background:rgba(0,0,0,0.4);border:1px solid ${color};border-radius:10px;padding:12px 16px;margin-bottom:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <span style="font-size:18px;">${icon}</span>
    <span class="small-text" style="flex:1;">${msg}</span>
    ${showBtn ? `<button class="primary" style="padding:6px 14px;font-size:12px;" onclick="openPaymentModal()">Αναβάθμιση →</button>` : ""}
  </div>`;
}

window.addEventListener("DOMContentLoaded", () => {
  applyLang();
  renderAuthState();
  updateRequestCodeButton();
  loadOrganizations();
  tripActive = !!localStorage.getItem("current_trip_id");
  applyBranding();

  if (isOperatorMode()) {
    if ($("operatorAuthState")) $("operatorAuthState").textContent = getOperatorToken() ? "Authenticated" : "Not authenticated";
    $("btnOperatorLogin")?.addEventListener("click", openOperatorLoginModal);
    $("btnCloseOperatorLogin")?.addEventListener("click", closeOperatorLoginModal);
    $("btnSubmitOperatorLogin")?.addEventListener("click", submitOperatorLogin);
    $("btnLoadOperator")?.addEventListener("click", async () => {
      await loadOperatorDashboard(); await loadOperatorVoice();
      await loadPendingDrivers(); await loadPendingClaims();
      await loadBillingStatus();
    });
    $("btnClosePaymentModal")?.addEventListener("click", closePaymentModal);
    initOperatorMap();
    applyBranding();

    // Handle Stripe redirect callbacks
    const qp = new URLSearchParams(window.location.search);
    if (qp.get("payment") === "success") {
      toast("Η πληρωμή ολοκληρώθηκε! Η συνδρομή σας είναι ενεργή.");
      history.replaceState({}, "", window.location.pathname);
    } else if (qp.get("payment") === "cancelled") {
      toast("Η πληρωμή ακυρώθηκε. Μπορείς να δοκιμάσεις ξανά όποτε θέλεις.");
      history.replaceState({}, "", window.location.pathname);
    } else if (qp.get("addon") === "marketplace_success") {
      toast("✅ Το Marketplace add-on ενεργοποιήθηκε!");
      history.replaceState({}, "", window.location.pathname);
    } else if (qp.get("addon") === "marketplace_cancelled") {
      toast("Η αγορά add-on ακυρώθηκε.");
      history.replaceState({}, "", window.location.pathname);
    }

    // Auto-load when redirected from landing page with token pre-set
    if (qp.get("autoload") === "1" && getOperatorToken()) {
      if ($("operatorAuthState")) $("operatorAuthState").textContent = "Authenticated — Loading…";
      setTimeout(async () => {
        await loadOperatorDashboard();
        await loadOperatorVoice();
        await loadPendingDrivers();
        await loadPendingClaims();
        await loadBillingStatus();
        if ($("operatorAuthState")) $("operatorAuthState").textContent = "Authenticated";
      }, 300);
    }
    return;
  }

  $("btnSendCode")?.addEventListener("click", requestCode);
  $("btnOperatorLogin")?.addEventListener("click", openOperatorLoginModal);
  $("btnCloseOperatorLogin")?.addEventListener("click", closeOperatorLoginModal);
  $("btnSubmitOperatorLogin")?.addEventListener("click", submitOperatorLogin);
  $("btnRequestOrg")?.addEventListener("click", openRequestOrgModal);
  $("btnCloseRequestOrg")?.addEventListener("click", closeRequestOrgModal);
  $("btnSubmitRequestOrg")?.addEventListener("click", submitOrganizationRequest);
  $("btnVerifyCode")?.addEventListener("click", verifyCode);
  $("btnStartTrip")?.addEventListener("click", startTrip);
  $("btnFinishTrip")?.addEventListener("click", finishTrip);
  $("btnSendTelemetry")?.addEventListener("click", sendTelemetry);
  $("btnStartAutoGps")?.addEventListener("click", startAutoGps);
  $("btnStopAutoGps")?.addEventListener("click", stopAutoGps);
  $("btnVoiceRecord")?.addEventListener("click", startVoiceRecording);
  $("btnVoiceStop")?.addEventListener("click", stopVoiceRecording);
  $("btnOpenProfile")?.addEventListener("click", openProfile);
  $("btnCloseProfile")?.addEventListener("click", () => {
    $("profileScreen").style.display = "none";
    $("dashboardScreen").style.display = "block";
  });
  $("btnSaveWallet")?.addEventListener("click", saveWallet);
  $("logoutBtn")?.addEventListener("click", logout);
  // Org picker (taxi free professionals)
  $("btnFindOrgs")?.addEventListener("click", loadNearbyOrgs);
  $("btnJoinOrg")?.addEventListener("click", joinOrg);
  // School student management
  $("btnAddStudent")?.addEventListener("click", addStudent);
  $("btnRefreshStudents")?.addEventListener("click", loadStudents);
  // Marketplace (free professionals)
  $("btnSaveMarketplace")?.addEventListener("click", saveMarketplaceOptIn);
  $("btnRefreshMarketplace")?.addEventListener("click", loadMarketplace);
  // Restore students card & CB inbox if already logged in
  if (getToken()) {
    afterLoginSetup();
    startCbInboxPolling();
  }
});
