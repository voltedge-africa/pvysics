"""Render wireframes/src/*.wireloom to SVG and assemble wireframes/WIREFRAMES.md.

Usage: python3 tools/build_wireframes.py
Needs node and `npm install` run once in tools/.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pvgraphics

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "wireframes" / "src"
SVG = ROOT / "wireframes" / "svg"
OUT = ROOT / "wireframes" / "WIREFRAMES.md"
RENDER = ROOT / "tools" / "render.mjs"

SCREENS = [
    ("01-hmi-main", "HMI: normal operation",
     "Plant and twin side by side. The deviation panel sits between the two, "
     "and the operator controls and fault buttons run along the bottom."),
    ("02-hmi-fault-active", "HMI: fault injected",
     "Same screen after partial shading is injected. The banner, deviation panel and "
     "alarm list all react."),
    ("05-hmi-model", "HMI: model view",
     "The Single Diode Model on screen: equivalent circuit, equations, editable parameters, "
     "live inputs and the resulting curve."),
    ("06-hmi-setup", "HMI: setup",
     "Choose or upload the input profile, set the plant and twin parameters, "
     "the plant-vs-twin mismatch, sensor noise and thresholds, then apply."),
    ("07-hmi-upload-dialog", "HMI: upload dialog",
     "Upload a profile CSV, map columns and see validation checks before use."),
    ("03-dashboard-overview", "Dashboard: overview",
     "Read-only KPIs and trends for a selected run."),
    ("04-dashboard-validation", "Dashboard: validation",
     "MAE, RMSE and MAPE for the healthy case, plus fault-detection results."),
]

NAV = """```mermaid
flowchart LR
    subgraph HMI["HMI (interactive)"]
        H1["Normal operation"] -- "inject fault" --> H2["Fault active + alarm list"]
        H1 <--> HM["Model view"]
        H1 <--> HS["Setup"]
        H2 -- "clear all" --> H1
    end
    subgraph DASH["Dashboard (read-only)"]
        D1["Overview"] <--> D2["Validation"] <--> D3["Events"]
    end
    BUS{{"Data bus"}}
    HMI --> BUS --> DASH
    H2 -. "alarm logged" .-> D3
```"""

MODEL = r"""![Single Diode Model equivalent circuit](svg/circuit_sdm.svg)

$$I = I_{ph} - I_0\left(e^{\frac{V + I R_s}{n N_s V_t}} - 1\right) - \frac{V + I R_s}{R_{sh}}$$

$$I_{ph} = \frac{G}{G_{ref}}\left[I_{sc} + K_i\,(T - T_{ref})\right], \qquad V_t = \frac{kT}{q}$$

```mermaid
flowchart LR
    G["$$G$$"] --> IPH["$$I_{ph}$$"]
    T["$$T$$"] --> IPH
    T --> VT["$$V_t$$"]
    T --> I0["$$I_0(T)$$"]
    IPH --> SOLVE["Solve SDM for $$I$$"]
    VT --> SOLVE
    I0 --> SOLVE
    PAR["$$R_s,\ R_{sh},\ n,\ N_s$$"] --> SOLVE
    SOLVE --> CURVE["I-V and P-V curve"]
    CURVE --> PPRED["$$P_{pred}$$"]
    PM["$$P_{meas} = V \cdot I$$"] --> DEV["$$\Delta = \frac{P_{meas} - P_{pred}}{P_{pred}} \times 100\%$$"]
    PPRED --> DEV
    DEV --> STATE["Normal / Warning / Abnormal"]
```"""


SETUP = """```mermaid
flowchart LR
    subgraph S["Setup screen"]
        ST["Site<br/>lat, lon, tilt, azimuth"]
        PR["Input profile<br/>preset / CSV / NASA POWER / synthetic"]
        ST --> PR
        PP["Plant parameters<br/>datasheet JSON or generic"]
        MM["Plant vs twin mismatch<br/>Rs, Rsh, temp-coeff offsets"]
        SN["Sensor model<br/>noise + quantisation"]
        TH["Thresholds<br/>manual or derived"]
    end
    V{"Validate setup"}
    A["Apply and start"]
    ST --> V
    PR --> V
    PP --> V
    MM --> V
    SN --> V
    TH --> V
    V -- "ok" --> A
    V -- "errors" --> S
    A --> ENG["Simulation engine"]
    A --> LOG[("run_001 config saved with CSV")]
```

Profile CSV: `timestamp, G, T` (G in W/m2, T in C). Datasheet JSON:
`{"Isc", "Voc", "Impp", "Vmpp", "Ki", "Kv", "Ns"}`.
"""


LAYOUT = """```mermaid
flowchart TB
    subgraph HMI_L["HMI layout"]
        direction TB
        a1["Header: title | profile + clock | state banner"]
        subgraph a2["Process view"]
            direction LR
            p["Plant (measured)"] ~~~ t["Digital twin (predicted)"] ~~~ d["Power deviation"]
        end
        a3["Operator panel: controls | fault injection | alarms"]
        a4["Footer: bus status | log file"]
        a1 --> a2 --> a3 --> a4
    end
    subgraph DASH_L["Dashboard layout"]
        direction TB
        b1["Header: title | tabs | run selector"]
        b2["KPI row"]
        b3["Chart grid: power | deviation | G and T | I-V and P-V"]
        b4["State time + latest events"]
        b1 --> b2 --> b3 --> b4
    end
```"""


def render(name: str) -> None:
    result = subprocess.run(
        ["node", str(RENDER), str(SRC / f"{name}.wireloom"), str(SVG / f"{name}.svg")],
        capture_output=True, text=True,
    )
    if result.returncode:
        sys.exit(result.stderr.strip())
    if name == "05-hmi-model":          # swap placeholders for the real schematic and typeset math
        svg = SVG / f"{name}.svg"
        svg.write_text(pvgraphics.embed_images(svg.read_text(), {
            "Circuit": pvgraphics.circuit_png(),
            "Typeset SDM": pvgraphics.equation_png("sdm"),
            "Typeset Iph": pvgraphics.equation_png("iph"),
            "Typeset Vt": pvgraphics.equation_png("vt"),
        }))
        shutil.copy(pvgraphics.PNG / "circuit_sdm.svg", SVG / "circuit_sdm.svg")


def main() -> None:
    SVG.mkdir(exist_ok=True)
    parts = [
        "# PV Digital Twin: UI wireframes\n",
        "Two separate UIs share one data bus. The **HMI** is the interactive demo "
        "of the plant and twin. The **dashboard** is read-only analytics.\n",
        "## Navigation and data flow\n", NAV + "\n",
        "## Setup and configuration flow\n", SETUP + "\n",
        "## Layout blocks\n", LAYOUT + "\n",
        "## The model\n", "The twin is the Single Diode Model. The HMI model view shows this "
        "circuit, its equations and its live parameters.\n", MODEL + "\n",
    ]
    for name, title, blurb in SCREENS:
        render(name)
        source = (SRC / f"{name}.wireloom").read_text().rstrip()
        parts += [
            f"## {title}\n", blurb + "\n",
            f"![{title}](svg/{name}.svg)\n",
            "<details><summary>Wireloom source</summary>\n",
            f"```wireloom\n{source}\n```\n",
            "</details>\n",
        ]
    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
