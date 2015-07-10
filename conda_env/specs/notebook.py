try:
    from IPython import nbformat
except ImportError:
    nbformat = None
from ..env import Environment


class NotebookSpec(object):
    msg = None

    def __init__(self, name=None, **kwargs):
        self.name = name

    def can_handle(self):
        try:
            self.nb = nbformat.reader.reads(open(self.name).read())
            return 'environment' in self.nb['metadata']
        except AttributeError:
            self.msg = "Please install IPython notebook"
        except IOError:
            self.msg = "{} does not exist o can't be accessed".format(self.name)
        except (nbformat.reader.NotJSONError, KeyError) as e:
            print(e)
            self.msg = "{} does not looks like a notebook file".format(self.name)
        return False

    @property
    def environment(self):
        return Environment(**self.nb['metadata']['environment'])
