# Copyright 2014, 2015 The ODL development group
#
# This file is part of ODL.
#
# ODL is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ODL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ODL.  If not, see <http://www.gnu.org/licenses/>.

"""Spaces of functions with common domain and range.

TODO: document properly
"""

# Imports for common Python 2/3 codebase
from __future__ import print_function, division, absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import super

# External imports
import numpy as np
from functools import wraps
from itertools import product

# ODL imports
from odl.operator.operator import Operator
from odl.set.domain import IntervalProd
from odl.set.sets import RealNumbers, ComplexNumbers, Set
from odl.set.space import LinearSpace
from odl.util.utility import (is_valid_input_array, is_valid_input_meshgrid,
                              meshgrid_input_order, vecs_from_meshgrid)


__all__ = ('FunctionSet', 'FunctionSpace')


def _apply_not_impl(*_):
    """Dummy function to be used when apply function is not given."""
    raise NotImplementedError('no `_apply` method defined.')


def enforce_defaults_as_kwargs(func):
    """Decorator forcing args with defaults to be passed by keyword."""
    @wraps(func)
    def kwargs_wrapper(*args, **kwargs):
        from inspect import getargspec

        argspec = getargspec(func)
        func_args = argspec.args
        func_defs = argspec.defaults
        if len(args) != len(func_args) - len(func_defs):
            # Expected exactly those positional arguments without defaults
            raise ValueError('{} takes exactly {} positional argument ({} '
                             'given). Positional arguments with defaults must '
                             'be passed by keyword.'
                             ''.format(func.__name__,
                                       len(func_args) - len(func_defs),
                                       len(args)))

        return func(*args, **kwargs)
    return kwargs_wrapper


