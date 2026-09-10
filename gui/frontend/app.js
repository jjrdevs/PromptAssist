/* PromptAssist frontend — dual-mode:
 *   1. Inside Tauri: calls the Rust core (which shells out to the passist CLI).
 *   2. In a plain browser: MOCK mode with canned data, so the UI design can be
 *      reviewed and the render logic smoke-tested without a desktop runtime.
 */
(() => {
  "use strict";

  const Tauri =
    window.__TAURI_INTERNALS__ && typeof window.__TAURI_INTERNALS__.transformCallback === "function"
      ? window.__TAURI_INTERNALS__
      : null;

  const invoke = (cmd, args) => {
    if (Tauri) return Tauri.invoke(cmd, args);
    return mockInvoke(cmd, args);
  };

  /* --------------------- MOCK backend (browser only) --------------------- */
  const MOCK = {
    stages: [
      { id: "research", name: "Research" },
      { id: "plan", name: "Plan" },
      { id: "check-plan", name: "Check plan" },
      { id: "build", name: "Build" },
      { id: "continue", name: "Continue" },
      { id: "review-code", name: "Review code" },
    ],
    features: [
      { name: "add_session_logging", target_repo: "/home/jjrdev/workspace/MyRepo", created: "2026-09-10T12:34:00Z", last_fired_stage: "plan", total_fires: 7, active: true },
    ],
    hotkeys: { research: "F2", plan: "F3", "check-plan": "F4", build: "F5", continue: "F6", "review-code": "F7", next: "F8", "open-window": "F9", quit: "Ctrl+Alt+Q" },
    safe_fallbacks: { research: "Ctrl+Shift+1", plan: "Ctrl+Shift+2", "check-plan": "Ctrl+Shift+3", build: "Ctrl+Shift+4", continue: "Ctrl+Shift+5", "review-code": "Ctrl+Shift+6", next: "Ctrl+Shift+7", "open-window": "Ctrl+Shift+8", quit: null },
    prompt: (stage) =>
      `[STAGE: ${stage.toUpperCase()} — sample]\nThis is the ${stage.toUpperCase()} stage. Do not start further stages.\n\nfeature_name: add_session_logging\ntarget_repo: /home/jjrdev/workspace/MyRepo` +
      "\n\n…(browser mock — real prompts render via the passist CLI inside Tauri)…",
    auto_paste: true,
  };

  function mockInvoke(cmd, args) {
    switch (cmd) {
      case "list_stage_ids":
        return Promise.resolve(MOCK.stages);
      case "list_features":
        return Promise.resolve(MOCK.features);
      case "set_active_feature":
        return Promise.resolve(true);
      case "new_feature":
        MOCK.features.unshift({
          name: args.name, target_repo: args.targetRepo || "/tmp/repo",
          created: new Date().toISOString(), last_fired_stage: null, total_fires: 0, active: true,
        });
        return Promise.resolve(MOCK.features[0]);
      case "render_stage":
        return Promise.resolve({
          stage: args.stage, stage_name: args.stage, feature: args.feature || "add_session_logging",
          target: args.targetRepo || "", agent_name: null, text: MOCK.prompt(args.stage),
        });
      case "render_all": {
        const text = MOCK.stages.map((s) => MOCK.prompt(s.id)).join("\n\n---\n\n");
        return Promise.resolve({ feature: "add_session_logging", stages: text });
      }
      case "sync_agent":
        return Promise.resolve(["CLAUDE.md", "AGENTS.md", ".github/copilot-instructions.md", "GEMINI.md"]);
      case "read_settings":
        return Promise.resolve({ version: 1, auto_paste: MOCK.auto_paste, on_conflict: "copy", hotkeys: MOCK.hotkeys, safe_fallbacks: MOCK.safe_fallbacks });
      case "list_bindings":
        return Promise.resolve({
          bindings: Object.entries({ ...MOCK.hotkeys }).map(([stage, effective]) => ({
            stage, effective: effective || "—", default: MOCK.hotkeys[stage] || "—", safe_fallback: MOCK.safe_fallbacks[stage] || "—",
          })),
          conflicts: [],
        });
      case "bind":
        if (args.combo) MOCK.hotkeys[args.stage] = args.combo;
        else delete MOCK.hotkeys[args.stage];
        return Promise.resolve();
      case "apply-safe-fallbacks":
        Object.assign(MOCK.hotkeys, MOCK.safe_fallbacks);
        return Promise.resolve();
      case "reset_settings":
        Object.assign(MOCK.hotkeys, { research: "F2", plan: "F3", "check-plan": "F4", build: "F5", continue: "F6", "review-code": "F7", next: "F8", "open-window": "F9", quit: "Ctrl+Alt+Q" });
        return Promise.resolve();
      case "set-auto-paste":
        MOCK.auto_paste = !!args.on;
        return Promise.resolve();
      case "version":
        return Promise.resolve("0.1.0 (mock)");
      case "quit":
        return Promise.resolve();
      default:
        return Promise.reject(new Error("mock: unknown command " + cmd));
    }
  }

  /* ----------------------------- helpers -------------------------------- */
  const $ = (s) => document.querySelector(s);
  const status = (msg, detail) => {
    $("#status").textContent = msg;
    $("#status-detail").textContent = detail || "";
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const isTauri = !!Tauri;

  if (!isTauri) document.body.setAttribute("data-mode", "mock");

  /* ----------------------------- state ---------------------------------- */
  let state = {
    stages: [],
    features: [],
    activeFeature: null,
    lastRender: null,
    bindings: [],
    safe_fallbacks: {},
  };

  /* --------------------------- tab switching ----------------------------- */
  document.querySelectorAll(".tab").forEach((t) => {
    t.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      $("#tab-" + t.dataset.tab).classList.add("active");
    });
  });

  /* --------------------------- stages tab -------------------------------- */
  function renderStageCards() {
    const grid = $("#stages-grid");
    grid.innerHTML = "";
    state.stages.forEach((s, i) => {
      const hk = (state.bindings.find((b) => b.stage === s.id) || {}).effective
        || (state.safe_fallbacks[s.id] && "default " + state.safe_fallbacks[s.id])
        || "tray only";
      const card = document.createElement("div");
      card.className = "stage-card";
      card.dataset.stage = s.id;
      card.setAttribute("role", "button");
      card.tabIndex = 0;
      card.innerHTML =
        `<div class="idx">Stage ${i + 1} / 6</div>
         <div class="name">${esc(s.name)}</div>
         <div class="hk">${esc(s.id)} · ${esc(hk)}</div>
         <div class="desc">Click to render${isTauri ? " & paste" : ""}</div>`;
      card.addEventListener("click", () => fireStage(s.id));
      card.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fireStage(s.id); }});
      grid.appendChild(card);
    });
  }

  async function fireStage(stage) {
    status("rendering", stage + " …");
    document.querySelectorAll(".stage-card").forEach((c) => c.classList.toggle("active", c.dataset.stage === stage));
    try {
      const r = await invoke("render_stage", {
        stage,
        feature: state.activeFeature ? state.activeFeature : "-",
        targetRepo: state.activeFeature ? (state.features.find((f) => f.name === state.activeFeature) || {}).target_repo : "",
      });
      showRendered(r);
      if (isTauri) {
        copyToClipboard(r.text);
        status("done", `stage=${stage} · copied to clipboard`);
      } else {
        status("done (mock)", `stage=${stage} · ${r.text.length} chars`);
      }
    } catch (e) {
      status("error", String(e.message || e));
    }
  }

  function showRendered(r) {
    state.lastRender = r;
    const p = $("#preview");
    p.innerHTML = "";
    // colour the stage header lines
    const lines = (r.text || "").split("\n");
    lines.forEach((ln, i) => {
      const div = document.createElement("span");
      if (i === 0 || /\[STAGE/i.test(ln)) div.className = "phase";
      else if (/STOP|do not start further/i.test(ln)) div.className = "stop";
      else div.className = "body";
      div.textContent = ln;
      p.appendChild(div);
      if (i < lines.length - 1) p.appendChild(document.createTextNode("\n"));
    });
    $("#stage-preview-meta").textContent = r.feature ? `${r.feature} · ${r.stage_name}` : "";
  }

  function copyToClipboard(text) {
    const done = () => {};
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text));
    } else fallbackCopy(text);
  }
  function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch {}
    document.body.removeChild(ta);
  }

  $("#copy-btn").addEventListener("click", () => { if (state.lastRender) { copyToClipboard(state.lastRender.text); status("copied", String(state.lastRender.text.length) + " chars"); }});

  const apToggle = $("#auto-paste-toggle");
  async function refreshAutoPasteBtn(v) {
    apToggle.classList.toggle("on", !!v);
    apToggle.textContent = v ? "Auto-paste: ON" : "Auto-paste: OFF";
  }
  apToggle.addEventListener("click", async () => {
    const on = !apToggle.classList.contains("on");
    await invoke("set-auto-paste", { on });
    await refreshAutoPasteBtn(on);
  });

  $("#new-feature-btn").addEventListener("click", openNewFeature);
  $("#new-feature-btn-2").addEventListener("click", openNewFeature);

  /* --------------------------- features tab ------------------------------ */
  async function refreshFeatures() {
    const feats = await invoke("list_features", {});
    state.features = feats;
    const sel = $("#active-feature");
    sel.innerHTML = "";
    feats.forEach((f) => {
      const o = document.createElement("option");
      o.value = f.name; o.textContent = f.name;
      sel.appendChild(o);
    });
    if (state.activeFeature && feats.find((f) => f.name === state.activeFeature)) sel.value = state.activeFeature;
    else if (feats[0]) { sel.value = feats[0].name; state.activeFeature = feats[0].name; }

    const rows = $("#feat-rows");
    rows.innerHTML = "";
    feats.forEach((f) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td><span class="tag ${f.active ? "active" : ""}">${esc(f.name)}</span></td>
         <td class="muted">${esc(f.target_repo)}</td>
         <td class="muted">${esc(f.created)}</td>
         <td>${f.last_fired_stage ? esc(f.last_fired_stage) : "—"}</td>
         <td>${f.total_fires}</td>
         <td><button class="btn small ghost" data-act="activate" data-name="${esc(f.name)}" ${f.active ? "disabled" : ""}>Set active</button></td>`;
      tr.querySelector("button[data-act=activate]").addEventListener("click", async () => {
        await invoke("set_active_feature", { name: f.name });
        state.activeFeature = f.name;
        sel.value = f.name;
        await refreshFeatures();
        status("active", f.name);
      });
      rows.appendChild(tr);
    });
  }

  /* --------------------------- settings tab ------------------------------ */
  async function refreshBindings() {
    const r = await invoke("list_bindings", {});
    state.bindings = r.bindings || [];
    const conflicts = r.conflicts || [];
    const warn = $("#hk-conflict");
    if (conflicts.length) { warn.hidden = false; warn.textContent = "Conflicts: " + conflicts.join(", "); }
    else warn.hidden = true;

    const tbody = $("#hk-table").querySelector("tbody");
    tbody.innerHTML = "";
    state.bindings.forEach((b) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${esc(b.stage)}</td>
         <td><input class="combo" data-stage="${esc(b.stage)}" value="${esc(b.effective || "")}" placeholder="(disabled)" /></td>
         <td class="muted">${esc(b.safe_fallback || "—")}</td>
         <td><button class="btn small ghost hk-reset" data-stage="${esc(b.stage)}">→ fallback</button></td>`;
      tr.querySelector(".hk-reset").addEventListener("click", async () => {
        const fallback = (b.safe_fallback || null);
        await invoke("bind", { stage: b.stage, combo: fallback });
        await refreshBindings();
        renderStageCards();
        status("done", `${b.stage} → ${fallback || "disabled"}`);
      });
      tbody.appendChild(tr);
    });
  }

  $("#apply-safe").addEventListener("click", async () => {
    await invoke("apply_safe_fallbacks", {});
    await refreshBindings(); renderStageCards(); status("done", "safe fallbacks applied");
  });
  $("#reset-bindings").addEventListener("click", async () => {
    await invoke("reset_settings", {});
    await refreshBindings(); renderStageCards(); status("done", "reset to defaults");
  });
  $("#save-bindings").addEventListener("click", async () => {
    const inputs = document.querySelectorAll("#hk-table input.combo");
    for (const inp of inputs) {
      const stage = inp.dataset.stage;
      if (inp.value.trim() === (state.bindings.find((b) => b.stage === stage)?.effective || "")) continue;
      await invoke("bind", { stage, combo: inp.value.trim() || null });
    }
    await refreshBindings();
    renderStageCards();
    status("done", "bindings saved");
  });

  $("#sync-agent").addEventListener("click", async () => {
    status("syncing", "agent files …");
    try {
      const written = await invoke("sync_agent", { targetRepo: (state.features.find((f) => f.name === state.activeFeature) || {}).target_repo });
      status("done", `wrote: ${written.join(", ")}`);
    } catch (e) { status("error", String(e.message || e)); }
  });

  $("#export-md").addEventListener("click", async () => {
    status("exporting", "all 6 stages …");
    const r = await invoke("render_all", {});
    copyToClipboard(r.text);
    status("done", "exported to clipboard");
  });

  const ap = $("#auto-paste");
  ap.addEventListener("change", async () => {
    await invoke("set-auto-paste", { on: ap.checked });
    await refreshAutoPasteBtn(ap.checked);
  });

  /* ------------------------------- modal --------------------------------- */
  const modal = $("#modal");
  function openNewFeature() { modal.hidden = false; $("#nf-name").focus(); }
  $("#nf-cancel").addEventListener("click", () => { modal.hidden = true; });
  $("#nf-ok").addEventListener("click", async () => {
    const name = $("#nf-name").value.trim();
    const repo = $("#nf-repo").value.trim();
    if (!name || !repo) { status("error", "name and target repo required"); return; }
    try {
      await invoke("new_feature", { name, targetRepo: repo });
      status("done", "feature created: " + name);
    } catch (e) { status("error", String(e.message || e)); }
    modal.hidden = true;
    $("#nf-name").value = ""; $("#nf-repo").value = "";
    await refreshFeatures();
  });

  $("#quit-btn").addEventListener("click", async () => { await invoke("quit", {}); });

  /* ------------------------------ boot ----------------------------------- */
  (async function boot() {
    state.stages = await invoke("list_stage_ids", {});
    const settings = await invoke("read_settings", {});
    if (settings && settings.auto_paste !== undefined) {
      ap.checked = settings.auto_paste;
      await refreshAutoPasteBtn(settings.auto_paste);
    }
    state.safe_fallbacks = settings?.safe_fallbacks || {};
    await refreshBindings();
    renderStageCards();
    await refreshFeatures();
    $("#data-dir").textContent = isTauri
      ? `Tauri · ${await invoke("version", {})}`
      : "mock mode (browser)";
  })().catch((e) => status("boot error", String(e.message || e)));
})();