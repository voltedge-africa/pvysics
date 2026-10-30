// Narration: synthesise every beat of script.json with the local Kokoro voice
// (sherpa-onnx, same engine and model files as the paseo-tts plugin), then lay the
// clips on one timeline.   node tutorials/common/tts.mjs --video tutorials/<name> [--jobs 3] [--speed 1.0]
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { execFileSync, fork } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const argOf = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
const VIDEO = resolve(argOf("--video", "."));   // the video folder: script.json in, build/ out
const BUILD = join(VIDEO, "build");
const AUDIO = join(BUILD, "audio");
const MODEL_DIR = join(homedir(), ".paseo/models/paseo-tts/kokoro-int8-v1_0");
const PASEO_PLUGIN = join(homedir(), "Workspace/paseo-tts/package.json");
// Speaker ids of the English voices in kokoro-multi-lang-v1_0 (as in paseo-tts/server/config.ts).
const VOICES = ["af_alloy","af_aoede","af_bella","af_heart","af_jessica","af_kore","af_nicole","af_nova",
  "af_river","af_sarah","af_sky","am_adam","am_echo","am_eric","am_fenrir","am_liam","am_michael",
  "am_onyx","am_puck","am_santa","bf_alice","bf_emma","bf_isabella","bf_lily","bm_daniel","bm_fable",
  "bm_george","bm_lewis"];

function wavBuffer(samples, rate) {
  const buf = Buffer.alloc(44 + samples.length * 2);
  buf.write("RIFF", 0); buf.writeUInt32LE(36 + samples.length * 2, 4); buf.write("WAVEfmt ", 8);
  buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(rate, 24); buf.writeUInt32LE(rate * 2, 28); buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34); buf.write("data", 36); buf.writeUInt32LE(samples.length * 2, 40);
  for (let i = 0; i < samples.length; i++)
    buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767), 44 + i * 2);
  return buf;
}
function readWav(file) {
  const b = readFileSync(file);
  const rate = b.readUInt32LE(24);
  const n = (b.length - 44) / 2;
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = b.readInt16LE(44 + i * 2) / 32768;
  return { rate, samples: out };
}