def vectorize(dtype, outarg='none'):
    """Vectorization decorator for our input parameter pattern.

    The wrapped function must be callable with one positional
    parameter. Keyword arguments are passed through, hence positional
    arguments with defaults can either be left out or passed by keyword,
    but not by position.

    Parameters
    ----------
    dtype : object
        Data type of the output array. Needs to be understood by the
        `numpy.dtype` function.
    outarg : {'none', 'positional', 'optional'}
        Type of the output argument of the decorated function for
        in-place evaluation

        'none': No output parameter. This is the default.
        Resulting argspec: `func(x, **kwargs)`
        Returns: the new array

        'positional': Required argument `out` at second position.
        Resulting argspec: `func(x, out=None, **kwargs)`
        Returns: `out`

        'optional': optional argument `out` with default `None`.
        Resulting argspec: `func(x, out=None, **kwargs)`
        Returns: `out` if it is not `None` otherwise a new array

    Note
    ----
    For `outarg` not equal to 'none', the decorated function returns
    the array given as `out` argument if it is not `None`.

    Examples
    --------
    Vectorize a function summing the x and y coordinates:

    >>> @vectorize(dtype=float)
    ... def sum(x):
    ...     return x[0] + x[1]

    This corresponds to (but is much slower than)

    >>> def sum_vec(x):
    ...     x0, x1 = x
    ...     return x0 + x1

    Both versions work for arrays and meshgrids:

    >>> x = np.arange(10, dtype=float).reshape((2, 5))
    >>> np.array_equal(sum(x), sum_vec(x))
    True

    >>> x = y = np.linspace(0, 1, 5)
    >>> mg_sparse = np.meshgrid(x, y, indexing='ij', sparse=True)
    >>> np.array_equal(sum(mg_sparse), sum_vec(mg_sparse))
    True
    >>> mg_dense = np.meshgrid(x, y, indexing='ij', sparse=False)
    >>> np.array_equal(sum(mg_dense), sum_vec(mg_dense))
    True

    With output parameter:

    >>> @vectorize(dtype=float, outarg='positional')
    ... def sum(x, r=0):
    ...     return x[0] + x[1] + r
    >>> x = np.arange(10, dtype=float).reshape((2, 5))
    >>> out = np.empty(5, dtype=float)
    >>> sum(x, out, r=2)  # returns out
    array([  7.,   9.,  11.,  13.,  15.])
    """
    def vect_decorator(func):
        def _vect_wrapper(x, out, **kwargs):
            print('at top: ', x, out)
            if isinstance(x, np.ndarray):  # array
                if x.ndim == 1:
                    dim = 1
                elif x.ndim == 2:
                    dim = len(x)
                    if dim == 1:
                        x = x.squeeze()
                else:
                    raise ValueError('only 1- or 2-dimensional arrays '
                                     'supported.')
            else:  # meshgrid
                dim = len(x)
                if dim == 1:
                    x = x[0]
            print('dim = ', dim)
            if dim == 1:
                if out is None:
                    out = np.empty(x.size, dtype=dtype)
                for i, xi in enumerate(x):
                    print(i, xi)
                    out[i] = func(xi, **kwargs)
                return out
            else:
                if is_valid_input_array(x, dim):
                    print(x.shape)
                    if out is None:
                        out = np.empty(x.shape[1], dtype=dtype)
                    for i, pt in enumerate(x.T):
                        print(i, pt)
                        out[i] = func(pt, **kwargs)
                    return out
                elif is_valid_input_meshgrid(x, dim):
                    order = meshgrid_input_order(x)
                    if out is None:
                        out_shape = np.broadcast(*x).shape
                        out = np.empty(out_shape, dtype=dtype, order=order)

                    # TODO: find a better way to iterate
                    vecs = vecs_from_meshgrid(x, order=order)
                    for i, pt in enumerate(product(*vecs)):
                        out.flat[i] = func(pt, **kwargs)
                    return out
                else:
                    if out is None:
                        try:
                            return func(x)
                        except (TypeError, ValueError, IndexError):
                            raise TypeError('invalid vectorized input type.')
                    else:
                        raise TypeError('invalid vectorized input type.')

        @wraps(func)
        def vect_wrapper_no_out(x, **kwargs):
            if 'out' in kwargs:
                raise TypeError("{}() got an unexpected keyword 'out'."
                                "".format(func.__name__))
            return _vect_wrapper(x, None, **kwargs)

        @wraps(func)
        def vect_wrapper_pos_out(x, out, **kwargs):
            if out is None:
                raise ValueError('output parameter cannot be `None`.')
            return _vect_wrapper(x, out, **kwargs)

        @wraps(func)
        def vect_wrapper_opt_out(x, out=None, **kwargs):
            return _vect_wrapper(x, out, **kwargs)

        outarg_ = str(outarg).lower()
        if outarg_ not in ('none', 'positional', 'optional'):
            raise ValueError('output arg type {!r} not understood.'
                             ''.format(outarg))

        if outarg_ == 'none':
            return vect_wrapper_no_out
        elif outarg_ == 'positional':
            return vect_wrapper_pos_out
        else:
            return vect_wrapper_opt_out
    return vect_decorator


