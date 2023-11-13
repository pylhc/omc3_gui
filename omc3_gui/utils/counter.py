from qtpy import QtWidgets


class Counter:
    """ Simple class to count up integers. Similar to itertools.count """

    def __init__(self, start=0, end=None):
        self.count = start
        self._end = end
        self._start = start

    def reset(self):
        self.count = self._start

    def __next__(self):
        self.count += 1

        if self._end is not None and self.count >= self._end:
            raise StopIteration

        return self.count

    def __iter__(self):
        return self

    def next(self):
        return next(self)

    def current(self):
        return self.count


class HorizontalGridLayoutFiller:
    """Fills a grid-layout with widgets, without having to give row and col positions, 
    but allows giving a col-span.
    """

    def __init__(self, layout: QtWidgets.QGridLayout, cols: int, rows: int = None):
        self._layout = layout
        self._cols = cols
        self._rows = rows
        self._current_col = 0
        self._current_row = 0

        
    def add(self, widget, col_span=1):
        self._layout.addWidget(widget, self._current_row, self._current_col, 1, col_span)
        self._current_col += col_span
        if self._current_col > self._cols:
            raise ValueError("Span too large for given columns.")

        if self._current_col == self._cols:
            self._current_col = 0
            self._current_row += 1
            if self._rows is not None and self._current_row >= self._rows:
                raise ValueError("Grid is already full.")

    
    addWidget = add

        