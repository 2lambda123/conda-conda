# (c) 2012 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.
''' The constraints module provides a variety of package `constraint` classes that
can be used to search and match packages in the package index.

'''


class PackageConstraint(object):
    ''' Base class for specific PackageConstraint objects that match packages with
    specified criteria.

    '''
    def match(self, pkg):
        '''
        match criteria against package info


        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            whether the specified package matches this constraint

        '''
        raise NotImplementedError()
    def __hash__(self):
        return hash(str(self))


class AllOf(PackageConstraint):
    ''' logical AND for matching multiple constraints

    Parameters
    ----------
    *constraints : :py:class:`PackageConstraint <conda.constraints.PackageConstraint>` objects
        package constraints to AND together


    '''
    def __init__(self, *constraints):
        self._constraints = tuple(set(constraints))
    def __str__(self):
        return 'all_of[%s]' % ', '.join(str(c) for c in self._constraints)
    def __repr__(self):
        return 'all_of[%s]' % ', '.join(str(c) for c in self._constraints)
    def __cmp__(self, other):
        return cmp(self._constraints, other._constraints)
    def match(self, pkg):
        ''' Match if a package matches all the specified constraints

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if all of the `constraints` match, False otherwise

        '''
        for constraint in self._constraints:
            if not pkg.matches(constraint): return False
        return True


class AnyOf(PackageConstraint):
    ''' logical OR for matching multiple constraints

    Parameters
    ----------
    *constraints : :py:class:`PackageConstraint <conda.constraints.PackageConstraint>` objects
        package constraints to OR together

    '''
    def __init__(self, *constraints):
        self._constraints = tuple(set(constraints))
    def __str__(self):
        return 'AnyOf[%s]' % ', '.join(str(c) for c in self._constraints)
    def __repr__(self):
        return 'AnyOf[%s]' % ', '.join(str(c) for c in self._constraints)
    def __cmp__(self, other):
        return cmp(self._constraints, other._constraints)
    def match(self, pkg):
        ''' Match if a package matches any of the specified constraints

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if any of the `constraints` match, False otherwise

        '''
        for constraint in self._constraints:
            if pkg.matches(constraint): return True
        return False


class Negate(PackageConstraint):
    ''' logical NOT for matching constraints

    Parameters
    ----------
    constraint : :py:class:`PackageConstraint <conda.constraints.PackageConstraint>` object
        package constraint to Negate

    '''
    def __init__(self, constraint):
        self._constraint = constraint
    def __str__(self):
        return 'Negate[%s]' % str(self._constraint)
    def __repr__(self):
        return 'Negate[%s]' % str(self._constraint)
    def __cmp__(self, other):
        return cmp(self._constraint, other._constraint)
    def match(self, pkg):
        ''' Match if a package does NOT match the specified constraint

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `constraint` does *not* match, False otherwise

        '''
        return not pkg.matches(self._constraint)


class Named(PackageConstraint):
    ''' constraint for matching package names

    Parameters
    ----------
    name : str
        :ref:`Package name <package_name>` to match against

    '''
    def __init__(self, name):
        self._name = name
    def __str__(self):
        return 'Named[%s]' % self._name
    def __repr__(self):
        return 'Named[%s]' % self._name
    def __cmp__(self, other):
        return cmp(self._name, other._name)
    def match(self, pkg):
        ''' Match if a package has the specified name

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if the package name matches, False otherwise

        '''
        return pkg.name == self._name


class Channel(PackageConstraint):
    ''' constraint for matching package channels

    Parameters
    ----------
    name : str
        :ref:`channel <channel>` to match against

    '''
    def __init__(self, channel):
        self._channel = channel
    def __str__(self):
        return 'Channel[%s]' % self._channel
    def __repr__(self):
        return 'Channel[%s]' % self._channel
    def __cmp__(self, other):
        return cmp(self._channel, other._channel)
    def match(self, pkg):
        ''' Match if a package has the specified channel

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if the package channel matches, False otherwise

        '''
        return self._channel in pkg.channel


