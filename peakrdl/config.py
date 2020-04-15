
import yaml

from systemrdl.messages import SourceRef

from . import yaml_schema as ys
from .elab_target import ElabTarget

class PeakRDLConfig:
    def __init__(self, app: "PeakRDLApp", path: str):
        self.app = app
        self.msg = app.msg

        with open(path) as f:
            document = f.read()

        loader = yaml.FullLoader(document)

        # Load any tags from input_loaders/exporters
        for input_loader in self.app.input_loaders:
            if input_loader.yaml_tag:
                loader.add_constructor(input_loader.yaml_tag, ys.TaggedYAMLData.yaml_constructor)

        try:
            data = loader.get_single_data()
        except yaml.parser.ParserError as e:
            src_ref = SourceRef(e.problem_mark.index, e.problem_mark.index, path)
            self.msg.fatal("Error parsing YAML. %s" % e.problem, src_ref)
        
        ctx = ys.YAMLContext(self.msg, path, self.app)

        if not isinstance(data, dict):
            self.msg.fatal("Bad top-level YAML datatype. Expected mapping", ctx.src_ref)

        self.inputs = self._parse_yaml_inputs(ctx, data)
        self.targets = self._parse_yaml_elab_targets(ctx, data)


    @staticmethod
    def representer(dumper, data):
        """
        Callback used by yaml.add_representer() to register this class
        as a dumpable yaml object.
        """
        return data.yaml_dump(dumper)

    def yaml_dump(self, dumper):
        data = {
            "inputs" : self.inputs,
            "targets" : self.targets,
        }
        return dumper.represent_data(data)


    def _parse_yaml_inputs(self, ctx: ys.YAMLContext, yaml_data: dict) -> list:
        """
        Processes the 'inputs' data structure from the YAML config.

        Return a list of InputEntry objects
        """
        if 'inputs' not in yaml_data:
            self.msg.fatal(
                "Configuration is missing required 'inputs' section",
                ctx.src_ref
            )
        input_data = yaml_data['inputs']

        # Collect all available input_loader schemas
        input_schemas = [i.get_input_schema() for i in self.app.input_loaders]

        # Process input data
        input_entries = []
        for input_datum in input_data:
            # Find first matching input_loader schema
            for input_schema in input_schemas:
                if input_schema.is_match(input_datum):
                    input_entry = input_schema.extract(ctx, input_datum)
                    input_entries.append(input_entry)
                    break
            else:
                # No match!
                self.msg.fatal(
                    "Invalid input entry: %s" % input_datum,
                    ctx.src_ref
                )
        
        return input_entries


    def _parse_yaml_elab_targets(self, ctx: ys.YAMLContext, yaml_data: dict) -> list:
        """
        Processes the 'targets' data structure from the YAML config.

        Return a list of ElabTarget objects
        """
        if 'targets' not in yaml_data:
            self.msg.fatal(
                "Configuration is missing required 'targets' section",
                ctx.src_ref
            )

        target_data = yaml_data['targets']

        # Process targets
        targets = []
        for target_datum in target_data:
            targets.append(ElabTarget.from_yaml_data(self.app, ctx, target_datum))

        return targets

yaml.add_representer(PeakRDLConfig, PeakRDLConfig.representer)
