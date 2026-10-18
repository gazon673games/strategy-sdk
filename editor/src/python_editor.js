import starter from "../examples/new_strategy.py?raw";

const DRAFT = "strategy-sdk.python.v1";
const $ = id => document.getElementById(id);

export class PythonEditor {
  constructor(post) {
    this.post = post;
    this.revision = null;
    this.savedFilename = null;
    this.dirty = false;
    this.sequence = 0;
    $("python-new").onclick = () => this.replace("new_strategy.py", starter, null);
    $("python-open").onclick = () => this.open();
    $("python-check").onclick = () => this.validate();
    $("python-save").onclick = () => this.save();
    $("python-export").onclick = () => this.download();
    $("python-import").onclick = () => $("python-file").click();
    $("python-file").onchange = async event => {
      const file = event.target.files[0];
      try {
        if (file && file.size <= 262144) this.replace(file.name, await file.text(), null);
        else if (file) throw new Error("Python-файл должен помещаться в 256 КиБ.");
      } catch (error) { this.status(error.message, true); }
      event.target.value = "";
    };
    for (const id of ["python-code", "python-filename", "python-params"]) $(id).oninput = () => this.changed();
    $("python-code").onkeydown = event => {
      const field = event.target;
      if (event.key === "Tab") {
        event.preventDefault();
        field.setRangeText("    ", field.selectionStart, field.selectionEnd, "end");
        this.changed();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        this.save();
      }
    };
    window.addEventListener("beforeunload", event => {
      if (this.dirty) { event.preventDefault(); event.returnValue = ""; }
    });
    let draft;
    try { draft = JSON.parse(localStorage.getItem(DRAFT)); } catch { /* New draft. */ }
    this.replace(draft?.filename ?? "new_strategy.py", draft?.source ?? starter, null, false);
    $("python-params").value = draft?.params ?? "{}";
    this.dirty = Boolean(draft);
  }

  status(message, failed = false) {
    $("python-status").textContent = message;
    $("python-status").classList.toggle("error", failed);
  }

  changed() {
    this.sequence++;
    this.dirty = true;
    this.status("Черновик изменён. В каталоге изменения ещё не сохранены.");
    try {
      localStorage.setItem(DRAFT, JSON.stringify({ filename: $("python-filename").value,
        source: $("python-code").value, params: $("python-params").value }));
    } catch { this.status("Черновик изменён. Хранилище браузера недоступно: скачайте Python."); }
  }

  replace(filename, source, revision, ask = true) {
    if (ask && this.dirty && !confirm("Заменить несохранённый код? При необходимости сначала скачайте Python.")) return;
    this.sequence++;
    $("python-filename").value = filename;
    $("python-code").value = source;
    $("python-params").value = "{}";
    this.revision = revision;
    this.savedFilename = revision ? filename : null;
    this.dirty = !revision;
    this.status(revision ? `Открыт ${filename}. Сохранение изменит общий файл SDK.` : "Новый Python-сценарий. Измените алгоритм и сохраните в каталоге.");
  }

  async list() {
    try {
      const response = await fetch("/api/sources");
      if (!response.ok) throw new Error("Каталог Python-файлов недоступен.");
      const data = await response.json();
      const selected = $("python-catalog").value;
      $("python-catalog").replaceChildren(...data.files.map(filename => {
        const option = document.createElement("option");
        option.value = option.textContent = filename;
        return option;
      }));
      if (data.files.includes(selected)) $("python-catalog").value = selected;
    } catch (error) { this.status(error.message, true); }
  }

  async open() {
    const sequence = this.sequence;
    try {
      const file = await this.post("source/open", { filename: $("python-catalog").value });
      if (sequence === this.sequence) this.replace(file.filename, file.source, file.revision);
    } catch (error) { this.status(error.message, true); }
  }

  payload() {
    const filename = $("python-filename").value.trim();
    const params = JSON.parse($("python-params").value);
    if (!params || typeof params !== "object" || Array.isArray(params)) throw new Error("Параметры: нужен JSON-объект.");
    return { filename, source: $("python-code").value, params,
      revision: filename === this.savedFilename ? this.revision : null };
  }

  async validate() {
    const sequence = this.sequence;
    try {
      this.status("Проверка контракта SDK…");
      const result = await this.post("source/validate", this.payload());
      if (sequence !== this.sequence) return;
      $("python-contract").textContent = JSON.stringify(result.requirements, null, 2);
      this.status("Контракт SDK проверен. Для проверки логики запустите бэктест.");
    } catch (error) { if (sequence === this.sequence) this.status(error.message, true); }
  }

  async save() {
    const sequence = this.sequence;
    $("python-save").disabled = true;
    try {
      const saved = await this.post("source/save", this.payload());
      this.savedFilename = saved.filename;
      this.revision = saved.revision;
      if (sequence === this.sequence) {
        this.dirty = false;
        this.status(`Сохранён ${saved.filename}. Бэктест увидит обновление при следующем запуске.`);
      } else this.status(`Сохранена предыдущая версия ${saved.filename}. Текущие правки ещё не сохранены.`);
      await this.list();
    } catch (error) { this.status(error.message, true); }
    finally { $("python-save").disabled = false; }
  }

  download() {
    const link = document.createElement("a");
    const url = URL.createObjectURL(new Blob([$("python-code").value], { type: "text/x-python" }));
    link.href = url;
    link.download = $("python-filename").value;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
