const state = {
  token: localStorage.getItem("panel_token") || "",
  account: null,
  chart: null,
  bandwidthChart: null,
  cpuSeries: [],
  ramSeries: [],
  labels: [],
};

const el = (id) => document.getElementById(id);

const api = async (url, method = "GET", body = null) => {
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: state.token ? `Bearer ${state.token}` : "",
    },
    body: body ? JSON.stringify(body) : null,
  });
  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { ok: false, error: raw || `HTTP ${response.status}` };
  }
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
};

const taskModal = {
  root: () => el("taskModal"),
  title: () => el("taskTitle"),
  output: () => el("taskOutput"),
};

const openTaskModal = (title) => {
  taskModal.title().textContent = title;
  taskModal.output().textContent = "Iniciando tarea...";
  taskModal.root().classList.remove("hidden");
  taskModal.root().classList.add("flex");
};

const closeTaskModal = () => {
  taskModal.root().classList.add("hidden");
  taskModal.root().classList.remove("flex");
};

const stringifyTaskData = (value, depth = 0) => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (depth > 3) return "";
  if (typeof value !== "object") return String(value);
  const lines = [];
  for (const [key, val] of Object.entries(value)) {
    if (["stdout", "stderr", "error", "message", "status"].includes(key) && typeof val === "string" && val.trim()) {
      lines.push(`${key}: ${val}`);
    } else if (typeof val === "object" && val !== null) {
      const nested = stringifyTaskData(val, depth + 1);
      if (nested) lines.push(`${key}:\n${nested}`);
    }
  }
  return lines.join("\n").trim();
};

const runTaskAction = async (title, fn) => {
  openTaskModal(title);
  const startedAt = new Date();
  try {
    taskModal.output().textContent = "Ejecutando...";
    const result = await fn();
    const body = stringifyTaskData(result);
    const duration = ((Date.now() - startedAt.getTime()) / 1000).toFixed(1);
    taskModal.output().textContent = [
      "Estado: abierto con exito",
      `Duracion: ${duration}s`,
      body || "Sin salida adicional",
    ].join("\n\n");
    setTimeout(() => {
      refreshActionStatus().catch(() => {});
    }, 200);
    setTimeout(closeTaskModal, 1800);
    return result;
  } catch (error) {
    taskModal.output().textContent = [
      "Estado: error",
      String(error.message || error),
      "Revisa logs si el problema persiste: journalctl -u mi-panel -n 120 --no-pager",
    ].join("\n\n");
    throw error;
  }
};

const showCopyBlock = (text) => {
  el("copyBlock").value = text || "";
};

const showExports = (exportsBundle) => {
  if (!exportsBundle) return;
  el("vlessLink").value = exportsBundle.vless?.link || "";
  el("trojanLink").value = exportsBundle.trojan?.link || "";
  el("ssLink").value = exportsBundle.shadowsocks?.link || "";
  const qr = exportsBundle.vless?.qr || "";
  if (qr) {
    el("qrImage").src = qr;
    el("qrImage").classList.remove("hidden");
  }
};

const showSubscription = (subscription) => {
  el("subLink").value = subscription?.url || "";
};

const updateHeader = () => {
  if (!state.account) {
    el("whoami").textContent = "Sin sesion";
    el("creditsValue").textContent = "-";
    el("profileUser").value = "";
    return;
  }
  el("whoami").textContent = `${state.account.username} (${state.account.role})`;
  el("creditsValue").textContent = state.account.role === "reseller" ? state.account.credits : "n/a";
  el("profileUser").value = state.account.username;
  const adminOnly = state.account.role === "admin";
  el("adminActions").style.display = adminOnly ? "block" : "none";
  el("adminAccountBlock").style.display = adminOnly ? "block" : "none";
};

const initChart = () => {
  const ctx = el("metricsChart").getContext("2d");
  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: state.labels,
      datasets: [
        { label: "CPU %", data: state.cpuSeries, borderColor: "#38bdf8", tension: 0.25 },
        { label: "RAM %", data: state.ramSeries, borderColor: "#4ade80", tension: 0.25 },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { min: 0, max: 100 } },
      plugins: { legend: { labels: { color: "#e2e8f0" } } },
    },
  });
};

