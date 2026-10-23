from PyQt6.QtWidgets import QMainWindow

from pvysics.gui.data_bus import DataBus
from pvysics.gui.playback import PlaybackController
from pvysics.gui.process_view import ProcessView
from pvysics.run import RunConfig, bundled_run_config


class MainWindow(QMainWindow):
    """The operator HMI window. The Process view is shown; other views are added by later tickets."""

    def __init__(self, bus: DataBus | None = None, config: RunConfig | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.bus = DataBus(self) if bus is None else bus
        config = bundled_run_config() if config is None else config
        self.playback = PlaybackController(config, self.bus, self)
        self.setCentralWidget(ProcessView(self.playback, self.bus))
