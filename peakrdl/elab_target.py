import yaml

from . import yaml_schema as ys

class ElabTarget:

    schema = ys.Mapping({
        ys.String() : ys.Mapping({
            "label": ys.String(),
            "inst_name": ys.String(),
            "parameters": ys.Mapping({
                ys.String() : ys.Anything()
            }),
            "export": ys.UniformList(ys.Anything()) # defer validating exporters to later
        })
    })

    def __init__(self, app, label: str, type_name: str, inst_name: str, parameters: list):
        self.app = app
        self.label = label
        self.type_name = type_name
        self.inst_name = inst_name
        self.parameters = parameters

        self.root = None

        self.exports = []

    @staticmethod
    def representer(dumper, data):
        """
        Callback used by yaml.add_representer() to register this class
        as a dumpable yaml object.
        """
        return data.yaml_dump(dumper)

    def yaml_dump(self, dumper):
        data = {
            self.type_name : {
                "label": self.label,
                "inst_name": self.inst_name,
                "parameters": self.parameters,
                "export": self.exports,
            }
        }
        return dumper.represent_data(data)

    @classmethod
    def from_yaml_data(cls, app, ctx: ys.YAMLContext, data: dict):
        if not cls.schema.is_match(data):
            ctx.msg.fatal(
                "Invalid entry in 'targets': %s" % data,
                ctx.src_ref
            )
        data = cls.schema.extract(ctx, data)

        if len(data.keys()) != 1:
            # user probably forgot to indent
            ctx.msg.fatal(
                "Malformed entry in 'targets'. Check your indentation near input '%s'" % list(data.keys())[0],
                ctx.src_ref
            )

        type_name = list(data.keys())[0]
        params = list(data.values())[0]

        label = params.get("label", None)
        inst_name = params.get("inst_name", None)

        # TODO: Add a YAML tag that allows one to eval an rdl expression as a parameter
        parameters = params.get("parameters", {})
        exports_data = params.get("export", [])

        # Collect all available exporter schemas
        export_schemas = [i.get_export_schema() for i in app.exporters]

        target = cls(app, label, type_name, inst_name, parameters)

        # Process exports
        ctx.target = target
        target.exports = []
        for export_datum in exports_data:
            # Find first matching exporter schema
            for export_schema in export_schemas:
                if export_schema.is_match(export_datum):
                    export_entry = export_schema.extract(ctx, export_datum)
                    target.exports.append(export_entry)
                    break
            else:
                # No match!
                ctx.msg.fatal(
                    "Invalid entry in 'exports': %s" % export_datum,
                    ctx.src_ref
                )
        ctx.target = None

        return target
    
    def elaborate(self):
        try:
            self.root = self.app.rdlc.elaborate(
                self.type_name,
                self.inst_name,
                self.parameters
            )
        except (ValueError, TypeError) as e:
            self.app.msg.fatal(
                "Unable to elaborate target '%s': %s" % (self.type_name, e)
            )

yaml.add_representer(ElabTarget, ElabTarget.representer)
