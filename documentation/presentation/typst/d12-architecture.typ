#import "/tools/typ/lib.typ": *
#show: setup

#canvas(length: 1cm, {
  import draw: *
  blk("eng", (0, 3), [*Simulation engine*\ virtual plant + twin], w: 5.2, h: 2.0)
  blk("bus", (8.0, 3), [*Data bus*\ + CSV logger], w: 3.8, h: 2.0, fill: rgb("#F4EBDD"), stroke: gold)
  blk("hmi", (15.8, 5.0), [*HMI*\ interactive demo], w: 4.8, h: 1.7)
  blk("dash", (15.8, 1.0), [*Dashboard*\ read-only analytics], w: 4.8, h: 1.7)
  arr("eng.east", "bus.west")
  arr("bus.east", (11.7, 3), (11.7, 5.0), "hmi.west")
  arr((11.7, 3), (11.7, 1.0), "dash.west")
  arr("hmi.north", (15.8, 7.3), (0, 7.3), "eng.north", dash: "dashed")
  tag((7.9, 7.3), [setpoints, faults])
})
