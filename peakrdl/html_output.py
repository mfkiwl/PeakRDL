from .exporter import Exporter
from . import yaml_schema as ys

class HTMLOutput(Exporter):
    name = "html"
    params_schema = {
        "title": ys.String()
    }