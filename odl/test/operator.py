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

import warnings
import numpy as np
from itertools import product

from odl.set.pspace import ProductSpace
from odl.operator.operator import Operator
from odl.space.base_ntuples import FnBase, NtuplesBase
from odl.discr.l2_discr import DiscreteL2
from odl.test.examples import scalar_examples, vector_examples

__all__ = ('OperatorTest',)

class OperatorTest(object):
    def __init__(self, operator, operator_norm=None):
        self.operator = operator
        self.operator_norm = operator_norm

    def norm(self):
        print('\n== Calculating operator norm ==\n')

        operator_norm = 0.0
        for [name, vec] in vector_examples(self.operator.domain):
            result = self.operator(vec)
            vecnorm = vec.norm()
            estimate = 0 if vecnorm == 0 else result.norm() / vecnorm

            operator_norm = max(operator_norm, estimate)

        print('Norm is at least: {}'.format(operator_norm))
        self.operator_norm = operator_norm
        return operator_norm

    def _adjoint_definition(self):
        print('\nVerifying the identity (Ax, y) = (x, A^T y)')
        print('error = ||(Ax, y) - (x, A^T y)|| / ||A|| ||x|| ||y||')

        x = []
        y = []

        num_failed = 0

        for [name_dom, vec_dom] in vector_examples(self.operator.domain):
            vec_dom_norm = vec_dom.norm()
            for [name_ran, vec_ran] in vector_examples(self.operator.range):
                vec_ran_norm = vec_ran.norm()

                Axy = self.operator(vec_dom).inner(vec_ran)
                xAty = vec_dom.inner(self.operator.adjoint(vec_ran))

                denom = self.operator_norm * vec_dom_norm * vec_ran_norm
                error = 0 if denom == 0 else abs(Axy-xAty)/denom

                if error > 0.00001:
                    print('x={:25s} y={:25s} : error={:6.5f}'
                          ''.format(name_dom, name_ran, error))
                    num_failed += 1

                x.append(Axy)
                y.append(xAty)

        if num_failed == 0:
            print('error = 0.0 for all test cases')
        else:
            print('*** FAILED {} TEST CASES ***'.format(num_failed))

        scale = np.polyfit(x, y, 1)[0]
        print('\nThe adjoint seems to be scaled according to:')
        print('(x, A^T y) / (Ax, y) = {}. Should be 1.0'.format(scale))

    def _adjoint_of_adjoint(self):
        # Verify (A^*)^* = A
        try:
            self.operator.adjoint.adjoint
        except AttributeError:
            print('A^* has no adjoint')
            return

        if self.operator.adjoint.adjoint is self.operator:
            print('(A^*)^* == A')
            return

        print('\nVerifying the identity Ax = (A^T)^T x')
        print('error = ||Ax - (A^T)^T x|| / ||A|| ||x||')

        num_failed = 0

        for [name, vec] in vector_examples(self.operator.domain):
            A_result = self.operator(vec)
            ATT_result = self.operator.adjoint.adjoint(vec)

            denom = self.operator_norm * vec.norm()
            error = 0 if denom == 0 else (A_result-ATT_result).norm()/denom
            if error > 0.00001:
                print('x={:25s} : error={:6.5f}'.format(name, error))
                num_failed += 1

        if num_failed == 0:
            print('error = 0.0 for all test cases')
        else:
            print('*** FAILED {} TEST CASES ***'.format(num_failed))

    def adjoint(self):
        """Verify that the adjoint works appropriately."""
        try:
            self.operator.adjoint
        except NotImplementedError:
            print('Operator has no adjoint')
            return

        print('\n== Verifying adjoint of operator ==\n')

        domain_range_ok = True
        if self.operator.domain != self.operator.adjoint.range:
            print('ERROR: A.domain != A.adjoint.range')
            domain_range_ok = False

        if self.operator.range != self.operator.adjoint.domain:
            print('ERROR: A.domain != A.adjoint.range')
            domain_range_ok = False

        if domain_range_ok:
            print('Domain and range of adjoint is OK.')
        else:
            print('Domain and range of adjoint not OK exiting.')
            return

        self._adjoint_definition()
        self._adjoint_of_adjoint()

    def derivative(self, step=0.0001):
        """Verify that the derivative works appropriately."""
        try:
            self.operator.derivative(self.operator.domain.zero())
        except NotImplementedError:
            print('Operator has no derivative')
            return

        if self.operator_norm is None:
            print('Cannot do tests before norm is calculated, run test.norm() '
                  'or give norm as a parameter')
            return

        print('\n== Verifying derivative of operator with step = {} ==\n'
              ''.format(step))
        print("error = ||A(x+c*dx)-A(x)-c*A'(x)(dx)|| / |c| ||dx|| ||A||")

        num_failed = 0

        for [name_x, x] in vector_examples(self.operator.domain):
            deriv = self.operator.derivative(x)
            opx = self.operator(x)
            for [name_dx, dx] in vector_examples(self.operator.domain):
                exact_step = self.operator(x+dx*step)-opx
                expected_step = deriv(dx*step)
                denom = step * dx.norm() * self.operator_norm
                error = (0 if denom == 0
                         else (exact_step-expected_step).norm() / denom)

                if error > 0.00001:
                    print('x={:15s} dx={:15s} : error={:6.5f}'
                          ''.format(name_x, name_dx, step, error))
                    num_failed += 1

        if num_failed == 0:
            print('error = 0.0 for all test cases')
        else:
            print('*** FAILED {} TEST CASES ***'.format(num_failed))

    def linear(self):
        """ Verifies that the operator is actually linear
        """
        if not self.operator.linear:
            print('Operator is not linear')
            return

        if self.operator_norm is None:
            print('Cannot do tests before norm is calculated, run test.norm() '
                  'or give norm as a parameter')
            return

        print('\n== Verifying linearity of operator ==\n')

        # Test zero gives zero
        result = self.operator(self.operator.domain.zero())
        print("||A(0)||={:6.5f}. Should be 0.0000".format(result.norm()))

        print("\nCalculating invariance under scaling")
        print("error = ||A(c*x)-c*A(x)|| / |c| ||A|| ||x||")

        # Test scaling
        num_failed = 0

        for [name_x, x] in vector_examples(self.operator.domain):
            opx = self.operator(x)
            for scale in scalar_examples(self.operator.domain):
                scaled_opx = self.operator(scale*x)

                denom = self.operator_norm * scale * x.norm()
                error = (0 if denom == 0
                         else (scaled_opx - opx * scale).norm() / denom)

                if error > 0.00001:
                    print('x={:25s} scale={:7.2f} error={:6.5f}'
                          ''.format(name_x, scale, error))
                    num_failed += 1

        if num_failed == 0:
            print('error = 0.0 for all test cases')
        else:
            print('*** FAILED {} TEST CASES ***'.format(num_failed))

        print("\nCalculating invariance under addition")
        print("error = ||A(x+y)-A(x)-A(y)|| / ||A||(||x|| + ||y||)")

        # Test addition
        num_failed = 0

        for [name_x, x] in vector_examples(self.operator.domain):
            opx = self.operator(x)
            for [name_y, y] in vector_examples(self.operator.domain):
                opy = self.operator(y)
                opxy = self.operator(x+y)

                denom = self.operator_norm * (x.norm() + y.norm())
                error = 0 if denom == 0 else (opxy - opx - opy).norm()/denom

                if error > 0.00001:
                    print('x={:25s} y={:25s} error={:6.5f}'
                          ''.format(name_x, name_y, error))
                    num_failed += 1

        if num_failed == 0:
            print('error = 0.0 for all test cases')
        else:
            print('*** FAILED {} TEST CASES ***'.format(num_failed))

    def run_tests(self):
        """Runs all tests on this operator
        """
        print('\n== RUNNING ALL TESTS ==\n')
        print('Operator = {}'.format(self.operator))

        self.norm()
        if self.operator.linear:
            self.linear()
            self.adjoint()
        else:
            self.derivative()
            
    def __str__(self):
        return 'OperatorTest({})'.format(self.operator)

    def __repr__(self):
        return 'OperatorTest({!r})'.format(self.operator)

if __name__ == '__main__':
    from doctest import testmod, NORMALIZE_WHITESPACE
    testmod(optionflags=NORMALIZE_WHITESPACE)