class FunctionSet(Set):

    """A general set of functions with common domain and range."""

    def __init__(self, domain, range):
        """Initialize a new instance.

        Parameters
        ----------
        domain : `Set`
            The domain of the functions.
        range : `Set`
            The range of the functions.
        """
        if not isinstance(domain, Set):
            raise TypeError('domain {!r} not a `Set` instance.'.format(domain))

        if not isinstance(range, Set):
            raise TypeError('range {!r} not a `Set` instance.'.format(range))

        self._domain = domain
        self._range = range

    @property
    def domain(self):
        """Common domain of all functions in this set."""
        return self._domain

    @property
    def range(self):
        """Common range of all functions in this set."""
        return self._range

    # TODO: use inspect to get argument spec and skip fapply if fcall has an
    # output optional parameter?
    # TODO: document how vectorization works
    def element(self, fcall, fapply=None, vectorized=True):
        """Create a `FunctionSet` element.

        Parameters
        ----------
        fcall : callable
            The actual instruction for out-of-place evaluation. If
            `fcall` is a `FunctionSet.Vector`, its `_call`, `_apply`
            and `vectorized` are used for initialization unless
            explicitly given
        fapply : callable, optional
            The actual instruction for in-place evaluation
        vectorized : bool
            Whether or not the function supports vectorized
            evaluation.

        Returns
        -------
        element : `FunctionSet.Vector`
            The new element created from `fcall` and `fapply`

        See also
        --------
        discr.grid.TensorGrid.meshgrid : efficient grids for function
        evaluation
        """
        if isinstance(fcall, self.Vector):  # no double wrapping
            if fapply is None:
                if vectorized == fcall.vectorized:
                    return fcall
                else:
                    vectorized = fcall.vectorized
                    fapply = fcall._apply
                    fcall = fcall._call
                    return self.Vector(self, fcall, fapply,
                                       vectorized=vectorized)
        else:
            return self.Vector(self, fcall, fapply,
                               vectorized=vectorized)

    def __eq__(self, other):
        """`s.__eq__(other) <==> s == other`.

        Returns
        -------
        equals : `bool`
            `True` if `other` is a `FunctionSet` with same `domain`
            and `range`, `False` otherwise.
        """
        if other is self:
            return True

        return (isinstance(other, FunctionSet) and
                self.domain == other.domain and
                self.range == other.range)

    def __contains__(self, other):
        """`s.__contains__(other) <==> other in s`.

        Returns
        -------
        equals : `bool`
            `True` if `other` is a `FunctionSet.Vector` whose `space`
            attribute equals this space, `False` otherwise.
        """
        return (isinstance(other, FunctionSet.Vector) and
                self == other.space)

    def __repr__(self):
        """`s.__repr__() <==> repr(s)`."""
        return '{}({!r}, {!r})'.format(self.__class__.__name__,
                                       self.domain, self.range)

    def __str__(self):
        """`s.__str__() <==> str(s)`."""
        return '{}({}, {})'.format(self.__class__.__name__,
                                   self.domain, self.range)

    class Vector(Operator):

        """Representation of a `FunctionSet` element."""

        def __init__(self, fset, fcall, fapply=None, vectorized=True):
            """Initialize a new instance.

            Parameters
            ----------
            fset : `FunctionSet`
                The set of functions this element lives in
            fcall : callable
                The actual instruction for out-of-place evaluation. If
                `fcall` is a `FunctionSet.Vector`, its `_call`, `_apply`
                and `vectorized` are used for initialization unless
                explicitly given as arguments
            fapply : callable, optional
                The actual instruction for in-place evaluation. This is
                possible only for vectorized functions.
            vectorized : bool
                Whether or not the function supports vectorized
                evaluation.

            See also
            --------
            discr.grid.TensorGrid.meshgrid : efficient grids for
            function evaluation
            """
            if not isinstance(fset, FunctionSet):
                raise TypeError('function set {!r} is not a `FunctionSet` '
                                'instance.'.format(fset))
            if not callable(fcall):
                raise TypeError('call function {} is not callable.'
                                ''.format(fcall))
            if fapply is not None and not callable(fapply):
                raise TypeError('apply function {} is not callable.'
                                ''.format(fapply))
            self._vectorized = bool(vectorized)
            if not self._vectorized and fapply is not None:
                raise ValueError('in-place function evaluation only possible '
                                 'for vectorized functions.')
            # TODO: is that really needed? Actually just for bounds_check..
            if (self._vectorized and
                    not isinstance(fset.domain, IntervalProd)):
                raise TypeError('vectorization requires the function set '
                                'domain to be an `IntervalProd` instance, '
                                'got {!r}.'.format(fset.domain))

            super().__init__(fset.domain, fset.range, linear=False)
            self._space = fset
            self._call = fcall
            self._apply = fapply if fapply is not None else _apply_not_impl

        @property
        def space(self):
            """Return `space` attribute."""
            return self._space

        @property
        def domain(self):
            """The function domain (abstract in `Operator`)."""
            return self.space.domain

        @property
        def range(self):
            """The function range (abstract in `Operator`)."""
            return self.space.range

        @property
        def vectorized(self):
            """Whether this function supports vectorized evaluation."""
            return self._vectorized

        # TODO: pass kwargs on to function
        def __call__(self, x, out=None, **kwargs):
            """Out-of-place evaluation.

            Parameters
            ----------
            x : object
                Input argument for the function evaluation. Conditions
                on `x` depend on vectorization:

                `False` : `x` must be a domain element

                `True` : `x` must be a `numpy.ndarray` with shape
                `(d, N)`, where `d` is the number of dimensions of
                the function domain
                OR
                `x` is a sequence of `numpy.ndarray` with length
                `space.ndim`, and the arrays can be broadcast
                against each other.

            out : `numpy.ndarray`, optional
                Output argument holding the result of the function
                evaluation, can only be used for vectorized
                functions. Its shape must be equal to
                `np.broadcast(*x).shape`.
                If `out` is given, it is returned.

            kwargs : {'vec_bounds_check'}
                'bounds_check' : bool
                    Whether or not to check if all input points lie in
                    the function domain. For vectorized evaluation,
                    this requires the domain to implement
                    `contains_all`.

                    Default: `True`

            Returns
            -------
            out : range element or array of elements
                Result of the function evaluation

            Raises
            ------
            TypeError
                If `x` is not a valid vectorized evaluation argument

                If `out` is not a range element or a `numpy.ndarray`
                of range elements

            ValueError
                If evaluation points fall outside the valid domain
            """
            vec_bounds_check = kwargs.pop('vec_bounds_check', True)
            scalar_out = False
            if self.vectorized:
                if x in self.domain:  # Allow also non-vectorized evaluation
                    x = np.atleast_2d(x).T  # make a (d, 1) array
                    scalar_out = (out is None)

                if is_valid_input_array(x, self.domain.ndim):
                    out_shape = (x.shape[1],)
                elif is_valid_input_meshgrid(x, self.domain.ndim):
                    if self.domain.ndim == 1:
                        out_shape = (x[0].shape[1],)
                    else:
                        out_shape = np.broadcast(*x).shape
                elif x in self.domain:  # Allow also non-vectorized evaluation
                    x = np.atleast_2d(x).T  # make a (d, 1) array
                else:
                    raise TypeError('argument {!r} not a valid vectorized '
                                    'input. Expected an element of the domain '
                                    '{dom}, a ({dom.ndim}, n) array '
                                    'or a length-{dom.ndim} meshgrid sequence.'
                                    ''.format(x, dom=self.domain))

                out_shape = np.broadcast(*x).shape

                if vec_bounds_check:
                    if not self.domain.contains_all(x):
                        raise ValueError('input contains points outside '
                                         'the domain {}.'.format(self.domain))
            else:  # not self.vectorized
                if x not in self.domain:
                    raise TypeError('input {!r} not in domain '
                                    '{}.'.format(x, self.domain))

            if out is None:
                out = self._call(x)
                if self.vectorized:
                    if out.shape != out_shape:
                        raise ValueError('output shape {} not equal to shape '
                                         '{} expected from input.'
                                         ''.format(out.shape, out_shape))
                    if vec_bounds_check:
                        if not self.range.contains_all(out):
                            raise ValueError('output contains points outside '
                                             'the range {}.'
                                             ''.format(self.domain))
            else:  # out is not None
                if self.vectorized:
                    if not isinstance(out, np.ndarray):
                        raise TypeError('output {!r} not a `numpy.ndarray` '
                                        'instance.')
                    if out.shape != out_shape:
                        raise ValueError('output shape {} not equal to shape '
                                         '{} expected from input.'
                                         ''.format(out.shape, out_shape))
                    self._apply(x, out)
                    if vec_bounds_check:
                        if not self.range.contains_all(out):
                            raise ValueError('output contains points outside '
                                             'the range {}.'
                                             ''.format(self.domain))
                else:  # not self.vectorized
                    raise ValueError('output parameter can only be specified '
                                     'for vectorized functions.')

            return out[0] if scalar_out else out

        def assign(self, other):
            """Assign `other` to this vector.

            This is implemented without `lincomb` to ensure that
            `vec == other` evaluates to `True` after
            `vec.assign(other)`.
            """
            if other not in self.space:
                raise TypeError('vector {!r} is not an element of the space '
                                '{} of this vector.'
                                ''.format(other, self.space))
            self._call = other._call
            self._apply = other._apply
            self._vectorized = other.vectorized

        def copy(self):
            """Create an identical (deep) copy of this vector."""
            result = self.space.element()
            result.assign(self)
            return result

        def __eq__(self, other):
            """`vec.__eq__(other) <==> vec == other`.

            Returns
            -------
            equals : `bool`
                `True` if `other` is a `FunctionSet.Vector` with
                `other.space` equal to this vector's space and
                the call and apply implementations of `other` and
                this vector are equal. `False` otherwise.
            """
            if other is self:
                return True

            return (isinstance(other, FunctionSet.Vector) and
                    self.space == other.space and
                    self._call == other._call and
                    self._apply == other._apply and
                    self.vectorized == other.vectorized)

        def __ne__(self, other):
            """`vec.__ne__(other) <==> vec != other`"""
            return not self.__eq__(other)

        def __str__(self):
            return str(self._call)  # TODO: better solution?

        def __repr__(self):
            inner_fstr = '{!r}'
            if self._apply is not None:
                inner_fstr += ', fapply={fapply!r}'
            if not self.vectorized:
                inner_fstr += ', vectorized=False'

            inner_str = inner_fstr.format(self._call, fapply=self._apply)

            return '{!r}.element({})'.format(self.space, inner_str)


