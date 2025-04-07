""" 
Defaults
--------

Defaults for segment by segment.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from omc3_gui.segment_by_segment.segment_model import SegmentTuple

if TYPE_CHECKING: 
    from omc3_gui.segment_by_segment.measurement_model import OpticsMeasurement

DEFAULT_SEGMENTS =(
    SegmentTuple("IP1", "BPM.12L1", "BPM.12R1"),
    SegmentTuple("IP2", "BPM.12L2", "BPM.12R2"),
    SegmentTuple("IP5", "BPM.12L5", "BPM.12R5"),
    SegmentTuple("IP8", "BPM.12L8", "BPM.12R8"),
)


LHC_ARCS = ('78', '81', '12', '23', '34', '45', '56', '67')  # 78 needs to be before 81 to make lr fit
LHC_CORRECTORS = (
    "kqf.a{}", 
    "kqd.a{}", 
    "kqt12.{}{}b{}", 
    "kqtl11.{}{}b{}", 
    "kq10.{}{}b{}",
    "kq9.{}{}b{}",
    "kq8.{}{}b{}",
    "kq7.{}{}b{}",
    "kq6.{}{}b{}",
    "kq5.{}{}b{}",
    "kq4.{}{}b{}",
    "kqsx3.{}{}",
    "ktqx2.{}{}",
    "ktqx1.{}{}",
    "kqx.{}{}",
)

def get_default_correctors(measurement: OpticsMeasurement) -> str:
    text = ""
    if measurement.accel == "lhc":
        text = ""
        for ip in (1, 2, 5, 8):
            text += f"! IP{ip} -----\n"
            arcs = [arc for arc in LHC_ARCS if str(ip) in arc]
            for arc, side in zip(arcs, "lr"):
                lhc_correctors = LHC_CORRECTORS if side == "l" else LHC_CORRECTORS[::-1]
                for corrector in lhc_correctors:
                    if "a" in corrector:
                        corrector = corrector.format(arc)
                    else:
                        corrector = corrector.format(side, ip, measurement.beam)
                    text += f"! {corrector} = {corrector};\n"
            text += "\n"
    return text 
