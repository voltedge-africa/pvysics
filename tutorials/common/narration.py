"""Narration timing for a video, read from the files produced by tts.mjs and asr.mjs:

  <video>/build/timeline.json   scene and beat start/end times (seconds, whole-video clock)
  <video>/build/words.json      per-word timestamps from the Parakeet ASR pass

Scenes use it as  n = self.n ;  n.start(beat), n.end(beat), n.cue(beat, "word").
Has no Manim dependency:  python3 tutorials/common/narration.py <video-dir>
"""
import json
import re
import sys
from pathlib import Path


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


class Narration:
    """Timing of one scene, in seconds since the scene started."""

    def __init__(self, scene_id: str, build: Path):
        tl = json.loads((build / "timeline.json").read_text())
        words = json.loads((build / "words.json").read_text())
        self.label = json.loads((build.parent / "script.json").read_text()).get("label", "").upper()   # small header line
        ids = [s["id"] for s in tl["scenes"]]
        self.index = ids.index(scene_id)
        sc = tl["scenes"][self.index]
        self.id, self.title = scene_id, sc["title"]
        # the first scene also owns the lead-in silence; every scene owns the gap after it,
        # so the rendered clips butt together and stay in sync with the narration track
        self.origin = 0.0 if self.index == 0 else sc["start"]
        nxt = tl["scenes"][self.index + 1]["start"] if self.index + 1 < len(ids) else tl["total"]
        self.duration = nxt - self.origin
        self.total = tl["total"]
        self.beats = [(b["start"] - self.origin, b["end"] - self.origin) for b in sc["beats"]]
        self.words = [[(w["w"], w["start"] - self.origin, w["end"] - self.origin) for w in b["words"]]
                      for b in words["scenes"][self.index]["beats"]]
        # the words as spoken (cue words refer to these first, then to the caption words); older builds have none
        self.spoken = [[(w["w"], w["start"] - self.origin, w["end"] - self.origin) for w in b.get("say", [])]
                       for b in words["scenes"][self.index]["beats"]]

    def start(self, beat: int) -> float:
        return self.beats[beat][0]

    def end(self, beat: int) -> float:
        return self.beats[beat][1]

    def cue(self, beat: int, word: str, nth: int = 0) -> float:
        """Scene time at which `word` is spoken in `beat` (as in the `say` text); falls back to the beat start (run check.py --cues)."""
        for source in (self.spoken[beat], self.words[beat]):
            hits = [s for (w, s, _e) in source if _norm(w) == _norm(word)]
            if len(hits) > nth:
                return hits[nth]
        return self.start(beat)


if __name__ == "__main__":
    build = Path(sys.argv[1]).resolve() / "build"
    tl = json.loads((build / "timeline.json").read_text())
    for sc in tl["scenes"]:
        n = Narration(sc["id"], build)
        print(f"{sc['id']:12s} {n.duration:6.1f} s   {len(n.beats)} beats")