class FunctionSpace(FunctionSet, LinearSpace):

    """A vector space of functions."""

    def __init__(self, domain, field):
        """Initialize a new instance.

        Parameters
        ----------
        domain : `Set`
            The domain of the functions.
        field : `RealNumbers` or `ComplexNumbers`
            The range of the functions.
        """
        if not isinstance(domain, Set):
            raise TypeError('domain {!r} not a `Set` instance.'.format(domain))
        if not isinstance(field, (RealNumbers, ComplexNumbers)):
            raise TypeError('field {!r} not a `RealNumbers` or '
                            '`ComplexNumbers` instance.'.format(field))

        super().__init__(domain, field)
        self._field = field

    @property
    def field(self):
        """Return `field` attribute."""
        return self._field

    def element(self, fcall=None, fapply=None, vectorized=True):
        """Create a `FunctionSet` element.

        Parameters
        ----------
        fcall : callable, optional
            The actual instruction for out-of-place evaluation. If
            `fcall` is a `FunctionSet.Vector`, its `_call`, `_apply`
            and `vectorized` are used for initialization unless
            explicitly given.
            If `fcall` is `None`, the zero function is created.
        fapply : callable, optional
            The actual instruction for in-place evaluation
        vectorized : bool
            Whether or not the function supports vectorized
            evaluation.

        Returns
        -------
        `element` : `FunctionSpace.Vector`
            The new element.
        """
        if fcall is None:
            return self.zero(vectorized=vectorized)
        else:
            return super().element(fcall, fapply, vectorized=vectorized)

    def zero(self, vectorized=True):
        """The function mapping everything to zero.

        Since `lincomb` is slow, we implement this function directly.
        This function is the additive unit in the function space.

        Parameters
        ----------
        vectorized : bool
            Whether or not the function supports vectorized
            evaluation.
        """
        dtype = complex if self.field == ComplexNumbers() else float
        vectorized = bool(vectorized)

        def zero_novec(_):
            """The zero function, non-vectorized."""
            return dtype(0.0)

        def zero_vec(x):
            """The zero function, vectorized."""
            if is_valid_input_meshgrid(x, self.domain.ndim):
                order = meshgrid_input_order(x)
            else:
                order = 'C'

            bcast = np.broadcast(*x)
            return np.zeros(bcast.shape, dtype=dtype, order=order)

        def zero_apply(_, out):
            """The in-place zero function."""
            out.fill(0.0)
            return out

        if vectorized:
            zero_func = zero_vec
            zero_a = zero_apply
        else:
            zero_func = zero_novec
            zero_a = None
        return self.element(zero_func, zero_a, vectorized=vectorized)

    def one(self, vectorized=True):
        """The function mapping everything to one.

        This function is the multiplicative unit in the function space.

        Parameters
        ----------
        vectorized : bool
            Whether or not the function supports vectorized
            evaluation.
        """
        dtype = complex if self.field == ComplexNumbers() else float
        vectorized = bool(vectorized)

        def one_novec(_):
            """The one function, non-vectorized."""
            return dtype(1.0)

        def one_vec(x):
            """The one function, vectorized."""
            if is_valid_input_meshgrid(x, self.domain.ndim):
                order = meshgrid_input_order(x)
            else:
                order = 'C'

            bcast = np.broadcast(*x)
            return np.ones(bcast.shape, dtype=dtype, order=order)

        def one_apply(_, out):
            """The in-place one function."""
            out.fill(0.0)
            return out

        if vectorized:
            one_func = one_vec
            one_a = one_apply
        else:
            one_func = one_novec
            one_a = None
        return self.element(one_func, one_a, vectorized=vectorized)

    def __eq__(self, other):
        """`s.__eq__(other) <==> s == other`.

        Returns
        -------
        equals : `bool`
            `True` if `other` is a `FunctionSpace` with same `domain`
            and `range`, `False` otherwise.
        """
        if other is self:
            return True

        return (isinstance(other, FunctionSpace) and
                self.domain == other.domain and
                self.range == other.range)

    def _lincomb(self, a, x1, b, x2, out):
        """Raw linear combination of `x1` and `x2`.

        Note
        ----
        The additions and multiplications are implemented via simple
        Python functions, so non-vectorized versions are slow.
        """
        # Store to allow aliasing
        x1_call = x1._call
        x1_apply = x1._apply
        x2_call = x2._call
        x2_apply = x2._apply

        lincomb_vect = x1.vectorized or x2.vectorized
        dtype = complex if self.field == ComplexNumbers() else float
        if lincomb_vect and not x1.vectorized:
            x1_call = vectorize(dtype, outarg='none')(x1_call)
            x1_apply = vectorize(dtype, outarg='positional')(x1_call)
        if lincomb_vect and not x2.vectorized:
            x2_call = vectorize(dtype, outarg='none')(x2_call)
            x2_apply = vectorize(dtype, outarg='positional')(x2_call)

        def lincomb_call(x):
            """Linear combination, call version."""
            # Due to vectorization, at least one call must be made to
            # ensure the correct final shape. The rest is optimized as
            # far as possible.
            if a == 0 and b != 0:
                out = x2_call(x)
                if b != 1:
                    out *= b
            elif b == 0:  # Contains the case a == 0
                out = x1_call(x)
                if a != 1:
                    out *= a
            else:
                out = x1_call(x)
                if a != 1:
                    out *= a
                tmp = x2_call(x)
                if b != 1:
                    tmp *= b
                out += tmp
            return out

        def lincomb_apply(x, out):
            """Linear combination, apply version."""
            if not isinstance(out, np.ndarray):
                raise TypeError('in-place evaluation only possible if output '
                                'is of type `numpy.ndarray`.')
            if a == 0 and b == 0:
                out *= 0
            elif a == 0 and b != 0:
                x2_apply(x, out)
                if b != 1:
                    out *= b
            elif b == 0 and a != 0:
                x1_apply(x, out)
                if a != 1:
                    out *= a
            else:
                tmp = np.empty_like(out)
                x1_apply(x, out)
                x2_apply(x, tmp)
                if a != 1:
                    out *= a
                if b != 1:
                    tmp *= b
                out += tmp
            return out

        out._call = lincomb_call
        out._vectorized = lincomb_vect
        # If one of the summands' apply method is undefined, it will not be
        # defined in the result either
        if _apply_not_impl in (x1_apply, x2_apply):
            out._apply = _apply_not_impl
        else:
            out._apply = lincomb_apply

        return out

    def _multiply(self, x1, x2, out):
        """Raw pointwise multiplication of two functions.

        Note
        ----
        The multiplication is implemented with a simple Python
        function, so the resulting function object is probably slow.
        """
        x1_call = x1._call
        x1_apply = x1._apply
        x2_call = x2._call
        x2_apply = x2._apply

        product_vect = x1.vectorized or x2.vectorized
        dtype = complex if self.field == ComplexNumbers() else float
        if product_vect and not x1.vectorized:
            x1_call = vectorize(dtype, outarg='none')(x1_call)
            x1_apply = vectorize(dtype, outarg='positional')(x1_call)
        if product_vect and not x2.vectorized:
            x2_call = vectorize(dtype, outarg='none')(x2_call)
            x2_apply = vectorize(dtype, outarg='positional')(x2_call)

        def product_call(x):
            """The product call function."""
            return x1_call(x) * x2_call(x)

        def product_apply(x, out):
            """The product apply function."""
            tmp = np.empty_like(out)
            x1_apply(x, out)
            x2_apply(x, tmp)
            out *= tmp
            return out

        out._call = product_call
        out._vectorized = product_vect
        # If one of the factors' apply method is undefined, it will not be
        # defined in the result either
        if _apply_not_impl in (x1._apply, x2._apply):
            out._apply = _apply_not_impl
        else:
            out._apply = product_apply

        return out

    def _divide(self, x1, x2, out):
        """Raw pointwise division of two functions."""
        x1_call = x1._call
        x1_apply = x1._apply
        x2_call = x2._call
        x2_apply = x2._apply

        quotient_vect = x1.vectorized or x2.vectorized
        dtype = complex if self.field == ComplexNumbers() else float
        if quotient_vect and not x1.vectorized:
            x1_call = vectorize(dtype, outarg='none')(x1_call)
            x1_apply = vectorize(dtype, outarg='positional')(x1_call)
        if quotient_vect and not x2.vectorized:
            x2_call = vectorize(dtype, outarg='none')(x2_call)
            x2_apply = vectorize(dtype, outarg='positional')(x2_call)

        def quotient_call(x):
            """The quotient call function."""
            return x1_call(x) / x2_call(x)

        def quotient_apply(x, out):
            """The quotient apply function."""
            tmp = np.empty_like(out)
            x1_apply(x, out)
            x2_apply(x, tmp)
            out /= tmp
            return out

        out._call = quotient_call
        out._vectorized = quotient_vect
        # If one of the factors' apply method is undefined, it will not be
        # defined in the result either
        if _apply_not_impl in (x1._apply, x2._apply):
            out._apply = _apply_not_impl
        else:
            out._apply = quotient_apply

        return out

    def divide(self, x1, x2, out=None):
        """Same as in LinearSpace.Vector, but with vectorization."""
        if out is None:
            out = self.element()

        if x1 not in self:
            raise TypeError('first vector {!r} not in space {!r}'
                            ''.format(x1, self))
        if x2 not in self:
            raise TypeError('second vector {!r} not in space {!r}'
                            ''.format(x2, self))
        else:
            if out not in self:
                raise TypeError('ouput vector {!r} not in space {!r}'
                                ''.format(out, self))
        return self._divide(x1, x2, out)

    def _scalar_power(self, x, p, out):
        """Raw p-th power of a function, p integer or general scalar."""
        x_call = x._call
        x_apply = x._apply

        def pow_posint(x, n):
            """Recursion to calculate the n-th power out-of-place."""
            if isinstance(x, np.ndarray):
                y = x.copy()
                return ipow_posint(y, n)
            else:
                return x**n

        def ipow_posint(x, n):
            """Recursion to calculate the n-th power in-place."""
            if n == 1:
                return x
            elif n % 2 == 0:
                x *= x
                return ipow_posint(x, n//2)
            else:
                tmp = x.copy()
                x *= x
                ipow_posint(x, n//2)
                x *= tmp
                return x

        def power_call(x):
            """The power call function."""
            if p == int(p) and p >= 1:
                return pow_posint(x_call(x), int(p))
            else:
                return x_call(x)**p

        def power_apply(x, out):
            """The power apply function."""
            x_apply(x, out)
            if p == int(p) and p >= 1:
                return ipow_posint(out, int(p))
            else:
                out **= p
                return out

        out._call = power_call
        out._vectorized = x.vectorized
        if x_apply == _apply_not_impl:
            out._apply = _apply_not_impl
        else:
            out._apply = power_apply

    class Vector(FunctionSet.Vector, LinearSpace.Vector):

        """Representation of a `FunctionSpace` element."""

        def __init__(self, fspace, fcall=None, fapply=None,
                     vectorized=True):
            """Initialize a new instance.

            Parameters
            ----------
            fspace : `FunctionSpace`
                The set of functions this element lives in
            fcall : callable
                The actual instruction for out-of-place evaluation. If
                `fcall` is a `FunctionSet.Vector`, its `_call`, `_apply`
                and `vectorization` are used for initialization unless
                explicitly given
            fapply : callable, optional
                The actual instruction for in-place evaluation
            vectorized : bool
                Whether or not the function supports vectorized
                evaluation.
            """
            if not isinstance(fspace, FunctionSpace):
                raise TypeError('function space {} not a `FunctionSpace` '
                                'instance.'.format(fspace))

            super().__init__(fspace, fcall, fapply,
                             vectorized=vectorized)

        # Convenience functions using element() need to be adapted
        def __add__(self, other):
            """`f.__add__(other) <==> f + other`."""
            out = self.space.element()
            if other in self.space:
                self.space.lincomb(1, self, 1, other, out=out)
            else:
                one = self.space.one(vectorized=self.vectorized)
                self.space.lincomb(1, self, 1, other * one, out=out)
            return out

        def __radd__(self, other):
            """`f.__radd__(other) <==> other + f`."""
            out = self.space.element(vectorized=self.vectorized)
            # the `other in self.space` case can never happen!
            one = self.space.one(vectorized=self.vectorized)
            self.space.lincomb(1, other * one, 1, self, out=out)
            return out

        def __iadd__(self, other):
            """`f.__iadd__(other) <==> f += other`."""
            if other in self.space:
                self.space.lincomb(1, self, 1, other, out=self)
            else:
                one = self.space.one(vectorized=self.vectorized)
                self.space.lincomb(1, self, 1, other * one, out=self)
            return self

        def __sub__(self, other):
            """Implementation of 'self - other'."""
            out = self.space.element(vectorized=self.vectorized)
            if other in self.space:
                self.space.lincomb(1, self, -1, other, out=out)
            else:
                one = self.space.one(vectorized=self.vectorized)
                self.space.lincomb(1, self, 1, -other * one, out=out)
            return out

        def __rsub__(self, other):
            """`f.__rsub__(other) <==> other - f`."""
            out = self.space.element(vectorized=self.vectorized)
            # the `other in self.space` case can never happen!
            one = self.space.one(vectorized=self.vectorized)
            self.space.lincomb(1, other * one, -1, self, out=out)
            return out

        def __isub__(self, other):
            """`f.__isub__(other) <==> f -= other`."""
            if other in self.space:
                self.space.lincomb(1, self, -1, other, out=self)
            else:
                one = self.space.one(vectorized=self.vectorized)
                self.space.lincomb(1, self, 1, -other * one, out=self)
            return self

        def __mul__(self, other):
            """`f.__mul__(other) <==> f * other`."""
            out = self.space.element(vectorized=self.vectorized)
            if other in self.space:
                self.space.multiply(self, other, out=out)
            else:
                self.space.lincomb(other, self, out=out)
            return out

        def __rmul__(self, other):
            """`f.__rmul__(other) <==> other * f`."""
            out = self.space.element(vectorized=self.vectorized)
            # the `other in self.space` case can never happen!
            self.space.lincomb(other, self, out=out)
            return out

        def __imul__(self, other):
            """`f.__imul__(other) <==> f *= other`."""
            if other in self.space:
                self.space.multiply(self, other, out=self)
            else:
                self.space.lincomb(other, self, out=self)
            return self

        def __truediv__(self, other):
            """`f.__truediv__(other) <==> f / other` (true division)."""
            out = self.space.element(vectorized=self.vectorized)
            if other in self.space:
                self.space.divide(self, other, out=out)
            else:
                self.space.lincomb(1./other, self, out=out)
            return out

        __div__ = __truediv__

        def __rtruediv__(self, other):
            """`f.__rtruediv__(other) <==> other / f` (true division)."""
            out = self.space.element(vectorized=self.vectorized)
            # the `other in self.space` case can never happen!
            one = self.space.one(vectorized=self.vectorized)
            self.space.divide(other * one, self, out=out)
            return out

        __rdiv__ = __rtruediv__

        def __itruediv__(self, other):
            """`f.__itruediv__(other) <==> f /= other` (true division)."""
            if other in self.space:
                self.space.divide(self, other, out=self)
            else:
                self.space.lincomb(1./other, self, out=self)
            return self

        __idiv__ = __itruediv__

        def __pow__(self, p):
            """`f.__pow__(p) <==> f ** p`."""
            out = self.space.element(vectorized=self.vectorized)
            self.space._scalar_power(self, p, out=out)
            return out

        def __ipow__(self, p):
            """`f.__ipow__(p) <==> f **= p`."""
            return self.space._scalar_power(self, p, out=self)

        def __neg__(self):
            """`f.__neg__() <==> -f`."""
            out = self.space.element(vectorization=self.vectorization)
            self.space.lincomb(-1.0, self, out=out)
            return out

        def __pos__(self):
            """`f.__pos__() <==> +f`."""
            return self.copy()


if __name__ == '__main__':
    from doctest import testmod, NORMALIZE_WHITESPACE
    testmod(optionflags=NORMALIZE_WHITESPACE)
