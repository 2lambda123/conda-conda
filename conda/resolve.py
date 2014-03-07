from __future__ import print_function, division, absolute_import

import re
import sys
import logging
from itertools import islice, combinations
from collections import defaultdict

from conda import verlib
from conda.utils import memoize
from conda.compat import itervalues, iteritems

log = logging.getLogger(__name__)


class MatchSpec(object):

    def __init__(self, spec):
        self.spec = spec
        parts = spec.split()
        self.strictness = len(parts)
        assert 1 <= self.strictness <= 3
        self.name = parts[0]

        if self.strictness == 2:
            rx = parts[1]
            rx = rx.replace('.', r'\.')
            rx = rx.replace('*', r'.*')
            rx = r'(%s)$' % rx
            self.ver_pat = re.compile(rx)

        elif self.strictness == 3:
            self.ver_build = tuple(parts[1:3])

    def match(self, fn):
        assert fn.endswith('.tar.bz2')
        name, version, build = fn[:-8].rsplit('-', 2)
        if name != self.name:
            return False
        if self.strictness == 2 and self.ver_pat.match(version) is None:
            return False
        if self.strictness == 3 and ((version, build) != self.ver_build):
            return False
        return True

    def to_filename(self):
        if self.strictness == 3:
            return self.name + '-%s-%s.tar.bz2' % self.ver_build
        else:
            return None

    def __eq__(self, other):
        return self.spec == other.spec

    def __hash__(self):
        return hash(self.spec)

    def __repr__(self):
        return 'MatchSpec(%r)' % (self.spec)

    def __str__(self):
        return self.spec


class Package(object):
    """
    The only purpose of this class is to provide package objects which
    are sortable.
    """

    def __init__(self, fn, info):
        self.fn = fn
        self.name = info['name']
        self.version = info['version']
        self.build_number = info['build_number']
        self.build = info['build']
        self.channel = info.get('channel')

        v = self.version
        v = v.replace('rc', '.dev99999')
        if v.endswith('.dev'):
            v += '0'
        try:
            self.norm_version = verlib.NormalizedVersion(v)
        except verlib.IrrationalVersionError:
            self.norm_version = self.version

    # http://python3porting.com/problems.html#unorderable-types-cmp-and-cmp
#     def __cmp__(self, other):
#         if self.name != other.name:
#             raise ValueError('cannot compare packages with different '
#                              'names: %r %r' % (self.fn, other.fn))
#         try:
#             return cmp((self.norm_version, self.build_number),
#                       (other.norm_version, other.build_number))
#         except TypeError:
#             return cmp((self.version, self.build_number),
#                       (other.version, other.build_number))

    def __lt__(self, other):
        if self.name != other.name:
            raise TypeError('cannot compare packages with different '
                             'names: %r %r' % (self.fn, other.fn))
        try:
            return ((self.norm_version, self.build_number, self.build) <
                    (other.norm_version, other.build_number, other.build))
        except TypeError:
            return ((self.version, self.build_number) <
                    (other.version, other.build_number))

    def __eq__(self, other):
        if self.name != other.name:
            raise TypeError('cannot compare packages with different '
                             'names: %r %r' % (self.fn, other.fn))
        try:
            return ((self.norm_version, self.build_number) ==
                    (other.norm_version, other.build_number))
        except TypeError:
            return ((self.version, self.build_number) ==
                    (other.version, other.build_number))

    def __gt__(self, other):
        return not (self.__lt__(other) or self.__eq__(other))

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def __hash__(self):
        try:
            return hash((self.name, self.norm_version, self.build_number))
        except TypeError:
            return hash((self.name, self.version, self.build_number))

    def __repr__(self):
        return '<Package %s>' % self.fn


