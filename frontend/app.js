const API_BASE = window.location.origin;

let requestCodeCooldownTimer = null;
let requestCodeCooldownLeft = 0;
let mediaRecorder = null;
let mediaChunks = [];
let mediaStopTimeout = null;
let operatorMap = null;
let operatorMarkers = [];
let tripActive = false;
let cbInboxTimer = null;

function $(id) { return document.getElementById(id); }
function isOperatorMode() { return window.location.pathname.startsWith('/operator') || window.location.pathname.startsWith('/school'); }
function isSchoolMode() { return window.location.pathname.startsWith('/school'); }

function toast(msg) { alert(msg); }

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
    document.title = b.app_name || 'Thronos Driver';
    const favicon = document.getElementById('faviconLink');
    if (favicon && b.favicon_url) favicon.href = b.favicon_url;
    if (b.primary_color) document.documentElement.style.setProperty('--accent', b.primary_color);
  } catch (_) {}
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
  box.innerHTML = (items || []).map(i => `<div style="margin-bottom:8px;"><div>${i.note || 'Voice message'} · ${i.created_at || ''}</div><button data-ack="${i.id}" class="outline">Ack</button></div>`).join('') || 'No messages';
  box.querySelectorAll('button[data-ack]').forEach(b => b.onclick = async () => {
    await apiFetch(`/api/v1/voice-messages/${b.getAttribute('data-ack')}/ack`, { method: 'POST' });
    b.disabled = true;
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
    role: "taxi",
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
  renderAuthState();
  startCbInboxPolling();
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
    form.append("target", "cb");
    const resp = await apiFetch("/api/v1/voice-messages", { method: "POST", body: form });
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
  const driver = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  $("profilePhone").value = driver.phone || "";
  $("profileName").value = driver.name || "";
  $("profileRole").value = driver.role || "taxi";
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

function renderOperatorData(data) {
  initOperatorMap();
  if (operatorMap) {
    operatorMarkers.forEach((m) => operatorMap.removeLayer(m));
    operatorMarkers = [];
  }

  const rows = (data.drivers || []).map((d) => {
    const t = d.last_telemetry || {};
    if (operatorMap && t.lat && t.lng) {
      const marker = L.marker([t.lat, t.lng]).addTo(operatorMap).bindPopup(`${d.name || d.phone} (${d.last_trip_status})`);
      operatorMarkers.push(marker);
    }
    return `<tr><td>${d.name || d.phone || '-'}</td><td>${d.last_trip_status || '-'}</td><td>${t.speed ?? '-'}</td><td>${t.timestamp || '-'}</td></tr>`;
  }).join("");

  $("operatorMeta").textContent = `${isSchoolMode() ? 'Active lessons' : 'Active drivers'}: ${data.active_drivers || 0}`;
  $("operatorTable").innerHTML = `<table style="width:100%;font-size:12px;"><thead><tr><th>Name</th><th>Status</th><th>Speed</th><th>Last ts</th></tr></thead><tbody>${rows || '<tr><td colspan="4">No data</td></tr>'}</tbody></table>`;
}

async function loadOperatorDashboard() {
  const token = $("operatorAdminToken").value.trim();
  const groupTag = $("operatorGroupTag").value.trim();
  const qs = new URLSearchParams();
  if (groupTag) qs.set("group_tag", groupTag);
  const resp = await fetch(`${API_BASE}/api/operator/dashboard?${qs.toString()}`, { headers: { "X-Admin-Token": token } });
  if (!resp.ok) return toast("Operator auth/data error");
  const data = await resp.json();
  renderOperatorData(data);
}


function logout() {
  if (tripActive) {
    if (!confirm("Έχεις ενεργή διαδρομή. Θέλεις σίγουρα να αποσυνδεθείς; Αυτό θα ακυρώσει τη διαδρομή.")) return;
  }
  const token = getToken();
  try { localStorage.removeItem("driverSessionToken"); } catch (e) {}
  try { localStorage.removeItem("driverProfile"); } catch (e) {}
  fetch(`${API_BASE}/api/auth/logout`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .finally(() => { window.location.href = "/"; });
}


async function loadOperatorVoice() {
  const token = $("operatorAdminToken").value.trim();
  const groupTag = $("operatorGroupTag").value.trim();
  const qs = new URLSearchParams();
  if (groupTag) qs.set('group_tag', groupTag);
  const resp = await fetch(`${API_BASE}/api/operator/voice/recent?${qs.toString()}`, { headers: { 'X-Admin-Token': token } });
  if (!resp.ok) return;
  const data = await resp.json();
  let host = document.getElementById('operatorVoiceList');
  if (!host) {
    const c=document.createElement('div'); c.className='card'; c.innerHTML='<div class="card-title">Voice/CB</div><div id="operatorVoiceList"></div>';
    document.getElementById('operatorScreen')?.appendChild(c); host=document.getElementById('operatorVoiceList');
  }
  host.innerHTML=(data.items||[]).map(i=>`<div style="margin:8px 0;">#${i.id} driver:${i.driver_id} <button data-reply="${i.id}" class="outline">Reply</button></div>`).join('')||'No voice';
  host.querySelectorAll('button[data-reply]').forEach(btn=>btn.onclick=()=>replyOperatorVoice(btn.getAttribute('data-reply')));
}

async function replyOperatorVoice(id) {
  const token = $("operatorAdminToken").value.trim();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const chunks=[];
  const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' });
  rec.ondataavailable=e=>{ if(e.data?.size) chunks.push(e.data); };
  rec.onstop=async()=>{
    stream.getTracks().forEach(t=>t.stop());
    const form=new FormData();
    form.append('file', new Blob(chunks,{type:'audio/webm'}), `reply-${Date.now()}.webm`);
    form.append('note','reply');
    const r=await fetch(`${API_BASE}/api/operator/voice/${id}/reply`, { method:'POST', headers:{'X-Admin-Token':token}, body:form });
    if(r.ok) toast('Reply sent'); else toast('Reply failed');
  };
  rec.start();
  setTimeout(()=>{ if(rec.state==='recording') rec.stop(); }, 5000);
}

window.addEventListener("DOMContentLoaded", () => {
  renderAuthState();
  updateRequestCodeButton();
  tripActive = !!localStorage.getItem("current_trip_id");
  applyBranding();
  if (getToken()) startCbInboxPolling();

  if (isOperatorMode()) {
    $("btnLoadOperator")?.addEventListener("click", async () => { await loadOperatorDashboard(); await loadOperatorVoice(); });
    initOperatorMap();
    applyBranding();
    return;
  }

  $("btnSendCode")?.addEventListener("click", requestCode);
  $("btnVerifyCode")?.addEventListener("click", verifyCode);
  $("btnStartTrip")?.addEventListener("click", startTrip);
  $("btnFinishTrip")?.addEventListener("click", finishTrip);
  $("btnSendTelemetry")?.addEventListener("click", sendTelemetry);
  $("btnVoiceRecord")?.addEventListener("click", startVoiceRecording);
  $("btnVoiceStop")?.addEventListener("click", stopVoiceRecording);
  $("btnOpenProfile")?.addEventListener("click", openProfile);
  $("btnCloseProfile")?.addEventListener("click", () => {
    $("profileScreen").style.display = "none";
    $("dashboardScreen").style.display = "block";
  });
  $("btnSaveWallet")?.addEventListener("click", saveWallet);
});
