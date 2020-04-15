import os

from peakrdl.ipxact import IPXACTImporter

from .input_loader import InputEntry
from .input_loader import InputLoader
from . import yaml_schema as ys

class IPXACTLoader(InputLoader):
    yaml_tag = "!ip-xact"
    params_schema = {}

    def compile_input(self, app, input_entry: InputEntry):
        if not os.path.isfile(input_entry.file_path):
            app.msg.fatal(
                "File does not exist: %s" % input_entry.file_path
            )
        
        IPXACTImporter(app.rdlc).import_file(input_entry.file_path)
