export const GROUPS = {
  schedule: { label: "Время и данные" },
  signal: { label: "Условия сигнала" },
  restrictions: { label: "Допуск направления" },
  sizing: { label: "Размер позиции" },
  other: { label: "Другие параметры" },
};

const GROUP_KEYS = {
  schedule: ["timeframe", "timezone", "decision_time", "session_start"],
  signal: ["sma_period", "confirmation_bars", "filter_bars", "fast_window", "slow_window",
    "window_bars", "window_minutes", "min_session_bars", "max_session_bars", "filter_minutes",
    "short_filter", "use_long_filter", "use_short_filter", "use_recent_filter"],
  restrictions: ["short_blocked_weekdays", "long_blocked_weekdays", "block_friday_short",
    "allow_long", "allow_short", "enforce_document_instruments", "allowed_contract_prefixes"],
  sizing: ["initial_percent", "leverage_percent", "add_percent", "contracts", "contracts_per_day"],
};

export const LABELS = {
  timeframe: "Таймфрейм", timezone: "Часовой пояс", decision_time: "Время решения",
  session_start: "Начало сессии", sma_period: "Период SMA", confirmation_bars: "Баров подтверждения",
  filter_bars: "Баров фильтра", fast_window: "Быстрая SMA", slow_window: "Медленная SMA",
  window_bars: "Окно в барах", window_minutes: "Окно в минутах", min_session_bars: "Минимум баров сессии",
  max_session_bars: "Максимум баров сессии", filter_minutes: "Минут фильтра",
  short_filter: "Фильтр SHORT", use_long_filter: "Фильтр LONG", use_short_filter: "Фильтр SHORT",
  use_recent_filter: "Фильтр последних баров", short_blocked_weekdays: "Запрет SHORT: дни",
  long_blocked_weekdays: "Запрет LONG: дни", block_friday_short: "Запрет SHORT в пятницу",
  allow_long: "Разрешить LONG", allow_short: "Разрешить SHORT",
  enforce_document_instruments: "Проверять инструмент", allowed_contract_prefixes: "Префиксы контрактов",
  initial_percent: "Начальная позиция, %", leverage_percent: "Плечо, %", add_percent: "Добор, %",
  contracts: "Контрактов", contracts_per_day: "Контрактов в день",
};

export const WEEKDAYS = [
  ["MON", "Пн", "Понедельник"], ["TUE", "Вт", "Вторник"], ["WED", "Ср", "Среда"],
  ["THU", "Чт", "Четверг"], ["FRI", "Пт", "Пятница"], ["SAT", "Сб", "Суббота"], ["SUN", "Вс", "Воскресенье"],
];

export function displayValue(value, spec) {
  if (spec.type === "bool") return value ? "Да" : "Нет";
  if (spec.name.endsWith("_blocked_weekdays")) {
    return value ? String(value).split(",").map(code => WEEKDAYS.find(day => day[0] === code)?.[1] ?? code).join(", ") : "Нет запрета";
  }
  return value === null || value === "" ? "Не задано" : String(value);
}

export function friendlyError(message) {
  const messages = {
    "Decision time must be on the M5 grid": "Время решения должно попадать на границу M5: минуты, кратные пяти.",
    "Clock must use HH:MM notation": "Укажите время в формате ЧЧ:ММ.",
    "Clock must be a naive wall-clock time at minute precision": "Укажите часы и минуты без секунд и часового пояса.",
    "Name must contain lowercase letters, digits and underscores": "Имя должно начинаться с латинской буквы и содержать строчные буквы, цифры и подчёркивание.",
    "Choose a new name; an existing SDK strategy cannot be overwritten": "Выберите новое имя. Базовый алгоритм SDK нельзя перезаписать.",
    "Version must contain 1 to 40 letters, digits, dots or underscores": "Версия: от 1 до 40 латинских букв, цифр, точек или подчёркиваний.",
    "File already exists; choose another name": "Файл уже существует. Задайте новое имя или скачайте Python для отдельного обновления.",
    "Cannot read or write editor files": "Редактор не смог прочитать или записать файл. Проверьте доступ к каталогу.",
    "Editor session authorization is required": "Сессия редактора устарела. Обновите страницу.",
  };
  if (messages[message]) return messages[message];
  const suffixes = {
    "is below its minimum": "значение меньше допустимого минимума.",
    "exceeds its maximum": "значение больше допустимого максимума.",
    "must be an integer without a fractional part": "нужно целое число.",
    "must be a finite number": "нужно конечное число.",
    "must be finite": "нужно конечное число.",
    "cannot be null in the editor": "значение обязательно.",
  };
  for (const [suffix, text] of Object.entries(suffixes)) {
    if (message.endsWith(suffix)) {
      const name = message.slice(0, -suffix.length).trim();
      return `${LABELS[name] ?? name}: ${text}`;
    }
  }
  return message;
}

