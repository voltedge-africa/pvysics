#!/usr/bin/env bash
# Build one video end to end.   bash tutorials/build.sh <name> [--draft]      (run from the repository root)
#   <name>   a folder under tutorials/, e.g. ch01-introduction
#   --draft  render at 480p15 (fast, for checking layout and timing)
set -euo pipefail
name="${1:?usage: build.sh <name> [--draft]}"
dir="tutorials/$name"
quality=h; [[ "${2:-}" == "--draft" ]] && quality=l
[[ -d "$dir" ]] || { echo "no such video: $dir"; exit 1; }
python3 tutorials/check.py "$dir"                                  # script and scene wiring
node tutorials/common/tts.mjs --video "$dir" --jobs 3              # narration (cached per sentence)
node tutorials/common/asr.mjs --video "$dir"                       # word timings
python3 tutorials/check.py "$dir" --cues                           # every n.cue(...) word really is spoken
tutorials/.venv/bin/python tutorials/common/render.py "$dir" --quality "$quality"
mkdir -p tutorials/out
if [[ $quality == h ]]; then cp "$dir/build/tutorial.mp4" "tutorials/out/$name.mp4"; echo "-> tutorials/out/$name.mp4"
else cp "$dir/build/tutorial_480p15.mp4" "tutorials/out/$name-draft.mp4"; echo "-> tutorials/out/$name-draft.mp4"; fi