const initBandwidthChart = () => {
  const ctx = el("bandwidthChart").getContext("2d");
  state.bandwidthChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        { label: "Consumo ventana (MB)", data: [], backgroundColor: "rgba(56, 189, 248, 0.6)" },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#e2e8f0" } } },
      scales: {
        y: { beginAtZero: true, ticks: { color: "#cbd5e1" } },
        x: { ticks: { color: "#cbd5e1" } },
      },
    },
  });
};

const refreshBandwidth = async () => {
  if (document.hidden) return;
  try {
    const hours = Number(el("bandwidthRange").value || 24);
    if (state.account?.role === "admin") {
      await api("/api/system/bandwidth/collect", "POST");
    }
    const data = await api(`/api/system/bandwidth/users?hours=${hours}`);
    const top = (data.users || []).slice(0, 8);
    state.bandwidthChart.data.labels = top.map((item) => item.user);
    state.bandwidthChart.data.datasets[0].data = top.map((item) => Number((item.window_bytes / 1024 / 1024).toFixed(2)));
    state.bandwidthChart.data.datasets[0].label = `Consumo ventana ${hours}h (MB)`;
    state.bandwidthChart.update();
  } catch {
    // no-op until logged in and xray stats enabled
  }
};

const pushMetricPoint = (cpu, ramPct) => {
  const now = new Date().toLocaleTimeString();
  state.labels.push(now);
  state.cpuSeries.push(cpu);
  state.ramSeries.push(ramPct);
  if (state.labels.length > 24) {
    state.labels.shift();
    state.cpuSeries.shift();
    state.ramSeries.shift();
  }
  state.chart.update();
};

const renderXray = (users) => {
  const body = el("xrayTable");
  body.innerHTML = "";
  users.forEach((u) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${u.id}</td><td>${u.name}</td><td>${u.expires_at}</td><td>${u.status}</td>`;
    body.appendChild(tr);
  });
};

const actionBtn = (text, action) => {
  const b = document.createElement("button");
  b.className = "btn-secondary";
  b.textContent = text;
  b.onclick = action;
  return b;
};

const renderSsh = (users) => {
  const body = el("sshTable");
  body.innerHTML = "";
  users.forEach((u) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${u.id}</td><td>${u.username}</td><td>${u.expires_at}</td><td>${u.status}</td><td></td>`;
    const actions = tr.querySelector("td:last-child");
    actions.appendChild(
      actionBtn("Pausar", async () => {
        try {
          await api(`/api/access/ssh-users/${u.id}/pause`, "POST");
          await refreshTables();
        } catch (e) {
          alert(e.message);
        }
      })
    );
    actions.appendChild(
      actionBtn("Eliminar", async () => {
        if (!confirm(`Eliminar ${u.username}?`)) return;
        try {
          await api(`/api/access/ssh-users/${u.id}`, "DELETE");
          await refreshTables();
        } catch (e) {
          alert(e.message);
        }
      })
    );
    body.appendChild(tr);
  });
};

const refreshTables = async () => {
  const [xray, ssh] = await Promise.all([api("/api/access/xray-users"), api("/api/access/ssh-users")]);
  renderXray(xray.users || []);
  renderSsh(ssh.users || []);
  const me = await api("/api/auth/me");
  state.account = me.account;
  updateHeader();
};

const refreshMetrics = async () => {
  if (document.hidden) return;
  try {
    const data = await api("/api/system/metrics");
    el("cpuValue").textContent = `${data.cpu_pct}%`;
    el("ramValue").textContent = `${data.memory.used_mb} MB`;
    pushMetricPoint(data.cpu_pct, data.memory.usage_pct);
  } catch {
    // no-op when unauthenticated
  }
};

