const $ = (id) => document.getElementById(id);

function updateClock() {
  $("clock").textContent = new Date().toLocaleString("vi-VN");
}

setInterval(updateClock, 1000);
updateClock();

function levelClass(level) {
  const value = String(level || "NORMAL").toLowerCase();

  if (value === "high") {
    return "danger-pill high";
  }

  if (value === "medium") {
    return "danger-pill medium";
  }

  if (value === "low") {
    return "danger-pill low";
  }

  return "danger-pill";
}

async function getJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }

  return response.json();
}

async function refreshStatus() {
  try {
    const data = await getJson("/api/status");

    $("cameraStatus").textContent = data.camera_ok ? "ONLINE" : "OFFLINE";
    $("cameraStatus").className = data.camera_ok ? "safe" : "danger";

    $("arduinoStatus").textContent = data.arduino_ok ? "CONNECTED" : "SIMULATION";
    $("arduinoStatus").className = data.arduino_ok ? "safe" : "warning";

    $("dangerLevel").textContent = data.danger_level || "NORMAL";
    $("currentCommand").textContent = data.command || "STOP";
    $("chainLength").textContent = data.chain_length || 1;
    $("controlMode").textContent = data.control_mode || "AUTO";

    $("modeText").textContent = data.mode || "--";
    $("modelText").textContent = data.model || "--";

    $("blockchainStatus").textContent = data.blockchain_valid ? "VALID" : "INVALID";
    $("blockchainStatus").className = data.blockchain_valid ? "safe" : "danger";

    $("alertCount").textContent = data.alert_count || 0;
    $("messageText").textContent = data.message || "--";

    $("lastUpdate").textContent = data.last_update
      ? `Last update: ${data.last_update}`
      : "Đang chờ dữ liệu...";

    $("dangerTag").textContent = data.danger_level || "NORMAL";
    $("dangerTag").className = levelClass(data.danger_level);

    renderDetections(data.detections || []);
  } catch (error) {
    console.error("Status error:", error);
  }
}

function renderDetections(items) {
  const box = $("detectionsBox");

  if (!box) {
    return;
  }

  if (!items.length) {
    box.innerHTML = `<p class="empty-text">Chưa có detection.</p>`;
    return;
  }

  box.innerHTML = items.map((item) => `
    <div class="detection-item">
      <strong>${String(item.class_name || "").toUpperCase()} · ${item.method || ""}</strong>
      <p>Confidence: ${item.confidence ?? "-"} · Area: ${item.area ?? "-"} px</p>
      <p>Box: (${item.x1}, ${item.y1}) → (${item.x2}, ${item.y2})</p>
    </div>
  `).join("");
}

async function refreshBlockchain() {
  try {
    const chain = await getJson("/api/blockchain");
    const table = $("blockchainTable");

    if (table) {
      table.innerHTML = chain.map((block) => {
        const data = block.data || {};

        return `
          <tr>
            <td>${block.index ?? ""}</td>
            <td>${block.timestamp || ""}</td>
            <td>${data.danger_level || "GENESIS"}</td>
            <td>${data.robot_command || "-"}</td>
            <td>${data.message || data.system || "-"}</td>
            <td>
              <div class="hash" title="${block.hash || ""}">
                ${block.hash || ""}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    }

    renderMiniBlockchain(chain);
  } catch (error) {
    console.error("Blockchain error:", error);
  }
}

function renderMiniBlockchain(chain) {
  const miniLength = $("miniChainLength");
  const miniStatus = $("miniChainStatus");
  const miniBox = $("miniBlockchainBox");

  if (!miniBox) {
    return;
  }

  if (miniLength) {
    miniLength.textContent = chain.length || 0;
  }

  if (miniStatus) {
    miniStatus.textContent = chain.length > 0 ? "ACTIVE" : "EMPTY";
    miniStatus.className = chain.length > 0 ? "safe" : "warning";
  }

  if (!chain.length) {
    miniBox.innerHTML = `<p class="empty-text">Chưa có block nào.</p>`;
    return;
  }

  const latestBlocks = [...chain].reverse().slice(0, 5);

  miniBox.innerHTML = latestBlocks.map((block) => {
    const data = block.data || {};
    const danger = data.danger_level || "GENESIS";
    const command = data.robot_command || "-";
    const message = data.message || data.system || "No message";

    return `
      <div class="mini-block-item">
        <div class="mini-block-top">
          <strong>Block #${block.index ?? "-"}</strong>
          <span>${danger}</span>
        </div>

        <p><b>Time:</b> ${block.timestamp || "-"}</p>
        <p><b>Command:</b> ${command}</p>
        <p><b>Message:</b> ${message}</p>

        <span class="mini-hash" title="${block.hash || ""}">
          Hash: ${block.hash || ""}
        </span>
      </div>
    `;
  }).join("");
}

async function refreshAlerts() {
  try {
    const alerts = await getJson("/api/alerts");
    const box = $("alertsBox");

    if (!box) {
      return;
    }

    if (!alerts.length) {
      box.innerHTML = `
        <div class="alert-item">
          <strong>Chưa có cảnh báo</strong>
          <p>Khi phát hiện lửa/khói, dữ liệu sẽ được ghi vào fire_alert_history.txt.</p>
        </div>
      `;
      return;
    }

    box.innerHTML = alerts.slice(0, 20).map((alert) => `
      <div class="alert-item">
        <strong>${alert.time || "Unknown time"} · ${alert.danger_level || "N/A"}</strong>
        <p>Mode: ${alert.mode || "-"} · Command: ${alert.robot_command || "-"}</p>
        <p>${alert.message || "-"}</p>
      </div>
    `).join("");
  } catch (error) {
    console.error("Alerts error:", error);
  }
}

async function sendCommand(command) {
  try {
    await getJson("/api/command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ command })
    });

    await refreshStatus();
  } catch (error) {
    alert("Không gửi được lệnh: " + error.message);
  }
}

async function setAuto() {
  try {
    await getJson("/api/auto", {
      method: "POST"
    });

    await refreshStatus();
  } catch (error) {
    alert("Không chuyển được AUTO: " + error.message);
  }
}

async function setMode(mode) {
  try {
    await getJson("/api/mode", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ mode })
    });

    await refreshStatus();
  } catch (error) {
    alert("Không đổi được mode: " + error.message);
  }
}

async function simulateAlert() {
  try {
    await getJson("/api/simulate_alert", {
      method: "POST"
    });

    await refreshStatus();
    await refreshBlockchain();
    await refreshAlerts();
  } catch (error) {
    alert("Không giả lập được cảnh báo: " + error.message);
  }
}

async function refreshAll() {
  await refreshStatus();
  await refreshBlockchain();
  await refreshAlerts();
}

setInterval(refreshStatus, 1000);
setInterval(refreshBlockchain, 4000);
setInterval(refreshAlerts, 4000);

refreshAll();