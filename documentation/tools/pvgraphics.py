"""Shared graphics for the PV digital twin docs: the SDM circuit schematic and typeset equations."""
import base64
import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
PNG = ROOT / "presentation" / "png"
TYPST = ROOT / "presentation" / "typst"
GREEN = "#137F36"

EQUATIONS = {
    "sdm": r"I = I_{ph} - I_0\left(e^{\frac{V + I R_s}{n N_s V_t}} - 1\right) - \frac{V + I R_s}{R_{sh}}",
    "iph": r"I_{ph} = \frac{G}{G_{ref}}\left[I_{sc} + K_i\,(T - T_{ref})\right]",
    "vt": r"V_t = \frac{k\,T}{q}",
    "kcl": r"I_{ph} = I_d + I_{sh} + I",
    "dev": r"\Delta = \frac{P_{meas} - P_{pred}}{P_{pred}} \times 100\%",
    "iph_vt": r"I_{ph} = \frac{G}{G_{ref}}\left[I_{sc} + K_i\,(T - T_{ref})\right], \qquad V_t = \frac{kT}{q}",
    "mae": r"\mathrm{MAE} = \frac{1}{N}\sum_{k=1}^{N}\left|P_{meas,k} - P_{pred,k}\right|",
    "rmse": r"\mathrm{RMSE} = \sqrt{\frac{1}{N}\sum_{k=1}^{N}\left(P_{meas,k} - P_{pred,k}\right)^2}",
    "mape": r"\mathrm{MAPE} = \frac{100\%}{N}\sum_{k=1}^{N}\left|\frac{P_{meas,k} - P_{pred,k}}{P_{meas,k}}\right|",
    "thr": r"\theta_{warn} = \mu + 2\sigma, \qquad \theta_{abn} = \mu + 3\sigma",
}


def equation_png(key: str, latex: str | None = None, fontsize: int = 30) -> Path:
    """Typeset an equation to a transparent PNG (Computer Modern math)."""
    out = PNG / f"eq_{key}.png"
    PNG.mkdir(parents=True, exist_ok=True)
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(1, 1))
    fig.text(0, 0, f"${latex or EQUATIONS[key]}$", fontsize=fontsize, color="black")
    fig.savefig(out, dpi=300, transparent=True, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out


def typst_png(name: str, ppi: int = 250, svg: bool = False) -> Path:
    """Compile presentation/typst/<name>.typ (Typst + CeTZ) to PNG, and optionally SVG, in presentation/png."""
    src, out = TYPST / f"{name}.typ", PNG / f"{name}.png"
    PNG.mkdir(parents=True, exist_ok=True)
    targets = [(out, ["--ppi", str(ppi)])] + ([(out.with_suffix(".svg"), [])] if svg else [])
    for target, extra in targets:
        if not target.exists() or target.stat().st_mtime < max(src.stat().st_mtime, (ROOT / "tools/typ/lib.typ").stat().st_mtime):
            subprocess.run(["typst", "compile", "--root", str(ROOT), *extra, str(src), str(target)], check=True)
    return out


def circuit_png() -> Path:
    """Single Diode Model equivalent circuit schematic (Typst + CeTZ), as PNG and SVG."""
    return typst_png("circuit_sdm", ppi=300, svg=True)


def embed_images(svg: str, mapping: dict[str, Path]) -> str:
    """Replace Wireloom image placeholders whose label contains a key with the real picture."""
    pattern = re.compile(
        r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="#fafbfc"[^>]*stroke-dasharray="4 3"[^>]*/>'
        r'<line [^>]*/><line [^>]*/><text [^>]*>([^<]*)</text>')

    def repl(m):
        x, y, w, h, label = m.groups()
        for key, path in mapping.items():
            if key in label:
                data = base64.b64encode(Path(path).read_bytes()).decode()
                return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#8a8a8a" stroke-width="0.5" rx="2" />'
                        f'<image x="{float(x) + 4}" y="{float(y) + 3}" width="{float(w) - 8}" height="{float(h) - 6}" '
                        f'preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{data}" />')
        return m.group(0)

    return pattern.sub(repl, svg)
