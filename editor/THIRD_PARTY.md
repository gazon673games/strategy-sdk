# Библиотеки интерфейса

- [Blockly 13.3.0](https://github.com/google/blockly), Apache-2.0.
- [LiteGraph.js 0.7.18](https://github.com/jagenjo/litegraph.js), MIT.

Версии закреплены в `package.json` и `package-lock.json`. При сборке их лицензии
копируются в `dist/blockly-LICENSE.txt` и `dist/litegraph.js-LICENSE.txt`.

Для LiteGraph сборка использует ядро до границы `//basic nodes`: встроенные
узлы для JavaScript, сетевых запросов и мультимедиа не включены. В ядре
арифметический `eval` числового виджета заменяется на `Number`; поля нашего
редактора используют текстовые виджеты. `allow_scripts=false`, политика CSP
запрещает выполнение строк как JavaScript. Проверки границ преобразования
останавливают сборку при несовместимом обновлении библиотеки.

Радиус полей LiteGraph ограничен 4 px при сборке, чтобы canvas соответствовал
геометрии остальных элементов редактора.

Документация: [Blockly](https://docs.blockly.com/),
[LiteGraph](https://github.com/jagenjo/litegraph.js/blob/master/guides/README.md).
