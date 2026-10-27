// The shared look of the PV Digital Twin manuals (Typst): colours, helpers and the `manual` template.
//
// A manual starts with
//
//   #import "manual-style.typ": *
//   #show: manual.with(version: "0.1.1", doc-title: "...", subtitle: [User Manual], tagline: [...])
//
// and then holds its chapters. Build from the repository root so the app icon under src/ and the screenshots under
// docs/ are inside the project root, and point Typst at the bundled Barlow fonts:
//
//   typst compile --root . --font-path src/pvysics/gui/fonts docs/<manual>.typ docs/<manual>.pdf

// The department's colours, as in the app (src/pvysics/gui/palette.py and assets/icon.svg).
#let green = rgb("#137f36")
#let green-deep = rgb("#0b5a25")
#let green-night = rgb("#0a3d1a")
#let green-tint = rgb("#e6f2ea")
#let sun = rgb("#ffca28")
#let ink = rgb("#1e1e1e")
#let muted = rgb("#5f5f5f")
#let rule = rgb("#d5d9dd")
#let paper = rgb("#f3f4f6")

#let icon = "../src/pvysics/gui/assets/icon.svg"
#let shots = "screenshots/"

#let key(k) = box(
  fill: white, stroke: 0.7pt + muted, radius: 3pt, inset: (x: 4pt), outset: (y: 3pt),
  text(size: 0.9em, weight: "medium", k),
)

// A screenshot, drawn at `w` of the text width. The frame keeps pale screenshots from bleeding into the page.
#let shot(file, caption, w: 100%) = figure(
  block(width: 100%, align(left, block(
    width: w, stroke: 0.6pt + rule, radius: 2pt, clip: true, image(shots + file, width: 100%),
  ))),
  caption: caption,
  kind: image,
  gap: 0.8em,
)

// A short "how-to" heading for the recipes.
#let recipe(title) = block(above: 1.4em, below: 0.6em, sticky: true, text(weight: "semibold", fill: green-deep, size: 11.5pt, title))

// The whole document: cover, contents, list of figures, then the body with chapter pages numbered from 1.
#let manual(version: "", doc-title: "", subtitle: [], tagline: [], body) = {
set document(title: doc-title, author: "pvysics")
set text(font: "Barlow", size: 10.5pt, fill: ink, lang: "en")
set par(leading: 0.62em, spacing: 1em, justify: false)

show raw: set text(font: ("DejaVu Sans Mono", "Liberation Mono"), size: 0.88em)
show raw.where(block: false): it => box(
  fill: paper, stroke: 0.5pt + rule, radius: 2pt, inset: (x: 3pt), outset: (y: 3pt), it,
)
show raw.where(block: true): it => block(
  width: 100%, fill: paper, stroke: (left: 2.5pt + green), inset: (x: 12pt, y: 9pt), radius: (right: 3pt), it,
)
show strong: set text(weight: "semibold")
show link: set text(fill: green)

