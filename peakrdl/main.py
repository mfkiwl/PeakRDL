
from systemrdl import RDLCompiler

from .config import PeakRDLConfig
from .rdl_loader import RDLLoader
from .ipxact_loader import IPXACTLoader
from .html_output import HTMLOutput

class PeakRDL:
    def __init__(self):
        self.input_loaders = [
            RDLLoader(),
            IPXACTLoader(),
        ]

        self.exporters = [
            HTMLOutput(),
        ]

        self.cfg = None

        self.rdlc = RDLCompiler()

        # Steal the RDL message handler
        self.msg = self.rdlc.msg

    def load_config(self, path: str):
        self.cfg = PeakRDLConfig(self, path)
    
    def compile_inputs(self):
        for inp in self.cfg.inputs:
            inp.input_loader.compile_input(self, inp)
