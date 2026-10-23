from PyQt6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """The operator HMI window. Panels are added by later tickets."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PV Digital Twin")
