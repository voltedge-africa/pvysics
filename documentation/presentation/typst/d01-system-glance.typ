#import "/tools/typ/lib.typ": *
#show: setup

#canvas(length: 1cm, {
  import draw: *
  blk("in", (0, 3), [Irradiance $G$\ Temperature $T$], w: 4.0, h: 1.7)
  blk("plant", (6.4, 4.7), [*PV plant*\ measured $V$, $I$], w: 3.8)
  blk("twin", (6.4, 1.3), [*Digital twin*\ SDM prediction], w: 3.8)
  blk("dev", (12.4, 3), [*Power deviation*\ percent], w: 4.2, h: 1.7)
  blk("state", (18.4, 3), [*State*\ Normal / Warning /\ Abnormal], w: 4.4, h: 2.2)
  blk("ui", (23.8, 3), [*HMI and*\ *dashboard*], w: 3.4, h: 1.7)
  arr("in.east", (3.0, 3), (3.0, 4.7), "plant.west")
  arr((3.0, 3), (3.0, 1.3), "twin.west")
  arr("plant.east", (9.3, 4.7), (9.3, 3.35), (10.3, 3.35))
  arr("twin.east", (9.3, 1.3), (9.3, 2.65), (10.3, 2.65))
  arr("dev.east", "state.west")
  arr("state.east", "ui.west")
})
