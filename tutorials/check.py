#!/usr/bin/env python3
"""Lint a video before (and after) the expensive stages.

  python3 tutorials/check.py tutorials/<name>           # script + scene wiring (before tts)
  python3 tutorials/check.py tutorials/<name> --cues    # also verify every n.cue(beat, "word") against the ASR words (after asr)

Errors stop the build; warnings are advice (mostly about how the voice will read the text).
"""
import json, re, sys
from pathlib import Path

video = Path(sys.argv[1]).resolve()
script = json.loads((video / "script.json").read_text())
files = {f.name: f.read_text() for f in sorted(video.glob("scenes*.py"))}   # a video may split its scenes over scenes*.py
code = "\n".join(files.values())
errors, warnings = [], []

classes = dict(re.findall(r"^class (\w+)\(Narrated\):\n\s+scene_id = \"(\w+)\"", code, re.M))   # class -> scene id
ids = [s["id"] for s in script["scenes"]]
if len(set(ids)) != len(ids):
    errors.append(f"duplicate scene ids: {sorted({i for i in ids if ids.count(i) > 1})}")
for sc in script["scenes"]:
    cls = sc.get("class")
    if not cls:
        errors.append(f"scene '{sc['id']}' has no \"class\" in script.json")
    elif cls not in classes:
        errors.append(f"scene '{sc['id']}': class {cls} not found in scenes.py (needs `class {cls}(Narrated)` with scene_id)")
    elif classes[cls] != sc["id"]:
        errors.append(f"class {cls} has scene_id '{classes[cls]}' but script.json says '{sc['id']}'")
    if not sc.get("title"):
        warnings.append(f"scene '{sc['id']}' has no title (shown in the header)")
    if not sc.get("beats"):
        errors.append(f"scene '{sc['id']}' has no beats")
for cls in classes:
    if cls not in {s.get("class") for s in script["scenes"]}:
        warnings.append(f"class {cls} in scenes.py is not used by script.json")

for sc in script["scenes"]:
    for i, b in enumerate(sc.get("beats", [])):
        say, where = b.get("say", ""), f"{sc['id']} beat {i}"
        if not say.strip():
            errors.append(f"{where}: empty \"say\"")
            continue
        n = len(say.split())
        if n > 45:
            warnings.append(f"{where}: {n} words (about {n / 2.6:.0f} s); split long beats so visuals can follow")
        if re.search(r"\d", say):
            warnings.append(f"{where}: digits in speech; write numbers as words and put the symbols in \"cap\"")
        if re.search(r"[%&/=<>^_]", say):
            warnings.append(f"{where}: symbols ({''.join(sorted(set(re.findall(r'[%&/=<>^_]', say))))}) are read unpredictably; spell them out")
        for acro in re.findall(r"\b[A-Z]{2,5}\b", say):
            if acro not in ("OK", "TV"):
                warnings.append(f"{where}: acronym {acro}: if it is mispronounced, spell it \"{' '.join(acro)}\" in \"say\" and keep {acro} in \"cap\"")

if "--cues" in sys.argv:
    words = json.loads((video / "build" / "words.json").read_text())
    by_id = {sc["id"]: words["scenes"][i] for i, sc in enumerate(json.loads((video / "build" / "timeline.json").read_text())["scenes"])}
    norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())
    cls_of, current, checked = {}, None, 0
    for fname, ln, line in [(f, i, l) for f, c in files.items() for i, l in enumerate(c.split("\n"), 1)]:
        m = re.match(r"^class (\w+)\(Narrated\)", line)
        if m:
            current = classes.get(m.group(1))
        for kind, beat, word in re.findall(r"\bn\.(cue|start|end)\(\s*(\d+)(?:\s*,\s*\"([^\"]+)\")?", line):
            if current is None or current not in by_id:
                continue
            beats = by_id[current]["beats"]
            if int(beat) >= len(beats):
                errors.append(f"{fname}:{ln}: {current} has no beat {beat} (it has {len(beats)})")
            elif kind == "cue" and word:
                checked += 1
                spoken = {norm(w["w"]) for w in beats[int(beat)]["words"] + beats[int(beat)].get("say", [])}
                if norm(word) not in spoken:
                    warnings.append(f"{fname}:{ln}: cue word \"{word}\" is not in {current} beat {beat}; it will fall back to the beat start")
    print(f"checked {checked} literal cue words")

for w in warnings:
    print("warning:", w)
for e in errors:
    print("ERROR:  ", e)
print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
sys.exit(1 if errors else 0)
