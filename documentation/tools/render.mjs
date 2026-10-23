// Usage: node render.mjs <in.wireloom> <out.svg> [theme]
import { readFileSync, writeFileSync } from 'node:fs';
import wireloom, { WireloomError } from 'wireloom';

const [, , src, out, theme = 'default'] = process.argv;
try {
  const { svg } = await wireloom.render('wf', readFileSync(src, 'utf8'), { theme });
  writeFileSync(out, svg);
} catch (err) {
  if (err instanceof WireloomError) {
    console.error(`${src}: line ${err.line}, col ${err.column}: ${err.message}`);
    process.exit(2);
  }
  throw err;
}
