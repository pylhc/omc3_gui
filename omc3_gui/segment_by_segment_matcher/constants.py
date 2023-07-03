from omc3.model.accelerators import lhc

MACHINE_OUTPUT_FOLDERS = ["LHCB1", "LHCB2"]

LHC_YEARS = lhc.Lhc.get_parameters()["year"]["choices"]
