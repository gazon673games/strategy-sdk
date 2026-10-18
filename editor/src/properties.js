import { LABELS, WEEKDAYS, groupsFor, valueText } from "./model.js";

const HELP = {
  timezone: "Время решения и начало сессии считаются в этом часовом поясе. Москва: UTC+03:00.",
  decision_time: "Локальное время решения. Для M5 используйте минуты, кратные пяти.",
  session_start: "Начало торговой сессии в выбранном часовом поясе.",
  sma_period: "Количество баров для одного значения SMA.",
  confirmation_bars: "Каждый завершённый бар сравнивается со своей SMA на тот момент.",
  short_blocked_weekdays: "В отмеченные дни направление SHORT запрещено. Без отметок запрета нет.",
  long_blocked_weekdays: "В отмеченные дни направление LONG запрещено. Без отметок запрета нет.",
  initial_percent: "Номинальная стоимость нового входа относительно стоимости счёта.",
  leverage_percent: "Номинальная стоимость нового входа относительно стоимости счёта.",
};

function helpFor(spec) { return HELP[spec.name] ?? ""; }

export class PropertiesPanel {
  constructor(container, changed, selected) {
    this.container = container;
    this.fields = container.querySelector("#property-fields");
    this.selector = container.querySelector("#property-group");
    this.changed = changed;
    this.fields.addEventListener("submit", event => event.preventDefault());
    this.selector.addEventListener("change", () => selected(this.selector.value));
  }

  setModel(model, template) {
    this.params = { ...model.params };
    this.template = template;
    this.groups = groupsFor(template);
    this.selector.replaceChildren(...this.groups.map(group => new Option(group.label, group.key)));
    const next = this.groups.some(group => group.key === this.group) ? this.group : this.groups[0]?.key;
    this.group = null;
    this.select(next);
  }

  select(key, field) {
    const group = this.groups?.find(item => item.key === key);
    if (!group) return;
    if (this.group !== key) {
      this.group = key;
      this.selector.value = key;
      this.container.querySelector("#property-title").textContent = group.label;
      this.controls = new Map();
      this.fields.replaceChildren();
      for (const spec of group.specs) this.addField(spec);
    }
    if (field) {
      const control = this.controls.get(field)?.element;
      (control?.querySelector("input") ?? control)?.focus();
    }
  }

  addField(spec) {
    const days = spec.name.endsWith("_blocked_weekdays");
    const row = document.createElement(days ? "fieldset" : "div");
    row.className = "property-field";
    const label = document.createElement(days ? "legend" : "label");
    label.textContent = LABELS[spec.name] ?? spec.name;
    if (spec.name === "initial_percent") label.textContent = "Новый вход, % от капитала";
    if (spec.name === "leverage_percent") label.textContent = "Позиция, % от капитала";
    if (spec.name === "add_percent") label.textContent = "Добор, %";
    const hint = document.createElement("p");
    hint.className = "field-help";
    hint.id = `help-${spec.name}`;
    hint.textContent = helpFor(spec, this.template);
    const limits = [spec.min === null ? "" : `Минимум: ${spec.min}.`, spec.max === null ? "" : `Максимум: ${spec.max}.`];
    if (spec.type === "int") hint.textContent += ` Целое число. ${limits.join(" ")}`;
    if (spec.type === "decimal" || spec.type === "float") hint.textContent += " Дробная часть отделяется точкой.";
    if (spec.nullable) hint.textContent += " Пустое поле: значение не задано.";
    let element, set;
    if (days) {
      element = document.createElement("div");
      element.className = "weekdays";
      for (const [code, short, full] of WEEKDAYS) {
        const day = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = code;
        input.setAttribute("aria-label", full);
        const text = document.createElement("span");
        text.textContent = short;
        day.title = full;
        day.append(input, text);
        element.append(day);
      }
      set = value => element.querySelectorAll("input").forEach(input => { input.checked = valueText(value).split(",").includes(input.value); });
      element.addEventListener("change", () => {
        const value = Array.from(element.querySelectorAll("input:checked"), input => input.value).join(",");
        this.params[spec.name] = value;
        this.changed(spec.name, value);
      });
    } else {
      element = document.createElement(spec.choices.length ? "select" : "input");
      element.id = `param-${spec.name}`;
      label.htmlFor = element.id;
      element.name = spec.name;
      element.setAttribute("aria-describedby", hint.id);
      if (spec.choices.length) {
        if (spec.nullable) element.add(new Option("Не задано", ""));
        spec.choices.forEach(value => element.add(new Option(String(value), String(value))));
        if (spec.choices.length === 1 && !spec.nullable) {
          element.disabled = true;
          hint.textContent += " Фиксировано выбранным алгоритмом.";
        }
      } else {
        element.type = spec.type === "bool" ? "checkbox" : ["decision_time", "session_start"].includes(spec.name) ? "time" : "text";
        if (spec.type === "int") element.inputMode = "numeric";
        if (["decimal", "float"].includes(spec.type)) element.inputMode = "decimal";
        if (element.type === "time") element.step = "60";
        element.spellcheck = false;
        if (spec.name === "timezone") {
          element.setAttribute("list", "timezones");
          const list = document.createElement("datalist");
          list.id = "timezones";
          ["UTC+03:00", "UTC", "UTC+02:00", "UTC+04:00"].forEach(value => list.append(new Option(value)));
          row.append(list);
        }
      }
      set = value => { if (spec.type === "bool") element.checked = !!value; else element.value = valueText(value); };
      element.addEventListener(element.tagName === "SELECT" || element.type === "checkbox" ? "change" : "input", () => {
        const value = spec.type === "bool" ? element.checked : element.value;
        this.params[spec.name] = value;
        this.changed(spec.name, value);
      });
    }
    set(this.params[spec.name]);
    row.append(label, element, hint);
    this.fields.append(row);
    this.controls.set(spec.name, { element, set });
  }

  sync(params) {
    this.params = { ...params };
    for (const [name, control] of this.controls ?? []) {
      if (!control.element.contains(document.activeElement)) control.set(params[name]);
    }
  }

  showError(message = "") {
    for (const [name, control] of this.controls ?? []) {
      const invalid = message.includes(name) || (LABELS[name] && message.includes(LABELS[name]));
      control.element.setAttribute("aria-invalid", String(!!invalid));
    }
  }
}
