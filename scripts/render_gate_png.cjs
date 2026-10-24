// Rasterize synthesis-derived SVGs for the LaTeX paper. The SVGs remain the
// zoomable primary diagrams; this step only makes them usable with pdfLaTeX.
const path = require('path');
const sharp = require('../tools/netlistsvg/node_modules/sharp');

const root = path.resolve(__dirname, '..');
const plots = path.join(root, 'results', 'plots');

async function main() {
  for (const stem of ['sync_ram_2x1_gate', 'sync_ram_4x4_gate']) {
    await sharp(path.join(plots, `${stem}.svg`), { density: 288 })
      .flatten({ background: '#ffffff' })
      .png()
      .toFile(path.join(plots, `${stem}.png`));
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
