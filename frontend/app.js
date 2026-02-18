const API_BASE = window.location.origin;


let requestCodeCooldownTimer = null;
let requestCodeCooldownLeft = 0;

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
  if (requestCodeCooldownTimer) {
    clearInterval(requestCodeCooldownTimer);
    requestCodeCooldownTimer = null;
  }

  requestCodeCooldownLeft = Math.max(0, Number(seconds) || 0);
  updateRequestCodeButton();

  if (requestCodeCooldownLeft <= 0) {
    return;
  }

  requestCodeCooldownTimer = setInterval(() => {
    requestCodeCooldownLeft = Math.max(0, requestCodeCooldownLeft - 1);
    updateRequestCodeButton();
    if (requestCodeCooldownLeft === 0 && requestCodeCooldownTimer) {
      clearInterval(requestCodeCooldownTimer);
      requestCodeCooldownTimer = null;
    }
  }, 1000);
}

function $(id) {
  return document.getElementById(id);
}

function getToken() {
  return localStorage.getItem("driverSessionToken");
}

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
  const headers = { "Content-Type": "application/json", ...(fetchOptions.headers || {}) };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  if (resp.status === 401 && !skipUnauthorizedRedirect) {
    clearSession();
    renderAuthState();
    throw new Error("Unauthorized");
  }
  return resp;
}

function renderAuthState() {
  const hasToken = !!getToken();
  $("loginScreen").style.display = hasToken ? "none" : "block";
  $("dashboardScreen").style.display = hasToken ? "block" : "none";
  $("profileScreen").style.display = "none";

  if (hasToken) {
    updateHeaderProfile();
  }
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

  const resp = await apiFetch("/api/auth/request-code", {
    method: "POST",
    body: JSON.stringify(payload),
    skipUnauthorizedRedirect: true,
  });

  if (resp.status === 429) {
    let retryAfter = 120;
    try {
      const data = await resp.json();
      retryAfter = Number(data.retry_after || data?.detail?.retry_after || 120);
    } catch (err) {
      console.warn("cooldown parse error", err);
    }
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
  const payload = {
    phone: $("loginPhone").value.trim(),
    code: $("loginCode").value.trim(),
  };

  const resp = await apiFetch("/api/auth/verify-code", {
    method: "POST",
    body: JSON.stringify(payload),
    skipUnauthorizedRedirect: true,
  });
  if (!resp.ok) {
    $("authMessage").textContent = "Λάθος ή ληγμένος κωδικός.";
    return;
  }

  const data = await resp.json();
  setSession(data);
  renderAuthState();
}

async function startTrip() {
  const payload = {
    origin: $("tripOrigin").value.trim() || null,
    destination: $("tripDestination").value.trim() || null,
    notes: null,
  };
  const resp = await apiFetch("/api/v1/trips/start", { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) {
    alert("Σφάλμα εκκίνησης δρομολογίου.");
    return;
  }
  const data = await resp.json();
  localStorage.setItem("current_trip_id", String(data.id));
  $("tripStatus").textContent = `Trip #${data.id} ενεργό`;
}

async function finishTrip() {
  const tripId = localStorage.getItem("current_trip_id");
  if (!tripId) {
    alert("Δεν υπάρχει ενεργό δρομολόγιο.");
    return;
  }

  const payload = {
    notes: $("tripNotes").value.trim() || null,
    distance_km: null,
    avg_speed_kmh: null,
    safety_score: null,
  };
  const resp = await apiFetch(`/api/v1/trips/${tripId}/finish`, { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) {
    alert("Σφάλμα ολοκλήρωσης δρομολογίου.");
    return;
  }

  const data = await resp.json();
  $("tripStatus").textContent = `Trip #${data.id} ολοκληρώθηκε`;
  localStorage.removeItem("current_trip_id");
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
  if (!resp.ok) {
    alert("Σφάλμα αποστολής telemetry.");
    return;
  }
  $("telemetryNotes").value = "";
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
  const payload = {
    wallet_address: $("walletAddress").value.trim(),
    company_token_symbol: $("tokenSymbol").value.trim() || null,
  };
  const resp = await apiFetch("/api/wallet/link", { method: "POST", body: JSON.stringify(payload) });
  if (!resp.ok) {
    $("walletMessage").textContent = "Αποτυχία αποθήκευσης wallet.";
    return;
  }

  const profile = JSON.parse(localStorage.getItem("driverProfile") || "{}");
  profile.name = $("profileName").value.trim() || null;
  localStorage.setItem("driverProfile", JSON.stringify(profile));

  await apiFetch("/api/me", {
    method: "POST",
    body: JSON.stringify({ name: profile.name }),
  });

  $("walletMessage").textContent = "Το wallet αποθηκεύτηκε.";
  updateHeaderProfile();
}

window.addEventListener("DOMContentLoaded", () => {
  renderAuthState();
  updateRequestCodeButton();
  $("btnSendCode").addEventListener("click", requestCode);
  $("btnVerifyCode").addEventListener("click", verifyCode);

  $("btnStartTrip").addEventListener("click", startTrip);
  $("btnFinishTrip").addEventListener("click", finishTrip);
  $("btnSendTelemetry").addEventListener("click", sendTelemetry);

  $("btnOpenProfile").addEventListener("click", openProfile);
  $("btnCloseProfile").addEventListener("click", () => {
    $("profileScreen").style.display = "none";
    $("dashboardScreen").style.display = "block";
  });
  $("btnSaveWallet").addEventListener("click", saveWallet);
});
