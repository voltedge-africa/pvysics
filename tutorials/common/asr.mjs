// Re-listen to the narration with the local Parakeet ASR model (sherpa-onnx, the same
// model family the Handy dictation app offers) to
//   1. get per-word timestamps for karaoke captions, and
//   2. measure how intelligible the synthetic voice is (word error rate vs the script).
//   node tutorials/common/asr.mjs --video tutorials/<name>
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const argOf = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
const VIDEO = resolve(argOf("--video", "."));   // the video folder: script.json in, build/ out
const BUILD = join(VIDEO, "build");
const require = createRequire(join(homedir(), "Workspace/paseo-tts/package.json"));
const sherpa = require("sherpa-onnx-node");
const D = join(homedir(), ".paseo/models/local-speech/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8");
const rec = new sherpa.OfflineRecognizer({
  featConfig: { sampleRate: 16000, featureDim: 80 },
  modelConfig: { transducer: { encoder: `${D}/encoder.int8.onnx`, decoder: `${D}/decoder.int8.onnx`, joiner: `${D}/joiner.int8.onnx` },
    tokens: `${D}/tokens.txt`, numThreads: 8, provider: "cpu", modelType: "nemo_transducer" },
});

const timeline = JSON.parse(readFileSync(join(BUILD, "timeline.json"), "utf8"));
const wav = sherpa.readWave(join(BUILD, "narration.wav"), false);

const norm = (w) => w.toLowerCase().replace(/[^a-z0-9']/g, "");
const NUM = { "20": "twenty", "22": "twenty two", "201": "two oh one", "100": "one hundred", "30": "thirty" };

function recognise(startS, endS) {
  const a = Math.max(0, Math.floor((startS - 0.15) * wav.sampleRate));
  const b = Math.min(wav.samples.length, Math.ceil((endS + 0.25) * wav.sampleRate));
  const stream = rec.createStream();
  stream.acceptWaveform({ sampleRate: wav.sampleRate, samples: wav.samples.slice(a, b) });
  rec.decode(stream);
  const r = rec.getResult(stream);
  // group tokens into words (a token starting with a space begins a word)
  const words = [];
  r.tokens.forEach((tok, i) => {
    const t = a / wav.sampleRate + r.timestamps[i];
    if (tok.startsWith(" ") || words.length === 0) words.push({ w: tok.trim(), start: t, end: t + (r.durations?.[i] ?? 0.1) });
    else { const w = words[words.length - 1]; w.w += tok; w.end = t + (r.durations?.[i] ?? 0.1); }
  });
  return { text: r.text, words };
}

// edit-distance alignment of ASR words to reference words
function align(ref, hyp) {
  const n = ref.length, m = hyp.length;
  const d = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = 0; i <= n; i++) d[i][0] = i;
  for (let j = 0; j <= m; j++) d[0][j] = j;
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++)
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (norm(ref[i - 1]) === norm(hyp[j - 1].w) ? 0 : 1));
  const map = new Array(n).fill(null);
  let i = n, j = m;
  while (i > 0 && j > 0) {
    const same = norm(ref[i - 1]) === norm(hyp[j - 1].w);
    if (d[i][j] === d[i - 1][j - 1] + (same ? 0 : 1)) { map[i - 1] = hyp[j - 1]; i--; j--; }
    else if (d[i][j] === d[i - 1][j] + 1) i--; else j--;
  }
  return { map, dist: d[n][m] };
}

let totalWords = 0, totalErr = 0;
const out = { scenes: [] };
for (const sc of timeline.scenes) {
  const so = { id: sc.id, beats: [] };
  let sErr = 0, sWords = 0;
  for (const b of sc.beats) {
    const { text, words } = recognise(b.start, b.end);
    const sayWords = b.say.split(/\s+/).filter(Boolean);
    // align on hyphen-split parts, then merge the parts back into the original words
    const parts = [], owner = [];
    sayWords.forEach((w, k) => w.split("-").filter(Boolean).forEach((p) => { parts.push(p); owner.push(k); }));
    const { map, dist } = align(parts, words);
    sErr += dist; sWords += parts.length;
    const pt = map.map((m) => (m ? { start: m.start, end: m.end } : null));
    for (let i = 0; i < pt.length; i++) if (!pt[i]) {
      let l = i - 1; while (l >= 0 && !pt[l]) l--;
      let r = i + 1; while (r < pt.length && !pt[r]) r++;
      const t0 = l >= 0 ? pt[l].end : b.start, t1 = r < pt.length ? pt[r].start : b.end;
      const span = r - l;
      pt[i] = { start: t0 + ((t1 - t0) * (i - l - 1)) / (span - 1 || 1), end: t0 + ((t1 - t0) * (i - l)) / (span - 1 || 1) };
    }
    const t = sayWords.map((_, k) => {
      const idx = owner.map((o, i) => (o === k ? i : -1)).filter((i) => i >= 0);
      return { start: pt[idx[0]].start, end: pt[idx[idx.length - 1]].end };
    });
    const say = sayWords;
    // caption words (may differ from spoken words, e.g. "PLC" vs "P L C")
    const cap = b.cap.split(/\s+/).filter(Boolean);
    const capT = cap.map((w, k) => {
      const idx = cap.length === say.length ? k : Math.min(say.length - 1, Math.round((k * (say.length - 1)) / Math.max(1, cap.length - 1)));
      return { w, start: t[idx].start, end: t[idx].end };
    });
    // `say` = the words as spoken (accurate times, used for cueing); `words` = caption words (timed by position when they differ)
    so.beats.push({ words: capT, say: say.map((w, k) => ({ w, start: t[k].start, end: t[k].end })), asr: text });
  }
  totalWords += sWords; totalErr += sErr;
  console.log(`${sc.id.padEnd(11)} WER ${(100 * sErr / sWords).toFixed(1)}%  (${sErr}/${sWords})`);
  out.scenes.push(so);
}
console.log(`overall WER ${(100 * totalErr / totalWords).toFixed(1)}%  (${totalErr}/${totalWords})`);
writeFileSync(join(BUILD, "words.json"), JSON.stringify(out));
