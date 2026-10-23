#import "/tools/typ/lib.typ": *
#show: setup

#canvas(length: 1cm, {
  import draw: *
  // PV test bench
  box-group("bench", (0, 0), (14.0, 9.6), [PV test bench])
  blk("pv", (2.0, 7.0), [PV module], w: 3.0)
  blk("ina", (6.6, 7.0), [*INA219*\ V and I sensing], w: 4.2)
  blk("load", (11.7, 7.0), [Load\ #text(size: 12pt)[resistive / electronic]], w: 4.2)
  blk("ds", (3.0, 4.4), [*DS18B20*\ module temperature], w: 5.0)
  blk("irr", (3.0, 1.7), [*Irradiance sensor*\ in module plane], w: 5.0)
  arr("pv.east", "ina.west", thick: true)
  arr("ina.east", "load.west", thick: true)

  // data acquisition
  blk("esp", (19.2, 4.4), [*ESP32*\ sampling and\ timestamping], w: 4.8, h: 2.8)
  arr("ds.east", "esp.west")
  tag((9.6, 4.4), [1-Wire])
  arr("ina.north", (6.6, 9.0), (15.4, 9.0), (15.4, 5.3), (16.8, 5.3))
  tag((11.0, 9.0), [I#sub[2]C])
  arr("irr.east", (15.4, 1.7), (15.4, 3.5), (16.8, 3.5))
  tag((9.6, 1.7), [analog])

  // digital twin
  box-group("twin", (23.8, 2.9), (34.4, 9.2), [Digital twin])
  blk("sdm", (29.1, 7.4), [*Single Diode Model*\ predicted power], w: 6.4)
  blk("dev", (29.1, 4.6), [*Power deviation*\ and state estimator], w: 6.4)
  arr("sdm.south", "dev.north")
  arr((21.6, 5.1), (22.8, 5.1), (22.8, 7.4), "sdm.west")
  tag((22.8, 6.25), text(size: 12pt)[G, T, V, I])
  arr((21.6, 3.7), (22.8, 3.7), (22.8, 4.6), "dev.west")
  tag((22.8, 4.15), text(size: 12pt)[P#sub[meas]])

  // UI
  blk("ui", (29.1, 0.9), [*Monitoring*\ dashboard and HMI], w: 6.4, h: 1.6)
  arr("dev.south", "ui.north")
})
