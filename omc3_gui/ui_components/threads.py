""" 
UI: Threads
-----------

Helper functions for threads.
"""
import logging
from qtpy.QtCore import QThread, Signal
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)


class BackgroundThread(QThread):
    """ Thread that runs a function in the background,
    providing a post- and exception-hook.
    
    Args:
        function (Callable): The function to run in the background.
        message (str): The message to display while the function is running.
        on_end_function (Callable): A function to call when the function is done.
        on_exception_function (Callable): A function to call when the function throws an exception.
    """

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
        """ 
        Runner for the thread.
        This function is called automatically when the thread is started. 
        """
        try:
            self._function()
        except Exception as e:
            LOGGER.exception(str(e))
            self.on_exception.emit(str(e))
            return 
            
        LOGGER.info(f"Finished {self.message!s} successfully!")

    def start(self):
        """
        Connects the thread to the on_end and on_exception signals and starts the thread.
        This function is triggered manually to start the thread.
        """
        self.finished.connect(self._on_end)
        self.on_exception.connect(self._on_exception)
        super(BackgroundThread, self).start()

    def _on_end(self):
        if self._on_end_function:
            self._on_end_function()

    def _on_exception(self, exception_message):
        if self._on_exception_function:
            self._on_exception_function(exception_message)
