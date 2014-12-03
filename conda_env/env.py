from __future__ import absolute_import, print_function
from collections import OrderedDict
from copy import copy
import os

# TODO This should never have to import from conda.cli
from conda.cli import common
from conda.cli import main_list
from conda import install

from . import exceptions
from . import yaml


def load_from_directory(directory):
    """Load and return an ``Environment`` from a given ``directory``"""
    files = ['environment.yml', 'environment.yaml']
    while True:
        for f in files:
            try:
                return from_file(os.path.join(directory, f))
            except exceptions.EnvironmentFileNotFound:
                pass
        old_directory = directory
        directory = os.path.dirname(directory)
        if directory == old_directory:
            break
    raise exceptions.EnvironmentFileNotFound(files[0])


# TODO This should lean more on conda instead of divining it from the outside
# TODO tests!!!
def from_environment(name, prefix):
    installed = install.linked(prefix)
    conda_pkgs = copy(installed)
    # json=True hides the output, data is added to installed
    main_list.add_pip_installed(prefix, installed, json=True)

    pip_pkgs = sorted(installed - conda_pkgs)

    dependencies = ['='.join(a.rsplit('-', 2)) for a in sorted(conda_pkgs)]
    if len(pip_pkgs) > 0:
        dependencies.append({'pip': ['=='.join(a.rsplit('-', 2)[:2]) for a in pip_pkgs]})

    return Environment(name=name, raw_dependencies=dependencies)


def from_file(filename):
    if not os.path.exists(filename):
        raise exceptions.EnvironmentFileNotFound(filename)
    with open(filename, 'rb') as fp:
        data = yaml.load(fp)
    if 'dependencies' in data:
        data['raw_dependencies'] = data['dependencies']
        del data['dependencies']
    return Environment(filename=filename, **data)


class Environment(object):
    def __init__(self, name=None, filename=None, channels=None,
                 raw_dependencies=None):
        self.name = name
        self.filename = filename
        self._dependencies = None
        self._parsed = False

        if raw_dependencies is None:
            raw_dependencies = {}
        self.raw_dependencies = raw_dependencies

        if channels is None:
            channels = []
        self.channels = channels

    @property
    def dependencies(self):
        if self._dependencies is None:
            self.parse()
        return self._dependencies

    def add_dependency(self, package_name):
        self.raw_dependencies.append(package_name)
        self._dependencies = None

    def to_dict(self):
        d = yaml.dict([('name', self.name)])
        if self.channels:
            d['channels'] = self.channels
        if self.raw_dependencies:
            d['raw_dependencies'] = self.raw_dependencies
        return d

    def to_yaml(self, stream=None):
        d = self.to_dict()
        if 'raw_dependencies' in d:
            d['dependencies'] = d['raw_dependencies']
            del d['raw_dependencies']
        if stream is None:
            return unicode(yaml.dump(d, default_flow_style=False))
        else:
            yaml.dump(d, default_flow_style=False, stream=stream)

    def parse(self):
        if not self.raw_dependencies:
            self._dependencies = []
            return

        self._dependencies = OrderedDict([('conda', [])])

        for line in self.raw_dependencies:
            if type(line) is dict:
                self._dependencies.update(line)
            else:
                self._dependencies['conda'].append(common.spec_from_line(line))

    def save(self):
        with open(self.filename, "wb") as fp:
            self.to_yaml(stream=fp)
