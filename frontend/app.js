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
let autoGpsWatchId = null;
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
    role: "taxi",
    group_tag: new URLSearchParams(window.location.search).get("group_tag") || null,
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
}


async function loadOperatorVoice() {
  const token = $("operatorAdminToken").value.trim();
  const groupTag = $("operatorGroupTag").value.trim();
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
}

function stopAutoGps() {
  if (autoGpsWatchId) navigator.geolocation.clearWatch(autoGpsWatchId);
  autoGpsWatchId = null;
  lastGpsPoint = null;
  updateAutoGpsStatus("Auto GPS: OFF");
}

async function loadPendingDrivers() {
  const token = $("operatorAdminToken")?.value.trim();
  const groupTag = $("operatorGroupTag")?.value.trim();
  const qs = new URLSearchParams();
  if (groupTag) qs.set("group_tag", groupTag);
  const resp = await fetch(`${API_BASE}/api/operator/pending-drivers?${qs.toString()}`, { headers: { "X-Admin-Token": token } });
  if (!resp.ok) return;
  const data = await resp.json();
  const host = $("operatorPendingList");
  if (!host) return;
  host.innerHTML = (data.items || []).map(d => `<div style="margin:8px 0;">${d.name || d.phone} (${d.group_tag || '-'}) <button class="outline" data-approve="${d.id}">Approve</button></div>`).join("") || "No pending drivers";
  host.querySelectorAll("button[data-approve]").forEach((btn) => btn.onclick = async () => {
    const id = btn.getAttribute("data-approve");
    const r = await fetch(`${API_BASE}/api/operator/drivers/${id}/approve`, { method: "POST", headers: { "X-Admin-Token": token } });
    if (r.ok) {
      await loadPendingDrivers();
      await loadOperatorDashboard();
    }
  });
}

window.addEventListener("DOMContentLoaded", () => {
  renderAuthState();
  updateRequestCodeButton();
  tripActive = !!localStorage.getItem("current_trip_id");
  applyBranding();
  if (getToken()) startCbInboxPolling();

  if (isOperatorMode()) {
    $("btnLoadOperator")?.addEventListener("click", async () => { await loadOperatorDashboard(); await loadOperatorVoice(); await loadPendingDrivers(); });
    initOperatorMap();
    applyBranding();
    return;
  }

  $("btnSendCode")?.addEventListener("click", requestCode);
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
});
