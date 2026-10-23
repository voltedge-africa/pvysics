#import "/tools/typ/lib.typ": *
#show: setup

#canvas(length: 1cm, {
  import draw: *
  blk("in", (0, 4.0), [$G$, $T$ profile], w: 3.2, h: 1.5)
  box-group("plant", (3.2, 3.4), (22.4, 8.4), [Virtual plant: the "real" PV])
  blk("ps", (7.6, 5.2), [*SDM, perturbed parameters*\ $R_"s"$, $R_"sh"$, temp-coeff offsets], w: 7.6, h: 2.0)
  blk("fi", (13.6, 5.2), [*Fault*\ *injector*], w: 3.2, h: 2.0)
  blk("sm", (19.3, 5.2), [*Sensor model*\ noise +\ quantisation], w: 4.2, h: 2.0)
  box-group("twin", (3.2, 0), (11.2, 2.8), [Digital twin])
  blk("tw", (7.2, 1.15), [*SDM*, nominal parameters], w: 6.6, h: 1.4)
  blk("cmp", (28.6, 3.6), [*Compare*], w: 3.4, h: 2.0)
  arr("in.east", (2.4, 4.0), (2.4, 5.2), "ps.west")
  arr((2.4, 4.0), (2.4, 1.15), "tw.west")
  arr("ps.east", "fi.west")
  arr("fi.east", "sm.west")
  arr("sm.east", (24.6, 5.2), (24.6, 4.1), (26.9, 4.1))
  tag((25.4, 5.2), text(size: 12pt)[$V$, $I$])
  arr("tw.east", (24.6, 1.15), (24.6, 3.1), (26.9, 3.1))
  tag((18.0, 1.15), text(size: 12pt)[$P_"pred"$])
})