def min_sat(clauses, max_n=1000):
    """
    Calculate the SAT solutions for the `clauses` for which the number of
    true literals is minimal.  Returned is the list of those solutions.
    When the clauses are unsatisfiable, an empty list is returned.

    This function could be implemented using a Pseudo-Boolean SAT solver,
    which would avoid looping over the SAT solutions, and would therefore
    be much more efficient.  However, for our purpose the current
    implementation is good enough.
    """
    try:
        import pycosat
    except ImportError:
        sys.exit('Error: could not import pycosat (required for dependency '
                 'resolving)')

    min_tl, solutions = sys.maxsize, []
    count = 0
    for sol in pycosat.itersolve(clauses):
        solutions.append(sol)
        count += 1
        if count >= max_n:
            print("Warning, stopping at %s solutions" % count)
            break

    return solutions


class Resolve(object):

    def __init__(self, index):
        self.index = index
        self.groups = defaultdict(list) # map name to list of filenames
        for fn, info in iteritems(index):
            self.groups[info['name']].append(fn)
        self.msd_cache = {}

    def find_matches(self, ms):
        for fn in self.groups[ms.name]:
            if ms.match(fn):
                yield fn

    def ms_depends(self, fn):
        # the reason we don't use @memoize here is to allow resetting the
        # cache using self.msd_cache = {}, which is used during testing
        try:
            res = self.msd_cache[fn]
        except KeyError:
            depends = self.index[fn]['depends']
            res = self.msd_cache[fn] = [MatchSpec(d) for d in depends]
        return res

    @memoize
    def features(self, fn):
        return set(self.index[fn].get('features', '').split())

    @memoize
    def track_features(self, fn):
        return set(self.index[fn].get('track_features', '').split())

    @memoize
    def get_pkgs(self, ms):
        return [Package(fn, self.index[fn]) for fn in self.find_matches(ms)]

    def get_max_dists(self, ms):
        pkgs = self.get_pkgs(ms)

        if not pkgs:
            raise RuntimeError("No packages found matching: %s" % ms)
        maxpkg = max(pkgs)
        for pkg in pkgs:
            if pkg == maxpkg:
                yield pkg.fn

    def all_deps(self, root_fn):
        res = set()

        def add_dependents(fn1):
            for ms in self.ms_depends(fn1):
                for pkg2 in self.get_pkgs(ms):
                    fn2 = pkg2.fn
                    if fn2 in res:
                        continue
                    res.add(fn2)
                    if ms.strictness < 3:
                        add_dependents(fn2)

        add_dependents(root_fn)
        return res

    def gen_clauses(self, v, dists, specs, features):
        groups = defaultdict(list) # map name to list of filenames
        for fn in dists:
            groups[self.index[fn]['name']].append(fn)

        for filenames in itervalues(groups):
            # ensure packages with the same name conflict
            for fn1 in filenames:
                v1 = v[fn1]
                for fn2 in filenames:
                    v2 = v[fn2]
                    if v1 < v2:
                        # NOT (fn1 AND fn2)
                        # e.g. NOT (numpy-1.6 AND numpy-1.7)
                        yield [-v1, -v2]

        for fn1 in dists:
            for ms in self.ms_depends(fn1):
                # ensure dependencies are installed
                # e.g. numpy-1.7 IMPLIES (python-2.7.3 OR python-2.7.4 OR ...)
                clause = [-v[fn1]]
                for fn2 in self.find_matches(ms):
                    if fn2 in dists:
                        clause.append(v[fn2])
                assert len(clause) > 1, '%s %r' % (fn1, ms)
                yield clause

                for feat in features:
                    # ensure that a package (with required name) which has
                    # the feature is installed
                    # e.g. numpy-1.7 IMPLIES (numpy-1.8[mkl] OR numpy-1.7[mkl])
                    clause = [-v[fn1]]
                    for fn2 in groups[ms.name]:
                         if feat in self.features(fn2):
                             clause.append(v[fn2])
                    if len(clause) > 1:
                        yield clause

        for spec in specs:
            ms = MatchSpec(spec)
            # ensure that a matching package with the feature is installed
            for feat in features:
                # numpy-1.7[mkl] OR numpy-1.8[mkl]
                clause = [v[fn] for fn in self.find_matches(ms)
                          if fn in dists and feat in self.features(fn)]
                if len(clause) > 0:
                    yield clause

            # finally, ensure a matching package itself is installed
            # numpy-1.7-py27 OR numpy-1.7-py26 OR numpy-1.7-py33 OR
            # numpy-1.7-py27[mkl] OR ...
            clause = [v[fn] for fn in self.find_matches(ms)
                      if fn in dists]
            assert len(clause) >= 1
            yield clause

    def solve2(self, specs, features, guess=True, return_all=False):
        dists = set()
        for spec in specs:
            for pkg in self.get_pkgs(MatchSpec(spec)):
                if pkg.fn in dists:
                    continue
                dists.update(self.all_deps(pkg.fn))
                dists.add(pkg.fn)

        v = {} # map fn to variable number
        w = {} # map variable number to fn
        for i, fn in enumerate(sorted(dists)):
            v[fn] = i + 1
            w[i + 1] = fn

        clauses = self.gen_clauses(v, dists, specs, features)
        solutions = min_sat(clauses)

        sols = [[w[lit] for lit in sol if lit > 0] for sol in solutions]

        maximal_solutions = self.maximal_sols(sols)

        if len(maximal_solutions) == 0:
            if guess:
                raise RuntimeError("Unsatisfiable package specifications\n" +
                                   self.guess_bad_solve(specs, features))
            raise RuntimeError("Unsatisfiable package specifications")

        if len(maximal_solutions) > 1:
            if return_all:
                return maximal_solutions

            print('Warning:', len(maximal_solutions), "possible package resolutions:")
            for sol in maximal_solutions:
                print('\t', sol)

        return maximal_solutions.pop()

    def guess_bad_solve(self, specs, features):
        # TODO: Check features as well
        hint = []
        # Try to find the largest satisfiable subset
        found = False
        for i in range(len(specs), 0, -1):
            if found:
                break
            for comb in combinations(specs, i):
                try:
                    self.solve2(comb, features, guess=False)
                except RuntimeError:
                    pass
                else:
                    rem = set(specs) - set(comb)
                    rem.discard('conda')
                    if len(rem) == 1:
                        hint.append("%s" % rem.pop())
                    else:
                        hint.append("%s" % ' and '.join(rem))

                    found = True
        if not hint:
            return ''
        if len(hint) == 1:
            return ("Hint: %s has a conflict with the remaining packages" %
                    hint[0])
        return ("""\
Hint: the following combinations of packages create a conflict with the
remaining packages:
  - %s""" % '\n  - '.join(hint))

    def explicit(self, specs):
        """
        Given the specifications, return:
          A. if one explicit specification (strictness=3) is given, and
             all dependencies of this package are explicit as well ->
             return the filenames of those dependencies (as well as the
             explicit specification)
          B. if not one explicit specifications are given ->
             return the filenames of those (not thier dependencies)
          C. None in all other cases
        """
        if len(specs) == 1:
            ms = MatchSpec(specs[0])
            fn = ms.to_filename()
            if fn is None:
                return None
            res = [ms2.to_filename() for ms2 in self.ms_depends(fn)]
            res.append(fn)
        else:
            res = [MatchSpec(spec).to_filename() for spec in specs
                   if spec != 'conda']

        if None in res:
            return None
        res.sort()
        log.debug('explicit(%r) finished' % specs)
        return res

    @memoize
    def sum_matches(self, fn1, fn2):
        return sum(ms.match(fn2) for ms in self.ms_depends(fn1))

    def find_substitute(self, installed, features, fn):
        """
        Find a substitute package for `fn` (given `installed` packages)
        which does *NOT* have `features`.  If found, the substitute will
        have the same package namd and version and its dependencies will
        match the installed packages as closely as possible.
        If no substribute is found, None is returned.
        """
        name, version, unused_build = fn.rsplit('-', 2)
        candidates = {}
        for fn1 in self.get_max_dists(MatchSpec(name + ' ' + version)):
            if self.features(fn1).intersection(features):
                continue
            key = sum(self.sum_matches(fn1, fn2) for fn2 in installed)
            candidates[key] = fn1

        if candidates:
            maxkey = max(candidates)
            return candidates[maxkey]
        else:
            return None

    def installed_features(self, installed):
        """
        Return the set of all features of all `installed` packages,
        """
        res = set()
        for fn in installed:
            try:
                res.update(self.features(fn))
            except KeyError:
                pass
        return res

    def update_with_features(self, fn, features):
        with_features = self.index[fn].get('with_features_depends')
        if with_features is None:
            return
        key = ''
        for fstr in with_features:
            fs = set(fstr.split())
            if fs <= features and len(fs) > len(set(key.split())):
                key = fstr
        if not key:
            return
        d = {ms.name: ms for ms in self.ms_depends(fn)}
        for spec in with_features[key]:
            ms = MatchSpec(spec)
            d[ms.name] = ms
        self.msd_cache[fn] = d.values()

    def solve(self, specs, installed=None, features=None):
        if installed is None:
            installed = []
        if features is None:
            features = self.installed_features(installed)
        for spec in specs:
            ms = MatchSpec(spec)
            for fn in self.get_max_dists(ms):
                features.update(self.track_features(fn))
        log.debug('specs=%r  features=%r' % (specs, features))
        for spec in specs:
            for fn in self.get_max_dists(MatchSpec(spec)):
                self.update_with_features(fn, features)

        return self.explicit(specs) or list(self.solve2(specs, features))

    def maximal_sols(self, sols):
        """
        Return the set of maximal solutions.

        A solution is maximal if there are no solutions > it.
        """
        maxset = set()
        solutions = [tuple([Package(fn, self.index[fn]) for fn in sol]) for sol in sols]
        for sol in solutions:
            newmax = True
            remove = set()
            for e in maxset:
                try:
                    lt = partial_lt(e, sol)
                    if lt:
                        remove.add(e)
                    if not lt:
                        newmax = False
                except TypeError:
                    pass
            maxset -= remove
            if newmax:
                maxset.add(sol)
        return {tuple([pkg.fn for pkg in sol]) for sol in maxset}

