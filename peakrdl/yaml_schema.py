import os
import sys

from systemrdl.messages import SourceRef

from collections import OrderedDict

import yaml
#-------------------------------------------------------------------------------
# Misc YAML utils
#-------------------------------------------------------------------------------
class TaggedYAMLData:
    """
    Used when parsing a YAML document to wrap data marked with a tag.
    """
    def __init__(self, tag: str, value):
        self.tag = tag
        self.value = value
    
    def __repr__(self):
        return "<%s tag='%s', value='%s'>" % (type(self).__name__, self.tag, repr(self.value))
    
    @classmethod
    def yaml_constructor(cls, loader, node):
        if isinstance(node, yaml.nodes.ScalarNode):
            value = loader.construct_scalar(node)
        elif isinstance(node, yaml.nodes.SequenceNode):
            value = loader.construct_sequence(node)
        elif isinstance(node, yaml.nodes.MappingNode):
            value = loader.construct_mapping(node)
        else:
            raise RuntimeError
        return cls(node.tag, value)
    
    @staticmethod
    def representer(dumper, data):
        """
        Callback used by yaml.add_representer() to register this class
        as a dumpable yaml object.
        """
        return data.yaml_dump(dumper)
    
    def yaml_dump(self, dumper):
        return dumper.represent_scalar(self.tag, self.value)

yaml.add_representer(TaggedYAMLData, TaggedYAMLData.representer)

class YAMLContext:
    """
    Context container object that is passed around while extracting data via
    a schema tree.
    """
    def __init__(self, msg, yaml_path: str, app):
        self.msg = msg

        # Path to the yaml file. May be absolute or relative to CWD
        self.yaml_path = yaml_path

        self.src_ref = SourceRef(filename=yaml_path)

        self.app = app
        self.target = None

#-------------------------------------------------------------------------------
# Primitive schema objects
#-------------------------------------------------------------------------------

class SchemaBase:
    """
    Represents a type-node in a yaml schema
    """
    def is_match(self, data) -> bool:
        """
        Returns True if 'data' is type-compatible with this type-node
        (including its descendants)
        """
        raise NotImplementedError

    def extract(self, ctx: YAMLContext, data):
        """
        Converts 'data' into a more desireable representation if applicable
        """
        return data


class _GenericScalar(SchemaBase):
    _typ = None

    def is_match(self, data) -> bool:
        return isinstance(data, self._typ)


class Boolean(_GenericScalar):
    _typ = bool


class String(_GenericScalar):
    _typ = str


class Integer(_GenericScalar):
    _typ = int


class Float(_GenericScalar):
    _typ = float


class UniformList(SchemaBase):
    """
    List of objects, all of the same type
    """
    def __init__(self, schema: SchemaBase):
        self.schema = schema
    
    def is_match(self, data) -> bool:
        if not isinstance(data, list):
            return False
        
        for el in data:
            if not self.schema.is_match(el):
                return False
        return True
    
    def extract(self, ctx: YAMLContext, data):
        return [self.schema.extract(ctx, el) for el in data]


class Mapping(SchemaBase):
    def __init__(self, schema: OrderedDict):
        """
        Dictionary mapping of objects.

        Schema is represented by a dict of allowable key:value pairs
        
        If key is a string, then it expects a matching key
        Otherwise, if key is a SchemaBase, only the type needs to match.

        Schema key:value pairs are evaluated in order. First one to match is used.
        """
        self.schema = schema


    def _get_matching_schema_entry(self, data_key, data_value):
        for s_key, s_value in self.schema.items():
            # check if data entry's key is a match
            if isinstance(s_key, str):
                if s_key != data_key:
                    continue
            elif isinstance(s_key, SchemaBase):
                if not s_key.is_match(data_key):
                    continue
            else:
                raise TypeError("Expecting schema key to be 'str' or 'SchemaBase'")

            # check if data entry's value is a match
            if not s_value.is_match(data_value):
                continue
            return (s_key, s_value)
        return (None, None)


    def is_match(self, data) -> bool:
        if not isinstance(data, dict):
            return False
        
        for d_key, d_value in data.items():
            s_key, _ = self._get_matching_schema_entry(d_key, d_value)
            if s_key is None:
                return False
        return True


    def extract(self, ctx: YAMLContext, data):
        dout = OrderedDict()
        for d_key, d_value in data.items():
            s_key, s_value = self._get_matching_schema_entry(d_key, d_value)
            if isinstance(s_key, str):
                dout[d_key] = s_value.extract(ctx, d_value)
            else:
                dout[s_key.extract(ctx, d_key)] = s_value.extract(ctx, d_value)
        return dout


class AnyOf(SchemaBase):
    """
    Can match any of the specified schemas
    """
    def __init__(self, schema: list):
        self.schema = schema
    
    def _get_matching_schema(self, data):
        for s in self.schema:
            if s.is_match(data):
                return s
        return None

    def is_match(self, data) -> bool:
        s = self._get_matching_schema(data)
        return s is not None

    def extract(self, ctx: YAMLContext, data):
        s = self._get_matching_schema(data)
        return s.extract(ctx, data)

class Anything(SchemaBase):
    """
    Wildcard. Matches anything
    """
    def is_match(self, data):
        return True


class Tagged(SchemaBase):
    def __init__(self, tag: str, schema):
        self.tag = tag
        self.schema = schema
    
    def is_match(self, data) -> bool:
        if not isinstance(data, TaggedYAMLData):
            return False
        
        if data.tag != self.tag:
            return False
        
        return self.schema.is_match(data.value)

    def extract(self, ctx: YAMLContext, data):
        return self.schema.extract(ctx, data.value)


#-------------------------------------------------------------------------------

class FilePath(String):
    def extract(self, ctx: YAMLContext, data):
        path = super().extract(ctx, data)

        path = os.path.expanduser(path)

        # Keep absolute paths as-is
        if os.path.isabs(path):
            return os.path.normpath(path)
        
        # Extend relative paths off of the YAML file's location
        path = os.path.join(os.path.dirname(ctx.yaml_path), path)
        return os.path.normpath(path)



"""
Regarding defaults:
    Defaults also get loaded via params schema dictionaries
    Defaults do not get injected until way at the end by the Importer itself while
    processing a file
    Reason is that some params may prefer special behavior when combining
        (eg. includes should prepend rather than replace defaults)
"""