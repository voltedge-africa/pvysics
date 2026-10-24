// A row of figures, grouped under small headings. Flat: no boxes, only type, space and one hairline per group.
// All data comes from the `strip` object that gui/metric_strip.py puts in the context.
import QtQuick
import QtQuick.Layouts

Item {
    id: root
    readonly property var c: strip.colours
    readonly property int unit: strip.unitPx
    implicitHeight: row.implicitHeight + 2 * unit

    function entry(key) {
        const found = strip.values[key]
        return found === undefined ? {number: "-", unit: "", fill: "", fillText: ""} : found
    }

    RowLayout {
        id: row
        x: root.unit * 0.5
        y: root.unit
        width: root.width - root.unit
        spacing: root.unit * 3

        Repeater {
            model: strip.groups
            delegate: ColumnLayout {
                id: group
                required property var modelData
                Layout.fillWidth: true
                Layout.preferredWidth: modelData.weight
                Layout.alignment: Qt.AlignTop
                spacing: root.unit * 0.5

                Text {
                    text: group.modelData.title.toUpperCase()
                    color: root.c.muted
                    font.family: strip.fontFamily
                    font.pixelSize: strip.smallPx
                    font.bold: true
                    font.letterSpacing: 1
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: root.c.rule }

                RowLayout {
                    spacing: root.unit * 1.5
                    Repeater {
                        model: group.modelData.tiles
                        delegate: ColumnLayout {
                            id: tile
                            required property var modelData
                            readonly property var shown: root.entry(modelData.key)
                            spacing: 0
                            Layout.alignment: Qt.AlignTop
                            Text {
                                text: tile.modelData.caption
                                color: root.c.muted
                                font.family: strip.fontFamily
                                font.pixelSize: strip.smallPx
                            }
                            RowLayout {
                                spacing: root.unit * 0.4
                                Rectangle {
                                    visible: tile.shown.fill !== ""
                                    color: tile.shown.fill === "" ? "transparent" : tile.shown.fill
                                    radius: 4
                                    implicitWidth: figure.implicitWidth + root.unit
                                    implicitHeight: figure.implicitHeight
                                    Text {
                                        id: figure
                                        anchors.centerIn: parent
                                        text: tile.shown.number
                                        color: tile.shown.fillText === "" ? root.c.text : tile.shown.fillText
                                        font.family: strip.fontFamily
                                        font.pixelSize: strip.numberPx
                                        font.bold: true
                                    }
                                }
                                Text {
                                    visible: tile.shown.fill === ""
                                    text: tile.shown.number
                                    color: root.c.text
                                    font.family: strip.fontFamily
                                    font.pixelSize: strip.numberPx
                                    font.bold: true
                                }
                                Text {
                                    text: tile.shown.unit
                                    color: root.c.muted
                                    font.family: strip.fontFamily
                                    font.pixelSize: strip.smallPx + 1
                                    Layout.alignment: Qt.AlignBottom
                                    Layout.bottomMargin: root.unit * 0.3
                                }
                            }
                        }
                    }
                    Item {
                        id: gauge
                        visible: group.modelData.gauge
                        Layout.fillWidth: true
                        Layout.minimumWidth: root.unit * 12
                        Layout.alignment: Qt.AlignBottom
                        implicitHeight: strip.numberPx
                        readonly property var g: strip.gauge
                        readonly property real scale: g.scale > 0 ? g.scale : 1
                        function at(pct) { return width * Math.min(pct, scale) / scale }

                        readonly property real band: root.unit * 0.8
                        readonly property real trackTop: root.unit * 1.2
                        Rectangle { x: 0; y: gauge.trackTop; width: gauge.at(gauge.g.warning); height: gauge.band
                                    color: strip.normalColour; opacity: 0.4 }
                        Rectangle { x: gauge.at(gauge.g.warning); y: gauge.trackTop; width: gauge.at(gauge.g.abnormal) - x
                                    height: gauge.band; color: strip.warningColour; opacity: 0.4 }
                        Rectangle { x: gauge.at(gauge.g.abnormal); y: gauge.trackTop; width: gauge.width - x
                                    height: gauge.band; color: strip.abnormalColour; opacity: 0.4 }
                        Rectangle { visible: gauge.g.active; width: root.unit * 0.5; radius: width / 2
                                    x: Math.max(0, gauge.at(gauge.g.reading) - width / 2); y: gauge.trackTop - root.unit * 0.5
                                    height: gauge.band + root.unit; color: gauge.g.colour }
                        Repeater {
                            model: [gauge.g.warning, gauge.g.abnormal]
                            delegate: Item {
                                required property var modelData
                                x: gauge.at(modelData)
                                Rectangle { y: gauge.trackTop; width: 1; height: gauge.band; color: root.c.text }
                                Text {
                                    x: -width / 2
                                    y: gauge.trackTop + gauge.band + root.unit * 0.3
                                    text: parent.modelData + " %"
                                    color: root.c.muted
                                    font.family: strip.fontFamily
                                    font.pixelSize: strip.smallPx
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
