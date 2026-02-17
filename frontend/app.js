const API_BASE = window.location.origin;

function $(id) {
  return document.getElementById(id);
}

function saveProfile() {
  const profile = {
    driverName: $("driverName").value.trim(),
    phone: $("driverPhone").value.trim(),
    company: $("taxiCompany").value.trim(),
    plate: $("plateNumber").value.trim(),
  };
  localStorage.setItem("driver_profile", JSON.stringify(profile));
}

function loadProfile() {
  try {
    const raw = localStorage.getItem("driver_profile");
    if (!raw) return;
    const p = JSON.parse(raw);
    $("driverName").value = p.driverName || "";
    $("driverPhone").value = p.phone || "";
    $("taxiCompany").value = p.company || "";
    $("plateNumber").value = p.plate || "";
  } catch (err) {
    console.error("profile load error", err);
  }
}

async function ensureDriver() {
  const name = $("driverName").value.trim();
  if (!name) {
    alert("Βάλε όνομα οδηγού (όπως θα εμφανίζεται στο dashboard)");
    return null;
  }

  const payload = {
    name,
    phone: $("driverPhone").value.trim() || null,
    taxi_company: $("taxiCompany").value.trim() || null,
    plate_number: $("plateNumber").value.trim() || null,
    notes: null,
  };

  try {
    const resp = await fetch(`${API_BASE}/api/v1/drivers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const txt = await resp.text();
      console.error("driver create error", txt);
      alert("Σφάλμα δημιουργίας οδηγού. Δες τα logs.");
      return null;
    }
    const data = await resp.json();
    localStorage.setItem("driver_id", String(data.id));
    return data.id;
  } catch (err) {
    console.error("driver create fetch error", err);
    alert("Δε μπόρεσα να μιλήσω με τον server (driver).");
    return null;
  }
}

async function startTrip() {
  let driverId = localStorage.getItem("driver_id");
  if (!driverId) {
    driverId = await ensureDriver();
    if (!driverId) return;
  }

  const origin = $("tripOrigin").value.trim() || null;
  const dest = $("tripDestination").value.trim() || null;

  const payload = {
    driver_id: Number(driverId),
    origin,
    destination: dest,
    notes: null,
  };

  try {
    const resp = await fetch(`${API_BASE}/api/v1/trips/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const txt = await resp.text();
      console.error("trip start error", txt);
      alert("Σφάλμα εκκίνησης δρομολογίου.");
      return;
    }
    const data = await resp.json();
    localStorage.setItem("current_trip_id", String(data.id));
    $("tripStatus").textContent = `Trip #${data.id} ενεργό`;
  } catch (err) {
    console.error("trip start fetch error", err);
    alert("Δε μπόρεσα να μιλήσω με τον server (trip start).");
  }
}

async function finishTrip() {
  const tripId = localStorage.getItem("current_trip_id");
  if (!tripId) {
    alert("Δεν υπάρχει ενεργό δρομολόγιο.");
    return;
  }

  const payload = {
    distance_km: null,
    avg_speed_kmh: null,
    safety_score: null,
    notes: $("tripNotes").value.trim() || null,
  };

  try {
    const resp = await fetch(`${API_BASE}/api/v1/trips/${tripId}/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const txt = await resp.text();
      console.error("trip finish error", txt);
      alert("Σφάλμα ολοκλήρωσης δρομολόγίου.");
      return;
    }
    const data = await resp.json();
    $("tripStatus").textContent = `Trip #${data.id} ολοκληρώθηκε`;
    localStorage.removeItem("current_trip_id");
  } catch (err) {
    console.error("trip finish fetch error", err);
    alert("Δε μπόρεσα να μιλήσω με τον server (trip finish).");
  }
}

async function sendTelemetry() {
  let driverId = localStorage.getItem("driver_id");
  if (!driverId) {
    driverId = await ensureDriver();
    if (!driverId) return;
  }
  const tripId = localStorage.getItem("current_trip_id");

  const payload = {
    driver_id: Number(driverId),
    trip_id: tripId ? Number(tripId) : null,
    latitude: $("gpsLat").value ? Number($("gpsLat").value) : null,
    longitude: $("gpsLng").value ? Number($("gpsLng").value) : null,
    speed_kmh: $("speed").value ? Number($("speed").value) : null,
    accel: null,
    brake_hard: $("brakeHard").checked,
    accel_hard: $("accelHard").checked,
    cornering_hard: $("cornerHard").checked,
    road_type: $("roadType").value || null,
    weather: $("weather").value || null,
    raw_notes: $("telemetryNotes").value.trim() || null,
  };

  try {
    const resp = await fetch(`${API_BASE}/api/v1/telemetry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const txt = await resp.text();
      console.error("telemetry error", txt);
      alert("Σφάλμα αποστολής telemetry.");
      return;
    }
    $("telemetryNotes").value = "";
    $("brakeHard").checked = false;
    $("accelHard").checked = false;
    $("cornerHard").checked = false;
  } catch (err) {
    console.error("telemetry fetch error", err);
    alert("Δε μπόρεσα να μιλήσω με τον server (telemetry).");
  }
}

// Voice capture (Web Speech API, where available)
let recognition = null;
let isRecording = false;

function initSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("No SpeechRecognition API");
    $("voiceStatus").textContent = "Η συσκευή δεν υποστηρίζει φωνητική αναγνώριση.";
    return;
  }
  recognition = new SpeechRecognition();
  recognition.lang = "el-GR";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isRecording = true;
    $("voiceDot").classList.add("recording");
    $("voiceStatus").textContent = "Μίλα τώρα…";
  };

  recognition.onerror = (e) => {
    console.error("speech error", e);
    isRecording = false;
    $("voiceDot").classList.remove("recording");
    $("voiceStatus").textContent = "Σφάλμα φωνής.";
  };

  recognition.onend = () => {
    isRecording = false;
    $("voiceDot").classList.remove("recording");
    if ($("voiceStatus").textContent === "Μίλα τώρα…") {
      $("voiceStatus").textContent = "Πάτα •VOICE για νέο μήνυμα.";
    }
  };

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    $("voiceStatus").textContent = `«${transcript}»`;

    let driverId = localStorage.getItem("driver_id");
    if (!driverId) {
      driverId = await ensureDriver();
      if (!driverId) return;
    }
    const tripId = localStorage.getItem("current_trip_id");

    const payload = {
      driver_id: Number(driverId),
      trip_id: tripId ? Number(tripId) : null,
      transcript,
      intent_hint: null,
    };

    try {
      const resp = await fetch(`${API_BASE}/api/v1/voice-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        console.error("voice event error", txt);
        return;
      }
    } catch (err) {
      console.error("voice fetch error", err);
    }
  };
}

function toggleVoice() {
  if (!recognition) {
    alert("Η συσκευή/Browser δεν υποστηρίζει ακόμη φωνητικές εντολές.");
    return;
  }
  if (isRecording) {
    recognition.stop();
  } else {
    recognition.start();
  }
}

window.addEventListener("DOMContentLoaded", () => {
  loadProfile();
  initSpeech();

  $("driverName").addEventListener("change", saveProfile);
  $("driverPhone").addEventListener("change", saveProfile);
  $("taxiCompany").addEventListener("change", saveProfile);
  $("plateNumber").addEventListener("change", saveProfile);

  $("btnStartTrip").addEventListener("click", startTrip);
  $("btnFinishTrip").addEventListener("click", finishTrip);
  $("btnSendTelemetry").addEventListener("click", sendTelemetry);
  $("voiceButton").addEventListener("click", toggleVoice);
});
