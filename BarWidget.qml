import QtQuick
import qs.Commons
import qs.Commons as Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "io.github.frestina.omakodi"

  property bool active: false
  readonly property string label: root.active ? "O · on" : "O"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.vertical ? (root.active ? "●" : "○") : root.label
    tooltipText: root.active ? "omakodi is active" : "Activate omakodi"

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) root.active = !root.active
    }
  }
}
