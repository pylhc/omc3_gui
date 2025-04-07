""" 
Help Dialogs
------------
"""
from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMessageBox

def show_help_dialog():
    """ Displays the help dialog for the segment-by-segment GUI. """

    help_text = """
    <h3> Frequently Asked Questions </h3><br>
    
    <br>
    <b> How do I open a Measurement?</b><br>
    
    One way to open measurements automatically, is to give them as command line
    arguments when starting the sbs_gui, either <i> -m </i> or <i> --measurements </i>.<br>
    If you want to load them manually, you click the <i>Load</i> button.<br><br>

    The given/selected measurements can be either <i>omc3 optics folders, folders containing sbs-json files
    or sbs-json files</i> directly.
    The latter are created automatically in the measurement-output folder when editing a loaded measurement.<br>

    <br>
    
    <b> Do I have to invert my corrections when using them in the machine?</b><br>

    YES! <i>(but it depends)</i><br>
    The "corrections" here are actually used to match the model opttics to the 
    mesured optics (see the info about the dashed "corr" line below). 
    Therefore you have to invert them, to actually use them as corrections in the machine. <br>
    <b> NOTE </b> that these are the MAD-X values. Make how the signs are actually
    mapped in the machine! <br>

    <br>

    <b> What is the solid line?</b><br>

    The solid line is the difference between the Measurement and 
    the propagated model, i.e. the Measurement at the start (or end) of the segment 
    propagated through the nominal model via MAD-X.<br>
    This line therefore shows you how much the optics deviate through the segment 
    from the nominal model.<br> 

    <br>   
    
    <b> What is the dashed line that says "corr"?</b><br>

    This is the difference between the <i>"corrected"</i> propagated model and the 
    nominal propagated model.<br>
    This means in both cases the measured values are used as initial conditions.
    What you are trying to achieve is a match between the dashed and the solid line,
    because that means that now your model matches the optics in the measured data.<br>

    <br>
    
    <b> What is the dashed line that says "expct"?</b><br>

    This is the difference between the Measurement and the "corrected" propagated model
    and is therefore the <i>expected</i> measured difference to the nominal model after 
    applying the correction in the machine (same as in global correction).<br>
    You can activate this view via the plot-settings <i>"Expectation"</i>.<br>

    <br>

    <b>Shortcuts</b><br>

    In Graph:<br>
    <i>Double-Click</i> : Zoom history back one step. <br>
    <i>Right-Click</i> : Zoom history back one step. <br>
    <i>Shift + Right-Click</i> : Zoom history back all steps. <br>
    <i>Alt + Right-Click</i> : pyqtgraph context menu. <br>

    <br>

    In Measurements-List:<br>
    <i>Double-Click</i> : Edit the Measurement.<br>

    <br> 
    
    """
    msg_box = QMessageBox(icon=QMessageBox.Information)
    msg_box.setWindowTitle("Help")
    msg_box.setTextFormat(Qt.TextFormat.RichText)
    msg_box.setText(help_text)
    msg_box.exec_()