// Headings -----------------------------------------------------------------------------------------------
set heading(numbering: "1.1")
show heading: set text(fill: green-deep, weight: "semibold")
show heading.where(level: 1): it => {
  v(1.6em, weak: true)
  block(width: 100%, below: 1em, {
    if it.numbering != none {
      text(size: 11pt, weight: "medium", fill: green, upper[Chapter #counter(heading).display("1")])
      v(-0.2em)
    }
    text(size: 24pt, it.body)
    v(-0.1em)
    line(length: 100%, stroke: 1.6pt + sun)
  })
}
show heading.where(level: 2): it => block(above: 1.7em, below: 0.9em, {
  text(size: 14pt, [#counter(heading).display() #h(0.4em) #it.body])
})
show heading.where(level: 1): set text(size: 24pt)

// Figures: screenshots in a thin frame, caption "Figure N. ..." --------------------------------------------
set figure(supplement: "Figure")
show figure.caption: it => block(width: 100%, {
  set text(size: 9pt, fill: muted)
  set align(left)
  text(weight: "semibold", fill: green-deep)[#it.supplement #context it.counter.display(it.numbering).]
  [ ]
  it.body
})
show figure: set block(above: 1.3em, below: 1.5em)
show figure: it => block(breakable: false, width: 100%, it)

// Tables -------------------------------------------------------------------------------------------------
set table(
  stroke: (x, y) => (bottom: if y == 0 { 1.2pt + green } else { 0.5pt + rule }),
  inset: (x: 8pt, y: 6pt),
  fill: (x, y) => if y == 0 { green-tint },
  align: left + horizon,
)
show table: set block(above: 1.1em, below: 1.3em)
show table.cell.where(y: 0): set text(weight: "semibold", fill: green-deep)

// Lists --------------------------------------------------------------------------------------------------
set list(marker: text(fill: green)[•], indent: 0.4em, body-indent: 0.6em)
set enum(numbering: n => text(fill: green, weight: "semibold")[#n.], indent: 0.4em, body-indent: 0.6em)

// ===================================================================================================== Cover
set page(paper: "a4", margin: 0pt)
page(fill: gradient.linear(green-deep, green-night, angle: 55deg), {
  // The faint I-V and P-V curves from the splash screen.
  let pw = 210mm
  let ph = 297mm
  place(top + left, curve(
    stroke: (paint: white.transparentize(90%), thickness: 3pt, cap: "round"),
    curve.move((0pt, ph * 0.64)),
    curve.line((pw * 0.52, ph * 0.64)),
    curve.cubic((pw * 0.74, ph * 0.64), (pw * 0.84, ph * 0.70), (pw * 0.92, ph)),
  ))
  place(top + left, curve(
    stroke: (paint: white.transparentize(90%), thickness: 3pt, cap: "round"),
    curve.move((0pt, ph)),
    curve.cubic((pw * 0.22, ph * 0.78), (pw * 0.52, ph * 0.48), (pw * 0.72, ph * 0.48)),
    curve.cubic((pw * 0.88, ph * 0.48), (pw * 0.94, ph * 0.74), (pw, ph)),
  ))

  place(top + left, dx: 24mm, dy: 38mm, image(icon, width: 44mm))
  place(top + left, dx: 24mm, dy: 104mm, {
    set text(fill: white)
    text(size: 15pt, weight: "medium", fill: sun, tracking: 0.12em, upper[pvysics])
    v(0.3em)
    text(size: 50pt, weight: "bold", [PV Digital\ Twin])
    v(0.1em)
    block(width: 18mm, line(length: 100%, stroke: 3pt + sun))
    v(0.5em)
    text(size: 26pt, weight: "regular", subtitle)
  })
  place(top + left, dx: 24mm, dy: 205mm, block(width: 120mm, {
    set text(fill: white.transparentize(15%), size: 12pt)
    tagline
  }))
  place(bottom + left, dx: 24mm, dy: -22mm, {
    set text(fill: white)
    text(weight: "semibold", size: 11pt)[Version #version]
    h(1em)
    text(fill: sun, [·])
    h(1em)
    text(size: 11pt, fill: white.transparentize(15%))[A physics-informed digital twin for PV state estimation]
  })
})

// ========================================================================================== Front matter
set page(
  margin: (top: 26mm, bottom: 24mm, x: 22mm),
  fill: white,
  numbering: "i",
  header: context {
    let pg = here().page()
    let chapters = query(heading.where(level: 1).before(here()))
    set text(size: 9pt, fill: muted)
    grid(
      columns: (auto, 1fr, auto), column-gutter: 8pt, align: horizon,
      image(icon, height: 6mm),
      text(weight: "semibold", fill: green-deep)[PV Digital Twin],
      if chapters.len() > 0 { chapters.last().body } else { subtitle },
    )
    v(-0.5em)
    line(length: 100%, stroke: 0.6pt + rule)
  },
  footer: context {
    set text(size: 9pt, fill: muted)
    line(length: 100%, stroke: 0.6pt + rule)
    v(-0.3em)
    grid(
      columns: (1fr, auto), align: horizon,
      [#subtitle · Version #version],
      text(weight: "semibold", fill: green-deep, counter(page).display(here().page-numbering())),
    )
  },
)
counter(page).update(1)

show outline.entry.where(level: 1): it => {
  v(0.55em, weak: true)
  set text(weight: "semibold", fill: green-deep)
  it
}
show outline.entry.where(level: 2): set text(size: 10pt)
show outline: set heading(outlined: false)

block(below: 1.4em, {
  text(size: 24pt, weight: "semibold", fill: green-deep)[Contents]
  v(-0.1em)
  line(length: 100%, stroke: 1.6pt + sun)
})
outline(title: none, depth: 2, indent: 1.4em)

pagebreak()
block(below: 1.4em, {
  text(size: 24pt, weight: "semibold", fill: green-deep)[Figures]
  v(-0.1em)
  line(length: 100%, stroke: 1.6pt + sun)
})
set outline.entry(fill: repeat(text(fill: rule)[.], gap: 3pt))
outline(title: none, target: figure.where(kind: image))

// ================================================================================================= Body
pagebreak()
set page(numbering: "1")
counter(page).update(1)
show heading.where(level: 1): it => { pagebreak(weak: true); it }

body
}
