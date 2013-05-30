from os.path import isfile, isdir, join

from utils import memoized
import config
from naming import name_fn, fn2spec
from fetch import fetch_index


@memoized
def get_index():
    """
    return the index of packages available on the channels
    """
    channel_urls = config.get_channel_urls()
    return fetch_index(channel_urls)


def app_get_index():
    index = get_index()
    return {fn: info for fn, info in index.iteritems()
            if info.get('type') == 'app'}


def app_missing_packages(fn):
    """
    given the filename of a package, return which packages (and their sizes)
    still need to be downloaded, in order to install the package.  That is,
    the package itself and it's dependencies (unless already in cache).
    Returns a list of tuples (pkg_name, pkg_version, size).
    """
    from resolve import Resolve

    index = get_index()
    r = Resolve(index)
    res = []
    for fn2 in r.solve([fn2spec(fn)]):
        if isfile(join(config.pkgs_dir, fn2[:-8], 'info', 'extracted')):
            continue
        info = index[fn2]
        res.append((info['name'], info['version'], info['size']))
    return res


def app_is_installed(fn):
    name = name_fn(fn)
    return # None or prefix

# It seems to me that we need different types of apps, i.e. apps which
# are preferably installed (or already exist) in existing environments,
# and apps which are more "standalone" (such as firefox).

def app_launch(fn, additional_args=None):
    # serach where app in installed and start it
    return


def app_install(fn):
    import plan

    for i in xrange(1000):
        prefix = join(config.envs_dir, '%s-%03d' % (name_fn(fn), i))
        if not isdir(prefix):
            break

    index = get_index()
    actions = plan.install_actions(prefix, index, [fn2spec(fn)])
    plan.execute_actions(actions, index)
    return prefix


def app_uninstall(fn):
    pass


if __name__ == '__main__':
    from pprint import pprint
    #pprint(missing_packages('twisted-12.3.0-py27_0.tar.bz2'))
    print app_install('twisted-12.3.0-py27_0.tar.bz2')