// ------------------------------------------------------------------ worker
if (process.argv.includes("--worker")) {
  const require = createRequire(PASEO_PLUGIN);
  const sherpa = require("sherpa-onnx-node");
  const threads = Number(process.env.TTS_THREADS ?? 4);
  const tts = new sherpa.OfflineTts({
    model: { kokoro: {
      model: `${MODEL_DIR}/model.int8.onnx`, voices: `${MODEL_DIR}/voices.bin`, tokens: `${MODEL_DIR}/tokens.txt`,
      lexicon: `${MODEL_DIR}/lexicon-us-en.txt,${MODEL_DIR}/lexicon-zh.txt`,
      dataDir: `${MODEL_DIR}/espeak-ng-data`, dictDir: `${MODEL_DIR}/dict` },
      numThreads: threads, provider: "cpu" },
    maxNumSentences: 1,
  });
  process.on("message", (job) => {
    const a = tts.generate({ text: job.text, sid: job.sid, speed: job.speed });
    writeFileSync(job.out, wavBuffer(Float32Array.from(a.samples), a.sampleRate));
    process.send({ id: job.id, seconds: a.samples.length / a.sampleRate });
  });
  process.send({ ready: true });
} else {
  // ---------------------------------------------------------------- main
  const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > 0 ? process.argv[i + 1] : dflt; };
  const JOBS = Number(arg("--jobs", 3));
  const script = JSON.parse(readFileSync(join(VIDEO, "script.json"), "utf8"));
  // speaking speed (1.0 = normal; worked-example videos use about 0.8): --speed overrides script.json "speed"
  const SPEED = Number(arg("--speed", script.speed ?? 1.0));
  // Engine: Kokoro (default, sherpa-onnx, Apache-2.0 licence) or Breeze (local Breeze-TTS-2.cpp build, research and
  // non-commercial licence): --engine breeze, or "engine": "breeze" in script.json. The Breeze voice is a saved voice
  // (see tutorials/voice/README.md) so every beat has the same narrator.
  const ENGINE = arg("--engine", script.engine ?? "kokoro");
  const BREEZE_DIR = process.env.BREEZE_DIR ?? join(homedir(), "Workspace/breeze-cpp");
  const BREEZE_VOICES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "voice", "voices");
  const BREEZE_SEED = Number(arg("--seed", script.breeze_seed ?? 42));
  const voice = ENGINE === "breeze" ? (script.breeze_voice ?? "zwane-tutor") : (script.voice ?? "af_heart");
  const sid = VOICES.indexOf(voice);
  if (ENGINE === "kokoro" && sid < 0) throw new Error(`unknown voice ${voice}`);
  mkdirSync(AUDIO, { recursive: true });

  // list beats and which need synthesis
  const clips = [];
  script.scenes.forEach((sc, si) => sc.beats.forEach((b, bi) => {
    const key = createHash("sha1").update(ENGINE === "breeze" ? `breeze|${voice}|${BREEZE_SEED}|${b.say}` : `${voice}|${SPEED}|${b.say}`).digest("hex").slice(0, 12);
    clips.push({ si, bi, text: b.say, file: join(AUDIO, `${sc.id}_${String(bi).padStart(2, "0")}_${key}.wav`) });
  }));
  const todo = clips.filter((c) => !existsSync(c.file));
  console.log(`${clips.length} beats, ${todo.length} to synthesise with ${ENGINE} voice ${voice}${ENGINE === "kokoro" ? ` (sid ${sid}), ${JOBS} workers` : ""}`);

  if (todo.length && ENGINE === "breeze") {
    // one clip at a time: the GPU holds the model, and each call loads it (a few seconds)
    const cli = join(BREEZE_DIR, "Breeze-TTS-2.cpp/build/breeze-cli"), model = join(BREEZE_DIR, "models/breeze-tts-2-q8_0.gguf");
    for (const c of todo) {
      const t0 = Date.now();
      execFileSync(cli, [model, "--text", c.text, "--voice", voice, "--voices-dir", BREEZE_VOICES, "--seed", String(BREEZE_SEED), "--output", c.file],
        { stdio: ["ignore", "ignore", "inherit"] });
      console.log(`  ${c.file.split("/").pop()}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    }
  } else if (todo.length) {
    const workers = [];
    await Promise.all(Array.from({ length: Math.min(JOBS, todo.length) }, () => new Promise((resolve) => {
      const w = fork(fileURLToPath(import.meta.url), ["--worker"], { env: { ...process.env, TTS_THREADS: String(Math.max(2, Math.floor(12 / JOBS))) }, stdio: ["inherit", "ignore", "inherit", "ipc"] });
      w.once("message", () => { workers.push(w); resolve(); });
    })));
    let next = 0, done = 0;
    await new Promise((resolve) => {
      const feed = (w) => {
        if (next >= todo.length) { w.kill(); if (++done === workers.length) resolve(); return; }
        const c = todo[next++];
        w.once("message", (m) => { console.log(`  ${c.file.split("/").pop()}  ${m.seconds.toFixed(1)}s`); feed(w); });
        w.send({ id: next, text: c.text, sid, speed: SPEED, out: c.file });
      };
      workers.forEach(feed);
    });
  }

  // ------------------------------------------------------------ timeline
  const RATE = 24000, GAP = script.gap ?? 0.32, LEAD = 0.5, SCENE_GAP = 0.9, TAIL = 0.7;
  let cursor = 0.6;
  const timeline = { rate: RATE, voice, scenes: [] };
  const pieces = [];
  script.scenes.forEach((sc, si) => {
    const scene = { id: sc.id, title: sc.title, mode: sc.mode, start: cursor, beats: [] };
    cursor += LEAD;
    sc.beats.forEach((b, bi) => {
      const clip = clips.find((c) => c.si === si && c.bi === bi);
      const wav = readWav(clip.file);
      const start = cursor, dur = wav.samples.length / wav.rate;
      pieces.push({ start, samples: wav.samples });
      scene.beats.push({ start, end: start + dur, say: b.say, cap: b.cap ?? b.say, after: b.after ?? 0 });
      cursor = start + dur + GAP + (b.after ?? 0);
    });
    scene.end = cursor + TAIL;
    cursor = scene.end + SCENE_GAP - TAIL;
    timeline.scenes.push(scene);
  });
  timeline.total = cursor;
  const total = Math.ceil(timeline.total * RATE);
  const mix = new Float32Array(total);
  for (const p of pieces) mix.set(p.samples, Math.round(p.start * RATE));
  writeFileSync(join(BUILD, "narration.wav"), wavBuffer(mix, RATE));
  writeFileSync(join(BUILD, "timeline.json"), JSON.stringify(timeline, null, 1));
  console.log(`narration ${timeline.total.toFixed(1)}s -> build/narration.wav, build/timeline.json`);
}
