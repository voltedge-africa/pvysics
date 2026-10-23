#import "/tools/typ/lib.typ": *
#show: setup

#canvas(length: 1cm, {
  import draw: *
  box-group("now", (0, 4.4), (7.0, 7.6), [Now: simulation])
  blk("vp", (3.5, 5.5), [*Virtual plant*\ + sensor model], w: 5.4, h: 1.7)
  box-group("later", (0, 0), (7.0, 3.2), [Later: hardware])
  blk("hw", (3.5, 1.1), [*ESP32* + sensors], w: 5.4, h: 1.5)
  blk("if", (12.4, 3.8), [*Data interface*\ timestamp, G, T, V, I], w: 5.4, h: 2.0, fill: rgb("#F4EBDD"), stroke: gold)
  blk("core", (20.4, 3.8), [*Unchanged core*\ twin, state estimator, UI], w: 6.0, h: 2.0)
  arr("vp.east", (8.2, 5.5), (8.2, 4.4), (9.7, 4.4))
  arr("hw.east", (8.2, 1.1), (8.2, 3.2), (9.7, 3.2), dash: "dashed")
  arr("if.east", "core.west")
})
