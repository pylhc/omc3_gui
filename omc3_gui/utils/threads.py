class BackgroundThread(QThread):

    on_exception = Signal([str])

    def __init__(self, view, function, message=None,
                 on_end_function=None, on_exception_function=None):
        QThread.__init__(self)
        self._view = view
        self._function = function
        self._message = message
        self._on_end_function = on_end_function
        self._on_exception_function = on_exception_function

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
        self._view.show_background_task_dialog(self._message)

    def _on_end(self):
        self._view.hide_background_task_dialog()
        self._on_end_function()

    def _on_exception(self, exception_message):
        self._view.hide_background_task_dialog()
        self._view.show_error_dialog("Error", exception_message)
        self._on_exception_function(exception_message)