class StrictRequires(PackageConstraint):
    ''' constraint for strictly matching package dependencies

    Parameters
    ----------
    req : :py:class:`Package_spec <conda.package_spec.package_spec>` object
        package specification to match against

    '''
    def __init__(self, req):
        self._req = req
    def __str__(self):
        return 'StrictRequires[%s]' % str(self._req)
    def __repr__(self):
        return 'StrictRequires[%s]' % str(self._req)
    def __cmp__(self, other):
        return cmp(self._req, other._req)
    def match(self, pkg):
        ''' Match if a package contains a specified requirement

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `req` is an exact requirement for `pkg`, False otherwise

        '''
        # package never requires itself
        if pkg.name == self._req.name: return False
        for req in pkg.requires:
            if req.name == self._req.name and req.version == self._req.version:
                return True
        return False


class Requires(PackageConstraint):
    ''' constraint for matching package dependencies

    Parameters
    ----------
    req : :py:class:`Package_spec <conda.package_spec.package_spec>` object
        package specification to match against

    '''
    def __init__(self, req):
        self._req = req
    def __str__(self):
        return 'Requires[%s]' % str(self._req)
    def __repr__(self):
        return 'Requires[%s]' % str(self._req)
    def __cmp__(self, other):
        return cmp(self._req, other._req)
    def match(self, pkg):
        ''' Match if a `req` is compatible with the requirements for `pkg`

        .. note:: matching includes the case when `pkg` has no requirement at all for the package specified by `req`

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `req` is compatible requirement for `pkg`, has False otherwise

        '''
        # package never Requires itself
        if pkg.name == self._req.name: return False
        vlen = len(self._req.version.version)
        for req in pkg.requires:
            if req.name == self._req.name and req.version.version[:vlen] != self._req.version.version[:vlen]:
                return False
        return True


class Satisfies(PackageConstraint):
    ''' constraint for matching whether a package satisfies a package specification

    Parameters
    ----------
    req : :py:class:`Package_spec <conda.package_spec.package_spec>` object
        package specification to match against

    '''
    def __init__(self, req):
        self._req = req
    def __str__(self):
        return 'Satisfies[%s]' % str(self._req)
    def __repr__(self):
        return 'Satisfies[%s]' % str(self._req)
    def __cmp__(self, other):
        return cmp(self._req, other._req)
    def match(self, pkg):
        ''' Match if a package satisfies the specified requirement

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `pkg` is compatible with the package specification `req`

        '''
        if self._req.name != pkg.name: return False
        if not self._req.version: return True
        vlen = len(self._req.version.version)
        try:
            return self._req.version.version[:vlen] == pkg.version.version[:vlen]
        except:
            return False


class PackageVersion(PackageConstraint):
    ''' constraint for matching package versions

    Parameters
    ----------
    req : :py:class:`Package_spec <conda.package.Package>` object
        package to match against

    '''
    def __init__(self, pkg):
        self._pkg = pkg
    def __str__(self):
        return 'PackageVersion[%s]' % str(self._pkg)
    def __repr__(self):
        return 'PackageVersion[%s]' % str(self._pkg)
    def __cmp__(self, other):
        return cmp(self._pkg, other._pkg)
    def match(self, pkg):
        ''' Match if specific package versions (excluding build) agree

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `pkg` matches the specified package version exactly, False otherwise

        '''
        return self._pkg.name == pkg.name and self._pkg.version == pkg.version


class ExactPackage(PackageConstraint):
    ''' constraint for matching exact packages

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match against

    '''
    def __init__(self, pkg):
        self._pkg = pkg
    def __str__(self):
        return 'build_version[%s]' % str(self._pkg)
    def __repr__(self):
        return 'build_version[%s]' % str(self._pkg)
    def __cmp__(self, other):
        return cmp(self._pkg, other._pkg)
    def match(self, pkg):
        ''' Match if specific package versions (including build) agree

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True if `pkg` matches the specified package exactly, False otherwise

        '''
        return self._pkg == pkg


class Wildcard(PackageConstraint):
    ''' constraint that always matches everything

    '''
    def __str__(self):
        return 'Wildcard'
    def __repr__(self):
        return 'Wildcard'
    def __cmp__(self, other):
        return 0
    def match(self, pkg):
        ''' Match all packages

        Parameters
        ----------
        pkg : :py:class:`Package <conda.package.Package>` object
            package to match

        Returns
        -------
        matches : bool
            True

        '''
        return True
