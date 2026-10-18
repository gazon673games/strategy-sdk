import Package from "litegraph.js";
import "litegraph.js/css/litegraph.css";
import { LABELS, displayValue, groupsFor, parseValue, valueText } from "./model.js";
import { theme } from "./theme.js";

const { LiteGraph, LGraph, LGraphCanvas } = Package;
LiteGraph.clearRegisteredTypes();
LiteGraph.allow_scripts = false;
LiteGraph.MAX_NUMBER_OF_NODES = 32;
LiteGraph.NODE_TITLE_COLOR = theme.text;
LiteGraph.NODE_TEXT_COLOR = theme.secondary;
LiteGraph.NODE_DEFAULT_BOXCOLOR = theme.border;
LiteGraph.NODE_BOX_OUTLINE_COLOR = theme.accent;
LiteGraph.NODE_SELECTED_TITLE_COLOR = theme.text;
LiteGraph.WIDGET_BGCOLOR = theme.sunken;
LiteGraph.WIDGET_TEXT_COLOR = theme.text;
LiteGraph.WIDGET_SECONDARY_TEXT_COLOR = theme.secondary;
LiteGraph.WIDGET_OUTLINE_COLOR = theme.border;
LiteGraph.LINK_COLOR = theme.info;

export class GraphEditor {
  constructor(container, canvas, changed, selected) {
    this.container = container;
    this.canvas = canvas;
    this.changed = changed;
    this.loading = false;
    this.graph = new LGraph();
    this.view = new LGraphCanvas(canvas, this.graph, { skip_render: true });
    this.view.background_image = null;
    this.view.clear_background_color = theme.canvas;
    this.view.title_text_font = `600 16px ${theme.font}`;
    this.view.inner_text_font = `14px ${theme.font}`;
    this.view.connections_width = 2;
    this.view.default_connection_color = {
      input_on: theme.info, output_on: theme.info, input_off: theme.border, output_off: theme.border,
    };
    this.view.render_shadows = false;
    this.view.render_canvas_border = false;
    this.view.show_info = false;
    this.view.allow_searchbox = false;
    this.view.onShowNodePanel = () => false;
    this.view.onDropItem = () => true;
    this.view.onNodeSelected = node => { if (node.groupKey) selected(node.groupKey); };
    // Canvas rows open the accessible properties panel instead of LiteGraph's generic prompt.
    this.view.processNodeWidgets = (node, pos, event) => {
      const y = pos[1] - node.pos[1];
      const widget = node.widgets?.find(item => y >= item.last_y && y <= item.last_y + LiteGraph.NODE_WIDGET_HEIGHT);
      if (widget && event.type === `${LiteGraph.pointerevents_method}down`) {
        event.preventDefault();
        selected(node.groupKey, widget.options.property);
        return widget;
      }
      return null;
    };
    this.graph.onAfterChange = () => { if (!this.loading) changed(); };
    this.graph.onConnectionChange = this.graph.onAfterChange;
  }

  setModel(model, template) {
    this.loading = true;
    this.template = template;
    this.groups = groupsFor(template);
    const rootType = `sdk/${template.name}/strategy`;
    if (!LiteGraph.registered_node_types[rootType]) {
      const groups = this.groups;
      function StrategyNode() {
        for (const group of groups) this.addInput(group.label, `sdk_${group.key}`);
        this.color = theme.blocks.root;
        this.bgcolor = theme.surface;
        this.shape = LiteGraph.BOX_SHAPE;
        this.size = [260, Math.max(100, groups.length * 24 + 35)];
        this.removable = false;
      }
      StrategyNode.title = template.name;
      LiteGraph.registerNodeType(rootType, StrategyNode);
      for (const group of groups) {
        function SettingsNode() {
          this.properties = {};
          this.groupKey = group.key;
          this.addOutput("", `sdk_${group.key}`);
          this.color = theme.blocks[group.key];
          this.bgcolor = theme.surface;
          this.shape = LiteGraph.BOX_SHAPE;
          for (const spec of group.specs) {
            this.properties[spec.name] = spec.type === "bool" ? false : "";
            this.addWidget("text", LABELS[spec.name] ?? spec.name, "", null, { property: spec.name });
          }
          this.size = [320, this.computeSize()[1]];
        }
        SettingsNode.title = group.label;
        LiteGraph.registerNodeType(`sdk/${template.name}/${group.key}`, SettingsNode);
      }
    }
    this.graph.clear();
    this.root = LiteGraph.createNode(rootType);
    this.graph.add(this.root);
    let y = 45;
    this.groups.forEach((group, index) => {
      const node = LiteGraph.createNode(`sdk/${template.name}/${group.key}`);
      node.pos = [30, y];
      group.specs.forEach((spec, widgetIndex) => {
        const value = spec.type === "bool" ? model.params[spec.name] : valueText(model.params[spec.name]);
        node.properties[spec.name] = value;
        node.widgets[widgetIndex].value = displayValue(model.params[spec.name], spec);
      });
      this.graph.add(node);
      node.connect(0, this.root, index);
      y += node.size[1] + 42;
    });
    this.root.pos = [415, Math.max(80, y / 2 - 100)];
    this.loading = false;
    this.arrange();
  }

  setParam(name, value) {
    const group = this.groups.find(item => item.specs.some(spec => spec.name === name));
    const node = this.graph._nodes.find(item => item.groupKey === group.key);
    if (!node) throw new Error(`Раздел «${group.label}» отсутствует на схеме.`);
    const index = group.specs.findIndex(spec => spec.name === name);
    node.properties[name] = value;
    node.widgets[index].value = displayValue(value, group.specs[index]);
    this.view.setDirty(true, true);
    this.changed();
  }

  selectGroup(key) {
    const node = this.graph._nodes.find(item => item.groupKey === key);
    if (node && !node.is_selected) this.view.selectNodes([node]);
  }

  readParams() {
    const params = {};
    if (this.graph._nodes.length !== this.groups.length + 1 || !this.root.graph) {
      throw new Error("Граф должен содержать одну стратегию и по одному узлу каждого раздела.");
    }
    const used = new Set();
    this.groups.forEach((group, index) => {
      const node = this.root.getInputNode(index);
      if (!node || node.type !== `sdk/${this.template.name}/${group.key}` || used.has(node.id)) {
        throw new Error(`Подключите узел «${group.label}» к стратегии.`);
      }
      used.add(node.id);
      for (const spec of group.specs) params[spec.name] = parseValue(node.properties[spec.name], spec);
    });
    return params;
  }

  resize() {
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    if (width && height) this.view.resize(width, height);
  }

  arrange() {
    this.resize();
    if (!this.canvas.width || !this.canvas.height || !this.graph._nodes.length) return;
    const right = Math.max(...this.graph._nodes.map(node => node.pos[0] + node.size[0])) + 30;
    const bottom = Math.max(...this.graph._nodes.map(node => node.pos[1] + node.size[1])) + 30;
    this.view.ds.scale = Math.min(1, this.container.clientWidth / right, this.container.clientHeight / bottom);
    this.view.ds.offset = [(this.container.clientWidth / this.view.ds.scale - right) / 2, 5];
    this.view.setDirty(true, true);
  }

  show(visible) {
    this.container.hidden = !visible;
    if (visible) { this.view.startRendering(); this.arrange(); }
    else this.view.stopRendering();
  }
}
