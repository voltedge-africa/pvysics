// Shared helpers for the PV digital twin diagrams (Typst + CeTZ), DUT colours.
#import "@preview/cetz:0.4.2": canvas, draw

#let green = rgb("#137F36")
#let green-light = rgb("#E3F1E7")
#let gold = rgb("#D7B680")
#let cream = rgb("#F7F3EA")
#let ink = black

#let setup(body) = {
  set page(width: auto, height: auto, margin: 8pt, fill: white)
  set text(font: ("Liberation Sans", "Arial", "DejaVu Sans"), size: 14pt)
  body
}

// Rectangular block centred at pos. A named group, so anchors like "id.east" work.
#let blk(id, pos, body, w: 3.6, h: 1.5, fill: green-light, stroke: green) = draw.group(name: id, {
  draw.rect((pos.at(0) - w / 2, pos.at(1) - h / 2), (pos.at(0) + w / 2, pos.at(1) + h / 2),
    fill: fill, stroke: 1.2pt + stroke, radius: 0.12)
  draw.content(pos, align(center, body))
})

// Grouping container with a title in its top-left corner.
#let box-group(id, a, b, title) = draw.group(name: id, {
  draw.rect(a, b, fill: cream, stroke: 1.2pt + gold, radius: 0.18)
  draw.content((a.at(0) + 0.25, b.at(1) - 0.2), text(weight: "bold", fill: rgb("#6b5a3a"), title), anchor: "north-west")
})

// Signal (thin) or power (thick) arrow through the given points.
#let arr(..pts, thick: false, color: ink, dash: none) = draw.line(..pts,
  stroke: (thickness: if thick { 3pt } else { 1.3pt }, paint: color, dash: dash),
  mark: (end: ">", fill: color, scale: if thick { 0.8 } else { 1 }))

// Plain wire (no arrowhead).
#let wire(..pts, color: ink) = draw.line(..pts, stroke: 1.6pt + color)

// Text label sitting on a line.
#let tag(pos, body, anchor: "center") = draw.content(pos, body, anchor: anchor,
  frame: "rect", fill: white, stroke: none, padding: 0.1)
