from functools import lru_cache

from PyQt6.QtWidgets import QMainWindow

from pvysics.gui.data_bus import DataBus
from pvysics.gui.playback import PlaybackController
from pvysics.gui.process_view import ProcessView
from pvysics.run import RunResult, bundled_run_config, run


@lru_cache(maxsize=1)
def bundled_result() -> RunResult:
    """The bundled Durban day, run once per process. The run is deterministic and takes seconds."""
    return run(bundled_run_config())


class MainWindow(QMainWindow):
    """The operator HMI window. The Process view is shown; other views are added by later tickets."""

    def __init__(self, bus: DataBus | None = None, run_result: RunResult | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
        self.bus = DataBus(self) if bus is None else bus
        result = bundled_result() if run_result is None else run_result
        self.playback = PlaybackController(result, self.bus, self)
        self.setCentralWidget(ProcessView(self.playback, self.bus))