export function groupsFor(template) {
  const groups = {};
  for (const spec of template.specs) {
    const group = Object.keys(GROUP_KEYS).find(key => GROUP_KEYS[key].includes(spec.name)) ?? "other";
    (groups[group] ??= []).push(spec);
  }
  return Object.entries(GROUPS).filter(([key]) => groups[key]).map(([key, style]) => ({
    key, ...style, specs: groups[key],
  }));
}

export function valueText(value) {
  return value === null ? "" : String(value);
}

export function parseValue(value, spec) {
  if (value === null || (value === "" && spec.nullable)) return null;
  if (spec.type === "bool") {
    if (value === true || value === "TRUE") return true;
    if (value === false || value === "FALSE") return false;
    throw new Error(`${LABELS[spec.name] ?? spec.name}: нужно логическое значение.`);
  }
  if (spec.type === "str" || spec.type === "decimal") return String(value);
  const number = Number(value);
  const numeric = /^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?$/;
  if (!numeric.test(String(value).trim()) || !Number.isFinite(number)) {
    throw new Error(`${LABELS[spec.name] ?? spec.name}: нужно число.`);
  }
  if (spec.type === "int" && !Number.isSafeInteger(number)) {
    throw new Error(`${LABELS[spec.name] ?? spec.name}: нужно целое число.`);
  }
  return number;
}

export function newModel(template) {
  return {
    schema_version: 1, name: `my_${template.name}`, version: "1",
    template: template.name, params: { ...template.params },
  };
}

export function checkModel(model, templates) {
  const keys = ["schema_version", "name", "version", "template", "params"];
  if (!model || typeof model !== "object" || Object.keys(model).length !== keys.length
      || keys.some(key => !Object.hasOwn(model, key)) || model.schema_version !== 1) {
    throw new Error("Неизвестный формат проекта. Откройте JSON, сохранённый этим редактором.");
  }
  const template = templates.find(item => item.name === model.template);
  if (!template) throw new Error("Алгоритм отсутствует в каталоге SDK.");
  if (typeof model.name !== "string" || typeof model.version !== "string"
      || !model.params || typeof model.params !== "object" || Array.isArray(model.params)
      || Object.keys(model.params).length !== template.specs.length
      || template.specs.some(spec => !Object.hasOwn(model.params, spec.name))) {
    throw new Error("Проект содержит неполные или неизвестные параметры.");
  }
  const params = {};
  for (const spec of template.specs) {
    const value = model.params[spec.name];
    if (value !== null && !["string", "boolean", "number"].includes(typeof value)) {
      throw new Error("Параметры должны быть простыми значениями.");
    }
    if (value === null && !spec.nullable) throw new Error(`${spec.name}: значение обязательно.`);
    if (value !== null && ((spec.type === "str" && typeof value !== "string")
        || (spec.type === "bool" && typeof value !== "boolean"))) {
      throw new Error(`${spec.name}: неверный тип параметра.`);
    }
    params[spec.name] = value === null ? null : parseValue(value, spec);
  }
  return { ...model, params };
}
