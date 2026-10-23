#import "/tools/typ/lib.typ": *
#show: setup
#set text(size: 15pt)

#canvas(length: 1cm, {
  import draw: *
  let h = 3.0          // rail separation
  let xd = 3.3         // diode branch
  let xs = 7.0         // shunt branch
  let xo = 11.6         // output terminals
  let g = (paint: green, thickness: 2pt)

  // current source Iph
  circle((0, h / 2), radius: 0.65, stroke: g)
  line((0, h / 2 - 0.35), (0, h / 2 + 0.35), stroke: g, mark: (end: ">", fill: green, scale: 0.9))
  wire((0, 0), (0, h / 2 - 0.65)); wire((0, h / 2 + 0.65), (0, h))
  content((-1.1, h / 2), text(fill: green)[$I_"ph"$])

  // rails
  wire((0, h), (xs, h)); wire((0, 0), (xo, 0))

  // diode D (conducting downward)
  wire((xd, h), (xd, h / 2 + 0.6))
  line((xd - 0.4, h / 2 + 0.6), (xd + 0.4, h / 2 + 0.6), (xd, h / 2 - 0.1), close: true, stroke: g, fill: white)
  line((xd - 0.4, h / 2 - 0.1), (xd + 0.4, h / 2 - 0.1), stroke: g)
  wire((xd, h / 2 - 0.1), (xd, 0))
  content((xd + 0.95, h / 2 + 0.25), text(fill: green)[$D$])

  // shunt resistor Rsh
  let zig(x, y0, y1) = {
    let n = 6
    let pts = ((x, y0),)
    for i in range(n) { pts.push((x + if calc.rem(i, 2) == 0 { -0.3 } else { 0.3 }, y0 + (y1 - y0) * (i + 0.5) / n)) }
    pts.push((x, y1))
    line(..pts, stroke: g)
  }
  wire((xs, h), (xs, h - 0.6)); zig(xs, h - 0.6, 0.6); wire((xs, 0.6), (xs, 0))
  content((xs + 1.15, h / 2), text(fill: green)[$R_"sh"$])

  // series resistor Rs on the top rail
  let zigx(y, x0, x1) = {
    let n = 6
    let pts = ((x0, y),)
    for i in range(n) { pts.push((x0 + (x1 - x0) * (i + 0.5) / n, y + if calc.rem(i, 2) == 0 { 0.3 } else { -0.3 })) }
    pts.push((x1, y))
    line(..pts, stroke: g)
  }
  wire((xs, h), (8.0, h)); zigx(h, 8.0, 9.8); content((8.9, h + 0.75), text(fill: green)[$R_"s"$])
  line((9.8, h), (xo - 0.1, h), stroke: 1.6pt + ink, mark: (end: ">", fill: ink))
  content((10.7, h + 0.65), $I$)

  // junction dots and output terminals
  for p in ((xd, h), (xd, 0), (xs, h), (xs, 0)) { circle(p, radius: 0.09, fill: ink, stroke: none) }
  circle((xo, h), radius: 0.13, fill: white, stroke: 1.6pt + ink)
  circle((xo, 0), radius: 0.13, fill: white, stroke: 1.6pt + ink)

  // output voltage
  line((xo + 0.9, 0.15), (xo + 0.9, h - 0.15), stroke: 1.3pt + ink, mark: (start: ">", end: ">", fill: ink, scale: 0.8))
  content((xo + 1.55, h / 2), $V$)
  content((xo + 0.55, h - 0.1), text(size: 12pt)[$+$]); content((xo + 0.55, 0.1), text(size: 12pt)[$-$])

  // branch currents
  line((xd - 0.9, h / 2 + 0.55), (xd - 0.9, h / 2 - 0.55), stroke: 1.2pt + ink, mark: (end: ">", fill: ink, scale: 0.8))
  content((xd - 1.55, h / 2), $I_"d"$)
  line((xs - 0.9, h / 2 + 0.55), (xs - 0.9, h / 2 - 0.55), stroke: 1.2pt + ink, mark: (end: ">", fill: ink, scale: 0.8))
  content((xs - 1.65, h / 2), $I_"sh"$)
})