const refreshActionStatus = async () => {
  try {
    const data = await api("/api/system/actions/status");
    const services = data.services || {};
    const ports = data.ports || {};
    const wsPorts = (ports.ws || [])
      .map((item) => `${item.port}:${item.open ? "abierto" : "cerrado"}`)
      .join(", ");
    const text = [
      "Estado de acciones:",
      `- xray: ${services.xray ? "activo" : "inactivo"}`,
      `- dropbear: ${services.dropbear ? "activo" : "inactivo"}`,
      `- stunnel4: ${services.stunnel4 ? "activo" : "inactivo"}`,
      `- ws_tunnel: ${services.ws_tunnel ? "activo" : "inactivo"}`,
      `- badvpn: ${services.badvpn ? "activo" : "inactivo"}`,
      `- https 443: ${ports.https ? "abierto" : "cerrado"}`,
      `- stunnel: ${ports.stunnel ? "abierto" : "cerrado"}`,
      `- badvpn 7300/udp: ${ports.badvpn ? "abierto" : "cerrado"}`,
      `- ws: ${wsPorts || "sin puertos"}`,
    ].join("\n");
    el("sysInfoText").textContent = text;
  } catch {
    // no-op
  }
};

el("loginBtn").addEventListener("click", async () => {
  try {
    const username = el("username").value.trim();
    const password = el("password").value;
    const data = await api("/api/auth/login", "POST", { username, password });
    state.token = data.token;
    state.account = data.account;
    localStorage.setItem("panel_token", state.token);
    updateHeader();
    if (data.must_change_password) {
      alert("Por seguridad, cambia tus credenciales en la seccion Mi Perfil antes de continuar.");
      return;
    }
    await refreshTables();
    await refreshBandwidth();
  } catch (e) {
    alert(e.message);
  }
});

el("taskCloseBtn").addEventListener("click", closeTaskModal);
el("taskModal").addEventListener("click", (event) => {
  if (event.target && event.target.id === "taskModal") closeTaskModal();
});

el("refreshMetricsBtn").addEventListener("click", refreshMetrics);
el("refreshBandwidthBtn").addEventListener("click", refreshBandwidth);
el("bandwidthRange").addEventListener("change", refreshBandwidth);

el("xrayCreateBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/access/xray-users", "POST", {
      name: el("xrayName").value.trim(),
      secret: el("xraySecret").value.trim() || null,
      expires_at: new Date(el("xrayExpires").value).toISOString(),
    });
    showCopyBlock(data.copy_block);
    showExports(data.exports);
    showSubscription(data.subscription);
    await refreshTables();
  } catch (e) {
    alert(e.message);
  }
});

el("xrayDemoBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/access/xray-users/demo", "POST");
    showCopyBlock(data.copy_block);
    showExports(data.exports);
    showSubscription(data.subscription);
    await refreshTables();
  } catch (e) {
    alert(e.message);
  }
});

el("sshCreateBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/access/ssh-users", "POST", {
      username: el("sshUser").value.trim(),
      password: el("sshPass").value,
      expires_at: new Date(el("sshExpires").value).toISOString(),
      max_sessions: Number(el("sshMaxSessions").value || 2),
    });
    showCopyBlock(data.copy_block);
    await refreshTables();
  } catch (e) {
    alert(e.message);
  }
});

el("sshDemoBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/access/ssh-users/demo", "POST");
    showCopyBlock(data.copy_block);
    await refreshTables();
  } catch (e) {
    alert(e.message);
  }
});

el("copyBtn").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(el("copyBlock").value);
  } catch {
    alert("No se pudo copiar");
  }
});

el("bbrBtn").addEventListener("click", async () => {
  await runTaskAction("Activando TCP BBR", () => api("/api/system/tuning/bbr", "POST")).catch(() => {});
});

el("cleanBtn").addEventListener("click", async () => {
  await runTaskAction("Limpiando RAM y logs", () => api("/api/system/cleanup", "POST")).catch(() => {});
});

el("memBoostBtn").addEventListener("click", async () => {
  await runTaskAction("Aplicando Zram/Swap", () => api("/api/system/memory/boost", "POST")).catch(() => {});
});

el("badvpnBtn").addEventListener("click", async () => {
  await runTaskAction("Instalando BadVPN", () => api("/api/system/badvpn/install", "POST")).catch(() => {});
});

el("wstBtn").addEventListener("click", async () => {
  await runTaskAction("Instalando WebSocket tunnel", () => api("/api/system/ws-tunnel/install", "POST")).catch(() => {});
});

el("dropbearBtn").addEventListener("click", async () => {
  await runTaskAction("Activando Dropbear", () => api("/api/system/dropbear/install", "POST")).catch(() => {});
});

