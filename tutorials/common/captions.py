"""Karaoke captions: build an ASS subtitle file from the Parakeet word timings.

Each caption chunk (about one clause) is shown while it is spoken; the current word is lime,
spoken words are white and upcoming words are dimmed. libass burns it in during the final encode.
"""
import json
from pathlib import Path

BOX, WHITE, DIM, LIME = "2E3D17", "FFFFFF", "A8B8AE", "7AE8C9"   # BGR hex, as ASS wants it


def ts(t: float) -> str:
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def chunks(words, limit=84):
    out, cur, length = [], [], 0
    for w in words:
        cur.append(w)
        length += len(w["w"]) + 1
        end = w["w"].endswith((".", "?", ":", ";"))
        if length > limit or (end and length > 36):
            out.append(cur); cur, length = [], 0
    if cur:
        out.append(cur)
    return out


def build(path: Path, build_dir: Path):
    words = json.loads((build_dir / "words.json").read_text())
    events = []
    for sc in words["scenes"]:
        for beat in sc["beats"]:
            cs = chunks(beat["words"])
            for ci, c in enumerate(cs):
                for i, w in enumerate(c):
                    start = w["start"] if i or ci else w["start"] - 0.15
                    end = c[i + 1]["start"] if i + 1 < len(c) else c[-1]["end"] + 0.35
                    text = " ".join(
                        (f"{{\\c&H{WHITE}&}}" if j < i else f"{{\\c&H{LIME}&\\b1}}" if j == i else f"{{\\c&H{DIM}&\\b0}}") + x["w"].replace("{", "(").replace("}", ")")
                        for j, x in enumerate(c))
                    events.append((max(0.0, start), end, text))
    # a lingering last word must not overlap the next chunk (that would stack two caption lines)
    events.sort(key=lambda e: e[0])
    events = [(a, min(b, events[i + 1][0]) if i + 1 < len(events) else b, t) for i, (a, b, t) in enumerate(events)]
    events = [e for e in events if e[1] - e[0] > 0.02]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Liberation Sans,40,&H00{WHITE},&H00{WHITE},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,60,60,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # one clean dark band per caption chunk (layer 0), text on top (layer 1): no seams between highlight runs
    band = "{\\an7\\pos(0,962)\\p1\\bord0\\shad0\\1c&H" + BOX + "&\\1a&H14&}m 0 0 l 1920 0 l 1920 118 l 0 118"
    spans, body = [], ""
    for a, b, t in events:
        if spans and abs(spans[-1][1] - a) < 0.02:
            spans[-1][1] = b
        else:
            spans.append([a, b])
    body += "".join(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{band}\n" for a, b in spans)
    body += "".join(f"Dialogue: 1,{ts(a)},{ts(b)},Cap,,0,0,0,,{t}\n" for a, b, t in events)
    path.write_text(header + body)
    return len(events)


if __name__ == "__main__":
    import sys
    d = Path(sys.argv[1]).resolve() / "build"
    print(build(d / "captions.ass", d), "caption events")
