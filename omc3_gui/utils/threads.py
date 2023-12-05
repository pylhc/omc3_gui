import logging
from qtpy.QtCore import QThread, Signal
from typing import Callable

LOGGER = logging.getLogger(__name__)


class BackgroundThread(QThread):

    on_exception = Signal([str])

    def __init__(self, 
                function: Callable,
                message: str = None,
                on_end_function: Callable = None, 
                on_exception_function: Callable = None):
        QThread.__init__(self)
        self._function = function
        self._message = message
        self._on_end_function = on_end_function
        self._on_exception_function = on_exception_function
    
    @property
    def message(self):
        return self._message

    def run(self):
        try:
            self._function()
        except Exception as e:
            LOGGER.exception(str(e))
            self.on_exception.emit(str(e))

    def start(self):
        self.finished.connect(self._on_end)
        self.on_exception.connect(self._on_exception)
        super(BackgroundThread, self).start()

    def _on_end(self):
        if self._on_end_function:
            self._on_end_function()

    def _on_exception(self, exception_message):
        if self._on_exception_function:
            self._on_exception_function(exception_message)