el("stunnelBtn").addEventListener("click", async () => {
  await runTaskAction("Activando SSL directo (Stunnel)", () => api("/api/system/stunnel/install", "POST")).catch(() => {});
});

el("backupBtn").addEventListener("click", async () => {
  await runTaskAction("Generando backup SQLite", () => api("/api/system/backup/run", "POST")).catch(() => {});
});

el("autoupdateBtn").addEventListener("click", async () => {
  await runTaskAction("Ejecutando actualizacion", () => api("/api/system/autoupdate/run", "POST")).catch(() => {});
});

el("applyProfileBtn").addEventListener("click", async () => {
  const mode = el("profileMode").value;
  const domain = el("profileDomain").value.trim() || undefined;
  const panel_port = Number(el("profilePanelPort").value || 0) || undefined;
  const titleByMode = {
    ssl: "Activando SSL directo",
    "ssl-payload": "Activando SSL + Payload",
    v2ray: "Activando V2Ray/Xray",
  };
  await runTaskAction(titleByMode[mode] || "Aplicando perfil", () =>
    api("/api/system/profile/apply", "POST", { mode, domain, panel_port })
  ).catch(() => {});
});

el("fwOpenBtn").addEventListener("click", async () => {
  const port = Number(el("fwPort").value);
  const protocol = el("fwProtocol").value;
  await runTaskAction(`Abriendo puerto ${port}/${protocol}`, () => api("/api/system/firewall/open", "POST", { port, protocol })).catch(() => {});
});

el("fwCloseBtn").addEventListener("click", async () => {
  const port = Number(el("fwPort").value);
  const protocol = el("fwProtocol").value;
  await runTaskAction(`Cerrando puerto ${port}/${protocol}`, () => api("/api/system/firewall/close", "POST", { port, protocol })).catch(() => {});
});

el("fwStatusBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/system/firewall/status");
    el("sysInfoText").textContent = data.stdout || data.stderr || "Sin datos";
  } catch (e) {
    alert(e.message);
  }
});

el("expireBtn").addEventListener("click", async () => {
  const result = await runTaskAction("Procesando expiraciones", () => api("/api/system/expire/run", "POST")).catch(() => null);
  if (result) {
    await refreshTables();
    await refreshActionStatus();
  }
});

el("newAccBtn").addEventListener("click", async () => {
  try {
    await api("/api/auth/accounts", "POST", {
      username: el("newAccUser").value.trim(),
      password: el("newAccPass").value,
      role: el("newAccRole").value,
      credits: Number(el("newAccCredits").value || 0),
    });
    alert("Cuenta creada");
  } catch (e) {
    alert(e.message);
  }
});

el("profileSaveBtn").addEventListener("click", async () => {
  try {
    const payload = {
      current_password: el("profileCurrentPass").value,
      new_username: el("profileUser").value.trim(),
      new_password: el("profileNewPass").value,
    };
    const data = await api("/api/auth/profile", "PUT", payload);
    state.account = data.account;
    updateHeader();
    el("profileCurrentPass").value = "";
    el("profileNewPass").value = "";
    await refreshTables();
    await refreshBandwidth();
    alert("Perfil actualizado");
  } catch (e) {
    alert(e.message);
  }
});

el("sysInfoBtn").addEventListener("click", async () => {
  try {
    const info = await api("/api/system/info");
    el("sysInfoText").textContent = [
      `Kernel: ${info.kernel}`,
      `Uptime: ${info.uptime}`,
      `RAM: ${info.memory.used_mb}MB / ${info.memory.total_mb}MB`,
      "Disk:",
      info.disk_root,
    ].join("\n");
  } catch (e) {
    alert(e.message);
  }
  await refreshActionStatus();
});

initChart();
initBandwidthChart();
updateHeader();
setInterval(refreshMetrics, 3000);
setInterval(refreshBandwidth, 60000);
setInterval(refreshActionStatus, 10000);

if (state.token) {
  Promise.all([refreshTables(), refreshBandwidth(), refreshActionStatus()]).catch(() => {
    state.token = "";
    localStorage.removeItem("panel_token");
  });
}
