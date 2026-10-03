// Interface TODOist : appelle l'API REST du même serveur (chemins relatifs /api/...).
// Tout texte venant de l'utilisateur est inséré via textContent (jamais innerHTML) -> pas de XSS.
const state = { view: "inbox", projectId: null, projects: [] };
// Formulaire d'ajout : champs modifiés à la main (l'analyse de la phrase ne les écrase plus)
const quick = { touched: {}, preview: null, timer: null };
const $ = (sel) => document.querySelector(sel);
const PRIORITES = { 1: "Urgente", 2: "Haute", 3: "Moyenne", 4: "Normale" };
const TITRES = { inbox: "Boîte de réception", today: "Aujourd'hui", upcoming: "À venir", all: "Toutes les tâches", done: "Terminées" };

async function api(method, url, body) {
  const res = await fetch(url, {
    method, headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = typeof err.detail === "string" ? err.detail : `Erreur ${res.status}`;
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function showError(msg) { const e = $("#error"); e.textContent = msg; e.hidden = !msg; }

function el(tag, props = {}, ...children) {
  const n = document.createElement(tag);
  Object.assign(n, props);
  children.forEach((c) => n.append(c));
  return n;
}

function formatDue(iso) {
  const d = new Date(iso + "T00:00:00");
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff = Math.round((d - today) / 86400000);
  if (diff === 0) return "Aujourd'hui";
  if (diff === 1) return "Demain";
  if (diff === -1) return "Hier";
  return d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
}

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const inboxId = () => state.projects.find((p) => p.name === "Boîte de réception")?.id;

// Remplit une liste déroulante avec les projets (+ éventuellement un projet à créer)
function fillProjects(select, selectedId, newName) {
  const opts = state.projects.map((p) => el("option", { value: p.id, textContent: p.name }));
  if (newName) opts.push(el("option", { value: "new", textContent: `${newName} (nouveau projet)` }));
  select.replaceChildren(...opts);
  select.value = newName ? "new" : String(selectedId ?? inboxId());
}

async function loadProjects() {
  state.projects = await api("GET", "/api/projects");
  const ul = $("#projects");
  ul.replaceChildren(...state.projects.map((p) => {
    const li = el("li", { className: state.projectId === p.id ? "active" : "" },
      el("span", { className: "dot", style: `background:${p.color}` }),
      el("span", { className: "name", textContent: p.name }),
      el("span", { className: "count", textContent: p.open_tasks || "" }));
    li.onclick = () => { state.projectId = p.id; state.view = "all"; resetQuickForm(); refresh(); };
    if (p.name !== "Boîte de réception") {
      const del = el("button", { className: "del", textContent: "×", title: "Supprimer le projet" });
      del.onclick = async (ev) => {
        ev.stopPropagation();
        if (!confirm(`Supprimer le projet « ${p.name} » et ses tâches ?`)) return;
        await api("DELETE", `/api/projects/${p.id}`);
        if (state.projectId === p.id) state.projectId = null;
        refresh();
      };
      li.append(del);
    }
    return li;
  }));
}

async function loadTasks() {
  const params = new URLSearchParams({ view: state.view });
  if (state.projectId) params.set("project_id", state.projectId);
  const tasks = await api("GET", `/api/tasks?${params}`);
  const project = state.projects.find((p) => p.id === state.projectId);
  $("#view-title").textContent = project ? project.name : TITRES[state.view];
  $("#view-count").textContent = `${tasks.length} tâche${tasks.length > 1 ? "s" : ""}`;
  $("#empty").hidden = tasks.length > 0;
  $("#tasks").replaceChildren(...tasks.map(renderTask));
}

function renderTask(t) {
  const check = el("button", { className: `check p${t.priority}`, title: t.done ? "Rouvrir" : "Terminer" });
  check.onclick = async () => { await api("PATCH", `/api/tasks/${t.id}`, { done: !t.done }); refresh(); };
  const meta = el("div", { className: "meta" });
  if (t.due_date) meta.append(el("span", { className: `due${t.overdue ? " late" : ""}`, textContent: formatDue(t.due_date) }));
  const color = state.projects.find((p) => p.id === t.project_id)?.color || "#94a3b8";
  meta.append(el("span", {}, el("span", { className: "proj-dot", style: `background:${color}` }), t.project_name));
  if (t.priority < 4) meta.append(el("span", { className: `prio p${t.priority}`, textContent: "P" + t.priority }));
  const del = el("button", { className: "del", textContent: "×", title: "Supprimer" });
  del.onclick = async () => { await api("DELETE", `/api/tasks/${t.id}`); refresh(); };
  const title = el("button", { className: "title", textContent: t.title, title: "Modifier la tâche" });
  const li = el("li", { className: `task${t.done ? " done" : ""}` },
    check, el("div", { className: "body" }, title, meta), del);
  title.onclick = () => li.replaceWith(renderEditor(t));
  return li;
}

// Édition d'une tâche : titre, projet, priorité, échéance -> PATCH /api/tasks/{id}
function renderEditor(t) {
  const title = el("input", { value: t.title, maxLength: 200, required: true });
  const project = el("select");
  fillProjects(project, t.project_id);
  const priority = el("select", {}, ...[1, 2, 3, 4].map((n) =>
    el("option", { value: n, textContent: `P${n} · ${PRIORITES[n]}`, selected: n === t.priority })));
  const due = el("input", { type: "date", value: t.due_date || "" });
  const cancel = el("button", { type: "button", className: "ghost", textContent: "Annuler" });
  cancel.onclick = refresh;
  const form = el("form", { className: "editor" }, title,
    el("div", { className: "fields" },
      el("label", {}, "Projet ", project), el("label", {}, "Priorité ", priority), el("label", {}, "Échéance ", due),
      el("span", { className: "spacer" }), cancel, el("button", { type: "submit", textContent: "Enregistrer" })));
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      await api("PATCH", `/api/tasks/${t.id}`, { title: title.value, project_id: Number(project.value),
        priority: Number(priority.value), due_date: due.value || null });
      refresh();
    } catch (e) { showError(e.message); }
  };
  const li = el("li", { className: "task editing" }, form);
  setTimeout(() => title.focus());
  return li;
}

async function loadStatus() {
  try {
    const h = await api("GET", "/api/health");
    $("#status").textContent = `Service opérationnel · ${h.tasks} tâche(s) en base`;
    $("#status").classList.remove("down");
  } catch {
    $("#status").textContent = "API injoignable";
    $("#status").classList.add("down");
  }
}

async function refresh() {
  try {
    showError("");
    document.querySelectorAll("#views button").forEach((b) =>
      b.classList.toggle("active", !state.projectId && b.dataset.view === state.view));
    await loadProjects();
    if (!quick.touched.project) fillProjects($("#quick-project"), state.projectId, quick.preview?.newProject);
    await loadTasks();
    loadStatus();
  } catch (e) { showError(e.message); }
}

document.querySelectorAll("#views button").forEach((b) => {
  b.onclick = () => { state.view = b.dataset.view; state.projectId = null; resetQuickForm(); refresh(); };
});

$("#today").textContent = new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

// ------------------------------------------------------------ formulaire d'ajout
const HINT = $("#quick-preview").innerHTML;  // texte d'aide statique écrit dans index.html

const defaultDue = () => (state.view === "today" && !state.projectId ? todayIso() : "");

// Valeurs par défaut selon la vue : projet affiché, échéance du jour dans « Aujourd'hui »
function resetQuickForm() {
  quick.touched = {}; quick.preview = null;
  $("#quick-text").value = "";
  $("#quick-priority").value = "4";
  $("#quick-due").value = defaultDue();
  $("#quick-preview").innerHTML = HINT;
  fillProjects($("#quick-project"), state.projectId);
}

// Pendant la saisie : le serveur analyse la phrase (/api/tasks/parse) et on remplit les champs
async function previewQuick() {
  const text = $("#quick-text").value.trim();
  const box = $("#quick-preview");
  if (!text) { quick.preview = null; box.innerHTML = HINT; return; }
  let r;
  try { r = await api("POST", "/api/tasks/parse", { text }); }
  catch (e) {
    quick.preview = null;
    box.replaceChildren(el("span", { className: "warn", textContent: e.message }));
    return;
  }
  const existing = r.project && state.projects.find((p) => p.name.toLowerCase() === r.project.toLowerCase());
  quick.preview = { title: r.title, newProject: r.project && !existing ? r.project : null };
  // Un champ modifié à la main garde sa valeur ; sinon il suit la phrase (ou revient au défaut)
  if (!quick.touched.project) fillProjects($("#quick-project"), existing?.id ?? state.projectId, quick.preview.newProject);
  if (!quick.touched.priority) $("#quick-priority").value = r.priority;
  if (!quick.touched.due) $("#quick-due").value = r.due_date || defaultDue();
  box.replaceChildren("Sera ajoutée : ", el("strong", { textContent: r.title }));
}

$("#quick-text").oninput = () => { clearTimeout(quick.timer); quick.timer = setTimeout(previewQuick, 250); };
[["project", "#quick-project"], ["priority", "#quick-priority"], ["due", "#quick-due"]].forEach(([k, sel]) => {
  $(sel).onchange = () => { quick.touched[k] = true; };
});

$("#quick-form").onsubmit = async (ev) => {
  ev.preventDefault();
  try {
    clearTimeout(quick.timer);
    await previewQuick();  // analyse à jour du texte final
    if (!quick.preview) return;
    let pid = $("#quick-project").value;
    if (pid === "new") {   // #Projet inconnu : on le crée d'abord
      pid = (await api("POST", "/api/projects", { name: quick.preview.newProject, color: "#64748b" })).id;
    }
    await api("POST", "/api/tasks", { title: quick.preview.title, project_id: Number(pid),
      priority: Number($("#quick-priority").value), due_date: $("#quick-due").value || null });
    resetQuickForm();
    refresh();
  } catch (e) { showError(e.message); }
};

$("#project-form").onsubmit = async (ev) => {
  ev.preventDefault();
  try {
    await api("POST", "/api/projects", { name: $("#project-name").value, color: $("#project-color").value });
    $("#project-name").value = "";
    refresh();
  } catch (e) { showError(e.message); }
};

refresh().then(resetQuickForm);
