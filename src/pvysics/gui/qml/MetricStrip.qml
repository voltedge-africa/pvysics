// Figures in groups, drawn straight on the window: type, space and one hairline between groups.
// The deviation figure is the hero: it is the largest thing on screen and carries a rail that shows where
// it sits between the limits. All data comes from the `strip` object that gui/metric_strip.py provides.
import QtQuick
import QtQuick.Layouts

Item {
    id: root
    readonly property var c: strip.colours
    readonly property int u: strip.unitPx
    implicitHeight: row.implicitHeight + 2 * u

    function entry(key) {
        const found = strip.values[key]
        return found === undefined ? {number: "-", unit: "", fill: "", fillText: ""} : found
    }
    function pixels(size) {
        return {hero: u * 7.5, large: u * 4.6, medium: u * 3.1, small: u * 2.4}[size]
    }

    RowLayout {
        id: row
        x: 0
        y: root.u
        width: root.width
        spacing: root.u * 2

        Repeater {
            model: strip.groups
            delegate: Rectangle {
                id: cell
                required property var modelData
                required property int index
                Layout.fillWidth: true
                Layout.maximumWidth: 100000  // a layout's own maximum is its content's unless this says otherwise
                Layout.preferredWidth: modelData.weight * 1000
                Layout.fillHeight: true  // the groups in a row are one height
                color: "transparent"
                border.color: root.c.rule   // each group is outlined: the rule is the only separator
                border.width: 1
                radius: 4
                implicitWidth: inner.implicitWidth + 2 * root.u * 1.3
                implicitHeight: inner.implicitHeight + 2 * root.u * 1.1

                ColumnLayout {
                    id: inner
                    anchors.fill: parent
                    anchors.margins: root.u * 1.2
                    spacing: root.u * 0.8

                    Text {
                        text: cell.modelData.title
                        color: root.c.muted
                        font.family: strip.fontFamily
                        font.pixelSize: strip.smallPx
                        font.weight: Font.Medium
                    }

                    GridLayout {
                        columns: cell.modelData.columns
                        uniformCellWidths: cell.modelData.spread
                        columnSpacing: root.u * 2.5
                        rowSpacing: root.u * 1.2
                        Layout.fillWidth: true
                        Layout.maximumWidth: 100000

                        Repeater {
                            model: cell.modelData.tiles
                            delegate: ColumnLayout {
                                id: tile
                                required property var modelData
                                readonly property var shown: root.entry(modelData.key)
                                readonly property bool hero: modelData.size === "hero"
                                Layout.alignment: Qt.AlignTop
                                Layout.fillWidth: hero || cell.modelData.spread
                                Layout.maximumWidth: 100000
                                Layout.columnSpan: hero ? cell.modelData.columns : 1
                                spacing: 0

                                Text {
                                    text: tile.modelData.caption
                                    visible: text !== ""
                                    color: root.c.muted
                                    font.family: strip.fontFamily
                                    font.pixelSize: strip.smallPx
                                }
                                RowLayout {
                                    spacing: root.u * 0.5
                                    Rectangle {
                                        visible: tile.shown.fill !== ""
                                        color: tile.shown.fill === "" ? "transparent" : tile.shown.fill
                                        radius: 3
                                        implicitWidth: pill.implicitWidth + root.u * 1.4
                                        implicitHeight: pill.implicitHeight
                                        Text {
                                            id: pill
                                            anchors.centerIn: parent
                                            text: tile.shown.number
                                            color: tile.shown.fillText === "" ? root.c.text : tile.shown.fillText
                                            font.family: strip.figureFamily
                                            font.pixelSize: root.pixels(tile.modelData.size) * 0.8
                                            font.weight: Font.DemiBold
                                            font.features: {"tnum": 1}
                                        }
                                    }
                                    Text {
                                        visible: tile.shown.fill === ""
                                        text: tile.shown.number
                                        color: root.c.text
                                        font.family: strip.figureFamily
                                        font.pixelSize: root.pixels(tile.modelData.size)
                                        font.weight: Font.DemiBold
                                        font.features: {"tnum": 1}
                                    }
                                    Text {
                                        text: tile.shown.unit
                                        color: root.c.muted
                                        font.family: strip.fontFamily
                                        font.pixelSize: tile.hero ? strip.smallPx * 1.5 : strip.smallPx * 1.2
                                        Layout.alignment: Qt.AlignBottom
                                        Layout.bottomMargin: root.pixels(tile.modelData.size) * 0.12
                                    }
                                }

                                // The state, under the hero figure: a dot in the state colour and a word.
                                RowLayout {
                                    visible: tile.hero && strip.status.text !== ""
                                    spacing: root.u * 0.6
                                    Layout.topMargin: root.u * 0.4
                                    Rectangle { width: root.u; height: root.u; radius: width / 2; color: strip.status.colour }
                                    Text {
                                        text: strip.status.text
                                        color: root.c.text
                                        font.family: strip.fontFamily
                                        font.pixelSize: strip.smallPx * 1.35
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        text: strip.status.note
                                        color: root.c.muted
                                        font.family: strip.fontFamily
                                        font.pixelSize: strip.smallPx * 1.35
                                    }
                                }

                                // The rail: the deviation between the limits, zero in the middle.
                                Item {
                                    id: rail
                                    visible: tile.hero && cell.modelData.gauge
                                    Layout.fillWidth: true
                                    Layout.topMargin: root.u * 1.2
                                    implicitHeight: root.u * 3.6
                                    readonly property var g: strip.gauge
                                    readonly property real half: g.scale > 0 ? g.scale : 1
                                    function at(v) { return width * (Math.max(-half, Math.min(half, v)) + half) / (2 * half) }
                                    readonly property real bar: Math.max(root.u * 0.7, 4)

                                    Rectangle { x: 0; width: rail.at(-rail.g.abnormal); height: rail.bar
                                                color: strip.abnormalColour; opacity: 0.55 }
                                    Rectangle { x: rail.at(-rail.g.abnormal); width: rail.at(-rail.g.warning) - x; height: rail.bar
                                                color: strip.warningColour; opacity: 0.55 }
                                    Rectangle { x: rail.at(-rail.g.warning); width: rail.at(rail.g.warning) - x; height: rail.bar
                                                color: strip.normalColour; opacity: 0.55 }
                                    Rectangle { x: rail.at(rail.g.warning); width: rail.at(rail.g.abnormal) - x; height: rail.bar
                                                color: strip.warningColour; opacity: 0.55 }
                                    Rectangle { x: rail.at(rail.g.abnormal); width: rail.width - x; height: rail.bar
                                                color: strip.abnormalColour; opacity: 0.55 }

                                    Repeater {
                                        model: [-rail.g.abnormal, -rail.g.warning, 0, rail.g.warning, rail.g.abnormal]
                                        delegate: Text {
                                            required property var modelData
                                            x: Math.min(Math.max(rail.at(modelData) - width / 2, 0), rail.width - width)
                                            y: rail.bar + root.u * 0.5
                                            text: (modelData > 0 ? "+" : modelData < 0 ? "−" : "") + Math.abs(modelData)
                                            color: root.c.muted
                                            font.family: strip.fontFamily
                                            font.pixelSize: strip.smallPx
                                        }
                                    }
                                    // The marker: a tall tick in the state colour.
                                    Rectangle {
                                        visible: rail.g.active
                                        width: Math.max(root.u * 0.45, 3)
                                        height: rail.bar + root.u * 1.2
                                        y: -root.u * 0.6
                                        radius: width / 2
                                        x: rail.at(rail.g.reading) - width / 2
                                        color: root.c.text
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
