import yaml

from . import yaml_schema as ys

class ExportEntrySchema(ys.SchemaBase):
    """
    Generic schema node for export entries.
    Handles the nuances of various export entry styles.
    Extract returns a resolved ExportEntry object.
    """

    def __init__(self, exporter, params_schema: dict):
        self.exporter = exporter
        self.params_schema = params_schema

        self.schema = ys.AnyOf([
            ys.Mapping({
                self.exporter.name: ys.FilePath()
            }),
            ys.Mapping({
                self.exporter.name: ys.Mapping({
                    "path": ys.FilePath(),
                    ys.String(): ys.Anything()
                })
            })
        ])

    def is_match(self, data) -> bool:
        return self.schema.is_match(data)

    def extract(self, ctx: ys.YAMLContext, data):
        data = self.schema.extract(ctx, data)

        if len(data.keys()) != 1:
            # user probably forgot to indent
            ctx.msg.fatal(
                "Malformed entry in 'inputs'. Check your indentation near input '%s'" % list(data.keys())[0],
                ctx.src_ref
            )

        data = list(data.values())[0]

        if isinstance(data, str):
            # Is shorthand entry
            return ExportEntry(ctx.app, ctx.target, self.exporter, data, {})

        # Otherwise, data is the params dict
        params = data

        # Extract path first
        if "path" not in params:
            # path is required!
            ctx.msg.fatal(
                "Missing required 'path' option for %s exporter" % self.exporter.name,
                ctx.src_ref
            )
        path = params.pop("path")

        # Process remaining params using schema
        processed_params = {}
        for param_name, param_value in params.items():
            if param_name in self.params_schema:
                if not self.params_schema[param_name].is_match(param_value):
                    # Invalid param format
                    ctx.msg.fatal(
                        "%s exporter uses param '%s' that contains an illegal value." % (self.exporter.name, param_name),
                        ctx.src_ref
                    )
                processed_params[param_name] = self.params_schema[param_name].extract(ctx, param_value)
            else:
                ctx.msg.warning(
                    "Ignoring unknown param '%s' in %s exporter" % (param_name, self.exporter.name),
                    ctx.src_ref
                )

        return ExportEntry(ctx.app, ctx.target, self.exporter, path, processed_params)


class ExportEntry:
    def __init__(self, app, target, exporter, path: str, params: dict):
        self.app = app
        self.target = target
        self.exporter = exporter
        self.path = path
        self.params = params
    
    @staticmethod
    def representer(dumper, data):
        """
        Callback used by yaml.add_representer() to register this class
        as a dumpable yaml object.
        """
        return data.yaml_dump(dumper)

    def yaml_dump(self, dumper):
        if self.params:
            p = {"path": self.path}
            p.update(self.params)
            data = {self.exporter.name: p}
        else:
            data = {self.exporter.name: self.path}

        return dumper.represent_data(data)

yaml.add_representer(ExportEntry, ExportEntry.representer)

class Exporter:
    name = ""
    params_schema = {}

    def get_export_schema(self) -> ExportEntrySchema:
        return ExportEntrySchema(self, self.params_schema)
