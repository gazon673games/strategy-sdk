import "./style.css";
import "./python.css";
import { BlocksEditor } from "./blocks.js";
import { GraphEditor } from "./graph.js";
import { checkModel, friendlyError, newModel } from "./model.js";
import { PropertiesPanel } from "./properties.js";
import { PythonEditor } from "./python_editor.js";

const $ = id => document.getElementById(id);
const DRAFT = "strategy-sdk.visual.v1";
const status = $("status");
const outputButtons = ["save", "download", "publish"].map($);
let templates, token, model, result;
let mode = "blocks";
let revision = 0;
let timer;
let publication;
const python = new PythonEditor(post);
for (const kind of ["visual", "python"]) $(`${kind}-mode`).onclick = () => {
  for (const option of ["visual", "python"]) {
    $(`${option}-workbench`).hidden = option !== kind;
    $(`${option}-mode`).setAttribute("aria-pressed", String(option === kind));
  }
  $("visual-actions").hidden = kind !== "visual";
  if (kind === "python") python.list();
  else editors[mode].arrange();
};
const properties = new PropertiesPanel($("properties-panel"), updateParam, selectGroup);
const editors = {
  blocks: new BlocksEditor($("blockly"), changed, inspectGroup),
  graph: new GraphEditor($("litegraph"), $("graph-canvas"), changed, inspectGroup),
};

function setStatus(message, error = false, state = "processing") {
  status.textContent = message;
  status.classList.toggle("error", error);
  status.dataset.state = error ? "error" : state;
}

function readModel() {
  return { ...model, name: $("name").value, version: $("version").value, params: editors[mode].readParams() };
}

function changed() {
  revision++;
  result = null;
  outputButtons.forEach(button => { button.disabled = true; });
  $("source").textContent = "";
  $("draft-state").textContent = "Изменения ещё не проверены и не сохранены.";
  $("requirements").classList.add("stale");
  $("requirements-help").textContent = "Требования обновятся после проверки параметров.";
  properties.showError();
  try { properties.sync(editors[mode].readParams()); } catch { /* Invalid fields stay editable. */ }
  renderPublication();
  setStatus("Проверка параметров…");
  clearTimeout(timer);
  timer = setTimeout(validate, 200);
}

function updateParam(name, value) {
  try { editors[mode].setParam(name, value); }
  catch (error) { setStatus(error.message, true); }
}

function showPanel(panel) {
  for (const name of ["properties", "source"]) {
    const active = name === panel;
    $(`${name}-panel`).hidden = !active;
    $(`${name}-tab`).setAttribute("aria-selected", String(active));
    $(`${name}-tab`).tabIndex = active ? 0 : -1;
  }
}

function inspectGroup(key, field) {
  if (!key) return;
  showPanel("properties");
  properties.select(key, field);
}

function selectGroup(key) {
  inspectGroup(key);
  editors[mode].selectGroup(key);
}

