import yaml

from . import yaml_schema as ys

class InputEntrySchema(ys.SchemaBase):
    """
    Generic schema node for input file entries.
    Handles the nuances of various input entry styles.
    Extract returns a resolved InputEntry object.
    """
    def __init__(self, input_loader, params_schema: dict, tag: str = None):
        self.input_loader = input_loader
        self.params_schema = params_schema
        
        if tag:
            self.schema = ys.AnyOf([
                ys.Tagged(tag, ys.FilePath()),
                ys.Mapping({
                    ys.Tagged(tag, ys.FilePath()) : ys.Mapping({
                        ys.String() : ys.Anything()
                    })
                })
            ])
        else:
            self.schema = ys.AnyOf([
                ys.FilePath(),
                ys.Mapping({
                    ys.FilePath() : ys.Mapping({
                        ys.String() : ys.Anything()
                    })
                })
            ])
    
    def is_match(self, data) -> bool:
        return self.schema.is_match(data)
    
    def extract(self, ctx: ys.YAMLContext, data):
        data = self.schema.extract(ctx, data)

        if isinstance(data, str):
            # Simple entry without params
            return InputEntry(self.input_loader, data, {})
        
        if len(data.keys()) != 1:
            # user probably forgot to indent
            ctx.msg.fatal(
                "Malformed entry in 'inputs'. Check your indentation near input '%s'" % list(data.keys())[0],
                ctx.src_ref
            )

        path = list(data.keys())[0]
        params = list(data.values())[0]

        # Process params using schema
        processed_params = {}
        for param_name, param_value in params.items():
            if param_name in self.params_schema:
                if not self.params_schema[param_name].is_match(param_value):
                    # Invalid param format
                    ctx.msg.fatal(
                        "Input '%s', param '%s' contains an illegal value." % (path, param_name),
                        ctx.src_ref
                    )
                processed_params[param_name] = self.params_schema[param_name].extract(ctx, param_value)
            else:
                ctx.msg.warning(
                    "Ignoring unknown param '%s' in input '%s'" % (param_name, path),
                    ctx.src_ref
                )
                
        return InputEntry(self.input_loader, path, processed_params)


class InputEntry:
    def __init__(self, input_loader, file_path: str, params: dict):
        self.input_loader = input_loader
        self.file_path = file_path
        self.params = params
    
    @staticmethod
    def representer(dumper, data):
        """
        Callback used by yaml.add_representer() to register this class
        as a dumpable yaml object.
        """
        return data.yaml_dump(dumper)

    def yaml_dump(self, dumper):
        if self.input_loader.yaml_tag:
            path_data = ys.TaggedYAMLData(self.input_loader.yaml_tag, self.file_path)
        else:
            path_data = self.file_path

        if self.params:
            data = {path_data: self.params}
        else:
            data = path_data
        return dumper.represent_data(data)

yaml.add_representer(InputEntry, InputEntry.representer)

class InputLoader:
    yaml_tag = None
    params_schema = {}

    def get_input_schema(self) -> InputEntrySchema:
        return InputEntrySchema(self, self.params_schema, self.yaml_tag)

    def compile_input(self, app, input_entry: InputEntry):
        raise NotImplementedError