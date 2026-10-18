// Read the same semantic tokens for SVG and canvas; colours stay defined in CSS.
const styles = getComputedStyle(document.documentElement);
const token = name => styles.getPropertyValue(`--${name}`).trim();

export const theme = {
  canvas: token("bg-canvas"), panel: token("bg-panel"), surface: token("bg-surface"),
  sunken: token("bg-sunken"),
  text: token("text-primary"), secondary: token("text-secondary"),
  border: token("border-normal"), accent: token("accent"), info: token("info"),
  grid: token("canvas-grid"), font: token("font-ui"),
  blocks: Object.fromEntries(["root", "schedule", "signal", "restrictions", "sizing", "other"]
    .map(name => [name, token(`block-${name}`)])),
};