def partial_lt(a, b):
    """
    Partial ordering on tuples of packages a and b

    Returns true if each element of a is < each corresponding element of b,
    False if each element of a is > each element of b, and raises TypeError
    otherwise.

    If either has an element that is not in the other, that is ignored for the
    purpose of the comparison.
    """
    a, b = {pkg.name: pkg for pkg in a}, {pkg.name: pkg for pkg in b}
    if a == b:
        return False
    if all(a[i] <= b[i] for i in a if i in b):
        if not any(a[i] < b[i] for i in set(a).intersection(set(b))):
            # a and b are different but all common packages are the same
            # Break the tie by finding smaller packages
            if len(a) > len(b):
                return True
            elif len(a) < len(b):
                return False
            raise TypeError("%s and %s are not comparable" % (a, b))
        return True
    if all(a[i] >= b[i] for i in a if i in b):
        # The case where a and b are different but all common packages are the
        # same is already handled above
        return False
    raise TypeError("%s and %s are not comparable" % (a, b))

if __name__ == '__main__':
    import json
    from pprint import pprint
    from optparse import OptionParser
    from conda.cli.common import arg2spec

    with open('../tests/index.json') as fi:
        r = Resolve(json.load(fi))

    p = OptionParser(usage="usage: %prog [options] SPEC(s)")
    p.add_option("--mkl", action="store_true")
    opts, args = p.parse_args()

    features = set(['mkl']) if opts.mkl else set()
    specs = [arg2spec(arg) for arg in args]
    pprint(r.solve(specs, [], features))
