# Narrator voice for the Breeze engine

The tutorials are narrated by Kokoro by default (`af_heart`, Apache-2.0 licence). They can instead use **Breeze-TTS-2**, run locally through
the C++/GGUF build `Breeze-TTS-2.cpp` (default location `~/Workspace/breeze-cpp`, override with `BREEZE_DIR`).

**Licence: read this before sharing anything made with Breeze.** The Breeze-TTS-2 weights, and audio generated from them on your own
machine, are under the BreezeBlue Research and Non-Commercial License (the inference code is Apache-2.0). Use the Breeze narration for
study, research and internal material. Do not put it in a commercial or sponsor-facing product without checking the licence. The Kokoro
set is the one to share freely. The reference clip and saved voice in this folder are outputs of the model, so they are git-ignored.

## One narrator, every beat

A voice described in words can come out a little different on every clip, so the narrator is designed once and then reused:

    B=~/Workspace/breeze-cpp
    REF="Welcome. In this series we will build the twin of a solar panel from first principles, and then use it to find out when a real panel is not making the power it should."
    $B/Breeze-TTS-2.cpp/build/breeze-cli $B/models/breeze-tts-2-q8_0.gguf --text "$REF" \
      --instruction "A warm, clear, friendly woman, a patient tutor, speaking English at a steady, unhurried pace with gentle enthusiasm." \
      --cfg-scale 4 --seed 42 --output tutorials/voice/ref.wav
    $B/Breeze-TTS-2.cpp/build/breeze-cli $B/models/breeze-tts-2-q8_0.gguf --ref-audio tutorials/voice/ref.wav --ref-text "$REF" \
      --save-voice zwane-tutor --voices-dir tutorials/voice/voices

`ref.txt` holds the exact transcript of `ref.wav` (a clone needs it exactly). Every beat is then synthesised with `--voice zwane-tutor
--seed 42`.

## Using it

    node tutorials/common/tts.mjs --video tutorials/t01-the-big-idea --engine breeze     # narration (cached per sentence and engine)
    node tutorials/common/asr.mjs --video tutorials/t01-the-big-idea                    # word timings
    # build.sh passes no engine flag: put  "engine": "breeze"  in the video's script.json (series.py --engine breeze does that for every video)

Clips are cached under the video's `build/audio` with a key that includes the engine, so the Kokoro and Breeze clips never overwrite each
other. Narration changes length with the voice, so re-render the video after switching (cues follow the spoken words).

Measured on this machine (Quadro RTX 4000, Vulkan): about 12 s to synthesise a 10 s beat including the model load; word error 5.6% through
the Parakeet round trip on a test of three beats; integrated loudness within 0.5 LU of the Kokoro narration. The model has no speed control.
