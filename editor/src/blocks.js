import * as Blockly from "blockly/core";
import * as Russian from "blockly/msg/ru";
import { LABELS, groupsFor, parseValue, valueText } from "./model.js";
import { theme as colours } from "./theme.js";

Blockly.setLocale(Russian);

function field(spec) {
  if (spec.type === "bool") return new Blockly.FieldCheckbox("FALSE");
  if (spec.choices.length) {
    return new Blockly.FieldDropdown(spec.choices.map(value => [String(value), String(value)]));
  }
  const input = new Blockly.FieldTextInput("");
  input.setSpellcheck(false);
  return input;
}

export class BlocksEditor {
  constructor(container, changed, selected) {
    this.container = container;
    this.changed = changed;
    this.loading = false;
    const theme = Blockly.Theme.defineTheme("sdk", {
      base: Blockly.Themes.Classic,
      fontStyle: { family: "Segoe UI, sans-serif", size: 11, weight: "500" },
      componentStyles: { workspaceBackgroundColour: colours.canvas, toolboxBackgroundColour: colours.panel,
        flyoutBackgroundColour: colours.panel, flyoutOpacity: 1, scrollbarColour: colours.border,
        insertionMarkerColour: colours.accent, insertionMarkerOpacity: 0.3 },
    });
    this.workspace = Blockly.inject(container, {
      theme, trashcan: false, sounds: false, media: "/blockly-media/",
      zoom: { controls: true, wheel: true, startScale: 0.85, minScale: 0.35, maxScale: 1.5 },
      grid: { spacing: 24, length: 1, colour: colours.grid, snap: true },
    });
    this.workspace.addChangeListener(event => {
      if (!this.loading && event.type === Blockly.Events.SELECTED) {
        const block = this.workspace.getBlockById(event.newElementId);
        const group = this.groups?.find(item => block?.type === `sdk_${this.template.name}_${item.key}`);
        if (group && Blockly.getSelected() === block) selected(group.key);
      }
      if (!this.loading && !event.isUiEvent && event.type !== Blockly.Events.FINISHED_LOADING) changed();
    });
  }

  setModel(model, template) {
    this.loading = true;
    this.template = template;
    this.groups = groupsFor(template);
    const rootType = `sdk_${template.name}_strategy`;
    if (!Blockly.Blocks[rootType]) {
      const groups = this.groups;
      Blockly.Blocks[rootType] = { init() {
        this.appendDummyInput().appendField(template.name);
        for (const group of groups) {
          this.appendValueInput(group.key).setCheck(`sdk_${group.key}`).appendField(group.label);
        }
        this.setColour(colours.blocks.root);
        this.setTooltip(template.description);
      } };
      for (const group of groups) {
        Blockly.Blocks[`sdk_${template.name}_${group.key}`] = { init() {
          this.appendDummyInput().appendField(group.label);
          for (const spec of group.specs) {
            this.appendDummyInput().appendField(LABELS[spec.name] ?? spec.name)
              .appendField(field(spec), `p_${spec.name}`);
          }
          this.setOutput(true, `sdk_${group.key}`);
          this.setColour(colours.blocks[group.key]);
          this.setTooltip("Измените значения и подключите блок к соответствующему входу стратегии.");
        } };
      }
    }
    this.workspace.clear();
    this.root = this.workspace.newBlock(rootType);
    this.root.setDeletable(false);
    this.root.initSvg();
    this.root.render();
    this.root.moveBy(40, 35);
    for (const group of this.groups) {
      const block = this.workspace.newBlock(`sdk_${template.name}_${group.key}`);
      for (const spec of group.specs) {
        const value = model.params[spec.name];
        block.setFieldValue(spec.type === "bool" ? (value ? "TRUE" : "FALSE") : valueText(value), `p_${spec.name}`);
      }
      block.initSvg();
      block.render();
      block.setDeletable(false);
      this.root.getInput(group.key).connection.connect(block.outputConnection);
    }
    // Blockly dispatches initial create/change events asynchronously.
    setTimeout(() => { this.loading = false; this.arrange(); }, 0);
  }

  setParam(name, value) {
    const group = this.groups.find(item => item.specs.some(spec => spec.name === name));
    const spec = group.specs.find(item => item.name === name);
    const block = this.workspace.getAllBlocks(false).find(item => item.type === `sdk_${this.template.name}_${group.key}`);
    if (!block) throw new Error(`Раздел «${group.label}» отсутствует на схеме.`);
    block.setFieldValue(spec.type === "bool" ? (value ? "TRUE" : "FALSE") : valueText(value), `p_${name}`);
    // Invalidate a pending compile immediately; Blockly emits field events asynchronously.
    this.changed();
  }

  selectGroup(key) {
    this.root.getInputTargetBlock(key)?.select();
  }

  readParams() {
    const params = {};
    if (this.workspace.getAllBlocks(false).length !== this.groups.length + 1) {
      throw new Error("Удалите лишние блоки. Каждый раздел должен быть подключён один раз.");
    }
    for (const group of this.groups) {
      const block = this.root.getInputTargetBlock(group.key);
      if (!block || block.type !== `sdk_${this.template.name}_${group.key}`) {
        throw new Error(`Подключите блок «${group.label}» к стратегии.`);
      }
      for (const spec of group.specs) params[spec.name] = parseValue(block.getFieldValue(`p_${spec.name}`), spec);
    }
    return params;
  }

  resize() { Blockly.svgResize(this.workspace); }
  arrange() {
    this.resize();
    this.workspace.zoomToFit();
    if (this.workspace.scale > 1) this.workspace.setScale(1);
    this.workspace.scrollCenter();
  }
  show(visible) { this.container.hidden = !visible; if (visible) this.resize(); }
}
