from PyQt6.QtCore import QObject, pyqtSignal


class DataBus(QObject):
    """The in-process data bus. The app owns one instance; windows subscribe to its signals.

    The playback controller emits; any window can connect to these signals.
    """

    sample = pyqtSignal(object)  # Sample, once per time step as the run plays
    event = pyqtSignal(object)  # Event, when the run reaches it
    run_reset = pyqtSignal()  # the run was reset to its start