async function post(route, body) {
  const response = await fetch(`/api/${route}`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Editor-Token": token },
    body: JSON.stringify(body), signal: AbortSignal.timeout(10000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(friendlyError(data.error ?? "Не удалось выполнить запрос."));
  return data;
}

function renderRequirements(requirements) {
  const values = {
    "Таймфрейм": requirements.timeframe,
    "История для расчёта": `${requirements.history_bars} баров`,
    "Доп. прогрев": requirements.warmup_bars ? `${requirements.warmup_bars} баров` : "Не требуется",
    "Часовой пояс": requirements.timezone,
    "Решение": requirements.decision_times.map(value => value.slice(0, 5)).join(", ") || "Каждый вызов",
    "Начало сессии": requirements.session_start?.slice(0, 5) ?? "Не задано",
  };
  const minimum = requirements.minimum_session_bars;
  if (minimum) values["Минимум в сессии"] = `${minimum} баров`;
  $("requirements").classList.remove("stale");
  $("requirements-help").textContent = "Требования задаёт выбранный локальный модуль.";
  $("requirements").replaceChildren();
  for (const [label, value] of Object.entries(values)) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    $("requirements").append(term, description);
  }
}

async function validate() {
  const current = revision;
  try {
    const next = readModel();
    const compiled = await post("compile", next);
    if (current !== revision) return;
    model = compiled.model;
    result = compiled;
    $("source").textContent = compiled.python;
    renderRequirements(compiled.requirements);
    properties.sync(model.params);
    outputButtons.forEach(button => { button.disabled = false; });
    renderPublication();
    try {
      localStorage.setItem(DRAFT, JSON.stringify(model));
      $("draft-state").textContent = "Проверенный черновик сохранён в этом браузере.";
      setStatus("Параметры проверены. Черновик сохранён в браузере.", false, "ready");
    } catch {
      $("draft-state").textContent = "Хранилище браузера недоступно. Скачайте JSON.";
      setStatus("Параметры проверены. Сохраните JSON: хранилище браузера недоступно.");
    }
  } catch (error) {
    if (current === revision) {
      properties.showError(error.message);
      $("draft-state").textContent = "Изменения не сохранены. Последний корректный черновик остаётся в браузере.";
      setStatus(`Проверка: ${error.message}`, true);
    }
  }
}

function renderPublication() {
  const current = result && publication?.model === JSON.stringify(model);
  const exists = result?.catalog_file_exists;
  $("publication-state").textContent = current
    ? `В каталоге создан файл ${publication.filename}.`
    : exists ? `В каталоге уже есть ${model.name}.py. Для обновления скачайте Python; автоматическая перезапись запрещена.`
      : publication ? `Текущие изменения не опубликованы. Ранее создан ${publication.filename}.`
        : result ? "Файла с этим именем в каталоге пока нет." : "Состояние каталога уточняется после проверки.";
  $("publish").textContent = current ? "Создано в каталоге" : exists ? "Имя уже занято" : "Создать в каталоге";
  $("publish").disabled = current || exists || !result;
}

function loadModel(next) {
  model = checkModel(next, templates);
  const template = templates.find(item => item.name === model.template);
  $("template").value = model.template;
  $("name").value = model.name;
  $("version").value = model.version;
  editors[mode].setModel(model, template);
  properties.setModel(model, template);
  changed();
}

function switchMode(next) {
  if (mode === next) return;
  try {
    model = readModel();
    mode = next;
    editors.blocks.show(next === "blocks");
    editors.graph.show(next === "graph");
    $("blocks-tab").setAttribute("aria-selected", next === "blocks");
    $("graph-tab").setAttribute("aria-selected", next === "graph");
    $("blocks-tab").tabIndex = next === "blocks" ? 0 : -1;
    $("graph-tab").tabIndex = next === "graph" ? 0 : -1;
    $("canvas-panel").setAttribute("aria-labelledby", `${next}-tab`);
    editors[next].setModel(model, templates.find(item => item.name === model.template));
    properties.sync(model.params);
    changed();
  } catch (error) { setStatus(error.message, true); }
}

function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$("blocks-tab").addEventListener("click", () => switchMode("blocks"));
$("graph-tab").addEventListener("click", () => switchMode("graph"));
$("properties-tab").addEventListener("click", () => showPanel("properties"));
$("source-tab").addEventListener("click", () => showPanel("source"));
$("arrange").addEventListener("click", () => editors[mode].arrange());
$("restore").addEventListener("click", () => loadModel({ ...model, name: $("name").value, version: $("version").value }));
$("name").addEventListener("input", changed);
$("version").addEventListener("input", changed);
$("template").addEventListener("change", () => loadModel(newModel(templates.find(item => item.name === $("template").value))));
$("import").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", async event => {
  const file = event.target.files[0];
  try {
    if (!file) return;
    if (file.size > 65536) throw new Error("Проект должен помещаться в 64 КиБ.");
    const next = checkModel(JSON.parse(await file.text()), templates);
    await post("compile", next);
    loadModel(next);
  } catch (error) { setStatus(`Не удалось открыть: ${error.message}`, true); }
  finally { event.target.value = ""; }
});
$("save").addEventListener("click", () => {
  if (result) download(`${model.name}.json`, `${JSON.stringify(model, null, 2)}\n`, "application/json");
});
$("download").addEventListener("click", () => {
  if (result) download(`${model.name}.py`, result.python, "text/x-python");
});
$("publish").addEventListener("click", async () => {
  if (!result) return;
  const snapshot = result.model;
  const current = revision;
  $("publish").disabled = true;
  try {
    const published = await post("publish", snapshot);
    publication = { ...published, model: JSON.stringify(snapshot) };
    renderPublication();
    if (current === revision) setStatus(`Создан файл ${published.filename}. Скачайте JSON для дальнейшего редактирования.`, false, "ready");
  } catch (error) { setStatus(`Не удалось добавить: ${error.message}`, true); }
  finally { renderPublication(); }
});

for (const tabs of document.querySelectorAll('[role="tablist"]')) {
  tabs.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(tabs.querySelectorAll('[role="tab"]'));
    const index = buttons.indexOf(document.activeElement);
    if (index === -1) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
      : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].click();
    buttons[next].focus();
  });
}

new ResizeObserver(() => editors[mode].arrange()).observe($("blockly").parentElement);

try {
  const response = await fetch("/api/catalog");
  if (!response.ok) throw new Error("Каталог SDK недоступен.");
  const catalog = await response.json();
  templates = catalog.templates;
  token = catalog.token;
  for (const template of templates) {
    const option = document.createElement("option");
    option.value = template.name;
    option.textContent = template.name;
    $("template").append(option);
  }
  let initial = newModel(templates[0]);
  initial.name = "my_cny_sma";
  let draftWarning;
  try {
    const draft = localStorage.getItem(DRAFT);
    if (draft) initial = checkModel(JSON.parse(draft), templates);
  } catch { draftWarning = "Черновик недоступен. Открыт новый проект."; }
  loadModel(initial);
  if (draftWarning) setStatus(draftWarning);
} catch (error) {
  setStatus(error.message, true);
  $("template").disabled = true;
}
