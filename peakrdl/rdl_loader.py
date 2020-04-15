import os

from .input_loader import InputEntry
from .input_loader import InputLoader
from . import yaml_schema as ys

class RDLLoader(InputLoader):
    yaml_tag = None
    params_schema = {
        "includes": ys.UniformList(ys.FilePath())
    }

    def compile_input(self, app, input_entry: InputEntry):
        includes = input_entry.params.get('includes', [])

        if not os.path.isfile(input_entry.file_path):
            app.msg.fatal(
                "File does not exist: %s" % input_entry.file_path
            )

        app.rdlc.compile_file(
            input_entry.file_path,
            incl_search_paths = includes
        )
