from itertools import chain, permutations

import pycosat
import pytest

from conda.logic import (Clauses, evaluate_eq, true, false, sat, minimal_unsatisfiable_subset)

from tests.helpers import raises

def my_itersolve(iterable):
    """
    Work around https://github.com/ContinuumIO/pycosat/issues/13
    """
    iterable = [[i for i in j] for j in iterable]
    return pycosat.itersolve(iterable)

# TODO: We test that all the models of the transformed system are models of
# the original, but not that all models of the original are models of the
# transformed system.  Or does testing -x do this?

class NoBool(object):
    # Will only be called if tests are wrong and don't short-circuit correctly
    def __bool__(self):
        raise TypeError
    __nonzero__ = __bool__

def boolize(x):
    if x == true:
        return True
    if x == false:
        return False
    return NoBool()

def test_ITE():
    # Note, pycosat will automatically include all smaller numbers in models,
    # e.g., itersolve([[2]]) gives [[1, 2], [-1, 2]]. This should not be an
    # issue here.

    for c in [true, false, 1]:
        for t in [true, false, 2]:
            for f in [true, false, 3]:
                Clneg = Clauses(3)
                Clpos = Clauses(3)
                Cl = Clauses(3)
                x = Cl.ITE(c, t, f)
                xneg = Clneg.ITE(c, t, f, polarity=False)
                xpos = Clpos.ITE(c, t, f, polarity=True)
                if x in [true, false]:
                    if t == f:
                        # In this case, it doesn't matter if c is not boolizable
                        assert boolize(x) == boolize(t)
                    else:
                        assert boolize(x) == (boolize(t) if boolize(c) else
                            boolize(f)), (c, t, f)
                else:

                    for sol in chain(my_itersolve([(x,)] + Cl.clauses),
                        my_itersolve([(xpos,)] + Clpos.clauses)):
                        C = boolize(c) if c in [true, false] else (1 in sol)
                        T = boolize(t) if t in [true, false] else (2 in sol)
                        F = boolize(f) if f in [true, false] else (3 in sol)
                        assert T if C else F, (T, C, F, sol, t, c, f)

                    for sol in chain(my_itersolve([(-x,)] + Cl.clauses),
                        my_itersolve([(-xneg,)] + Clneg.clauses)):
                        C = boolize(c) if c in [true, false] else (1 in sol)
                        T = boolize(t) if t in [true, false] else (2 in sol)
                        F = boolize(f) if f in [true, false] else (3 in sol)
                        assert not (T if C else F)

def test_And_clauses():
    # XXX: Is this i, j stuff necessary?
    for i in range(-1, 2, 2): # [-1, 1]
        for j in range(-1, 2, 2):
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.And(i*1, j*2)
            xpos = Cpos.And(i*1, j*2, polarity=True)
            xneg = Cneg.And(i*1, j*2, polarity=False)
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert f and g
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert not (f and g)

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.And(1, -1)
    xpos = Cpos.And(1, -1, polarity=True)
    xneg = Cneg.And(1, -1, polarity=False)
    assert x == xneg == xpos == false # x and ~x
    assert C.clauses == Cpos.clauses == Cneg.clauses == []

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.And(1, 1)
    xpos = Cpos.And(1, 1, polarity=True)
    xneg = Cneg.And(1, 1, polarity=False)
    for sol in chain(my_itersolve([(x,)] + C.clauses), 
        my_itersolve([(xpos,)] + Cpos.clauses)):
        f = 1 in sol
        assert (f and f)
    for sol in chain(my_itersolve([(-x,)] + C.clauses),
        my_itersolve([(-xneg,)] + Cneg.clauses)):
        f = 1 in sol
        assert not (f and f)

def test_And_bools():
    for f in [true, false]:
        for g in [true, false]:
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.And(f, g)
            xpos = Cpos.And(f, g, polarity=True)
            xneg = Cneg.And(f, g, polarity=False)
            assert x == xpos == xneg == (true if (boolize(f) and boolize(g)) else false)
            assert C.clauses == Cpos.clauses == Cneg.clauses == []

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.And(f, 1)
        xpos = Cpos.And(f, 1, polarity=True)
        xneg = Cneg.And(f, 1, polarity=False)
        fb = boolize(f)
        if x in [true, false]:
            assert C.clauses == Cpos.clauses == Cneg.clauses == []
            xb = boolize(x)
            xbpos = boolize(xpos)
            xbneg = boolize(xneg)
            assert xb == xbpos == xbneg == (fb and NoBool())
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert (fb and a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not (fb and a)

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.And(1, f)
        xpos = Cpos.And(1, f, polarity=True)
        xneg = Cneg.And(1, f, polarity=False)
        if x in [true, false]:
            assert C.clauses == Cpos.clauses == Cneg.clauses == []
            xb = boolize(x)
            xbpos = boolize(xpos)
            xbneg = boolize(xneg)
            assert xb == xbpos == xbneg == (fb and NoBool())
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert (fb and a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not (fb and a)


def test_Or_clauses():
    # XXX: Is this i, j stuff necessary?
    for i in range(-1, 2, 2): # [-1, 1]
        for j in range(-1, 2, 2):
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.Or(i*1, j*2)
            xpos = Cpos.Or(i*1, j*2, polarity=True)
            xneg = Cneg.Or(i*1, j*2, polarity=False)
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert f or g
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert not (f or g)

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.Or(1, -1)
    xpos = Cpos.Or(1, -1, polarity=True)
    xneg = Cneg.Or(1, -1, polarity=False)
    assert x == xpos == xneg == true # x or ~x
    assert C.clauses == Cpos.clauses == Cneg.clauses == []

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.Or(1, 1)
    xpos = Cpos.Or(1, 1, polarity=True)
    xneg = Cneg.Or(1, 1, polarity=False)
    for sol in chain(my_itersolve([(x,)] + C.clauses), 
        my_itersolve([(xpos,)] + Cpos.clauses)):
        f = 1 in sol
        assert (f or f)
    for sol in chain(my_itersolve([(-x,)] + C.clauses),
        my_itersolve([(-xneg,)] + Cneg.clauses)):
        f = 1 in sol
        assert not (f or f)


def test_Or_bools():
    for f in [true, false]:
        for g in [true, false]:
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.Or(f, g)
            xpos = Cpos.Or(f, g, polarity=True)
            xneg = Cneg.Or(f, g, polarity=False)
            assert x == xpos == xneg == (true if (boolize(f) or boolize(g)) else false)
            assert C.clauses == Cpos.clauses == Cneg.clauses == []

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.Or(f, 1)
        xpos = Cpos.Or(f, 1, polarity=True)
        xneg = Cneg.Or(f, 1, polarity=False)
        fb = boolize(f)
        if x in [true, false]:
            assert C.clauses == Cpos.clauses == Cneg.clauses == []
            xb = boolize(x)
            xbpos = boolize(xpos)
            xbneg = boolize(xneg)
            assert xb == xbpos == xbneg == (fb or NoBool())
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert (fb or a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not (fb or a)

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.Or(1, f)
        xpos = Cpos.Or(1, f, polarity=True)
        xneg = Cneg.Or(1, f, polarity=False)
        if x in [true, false]:
            assert C.clauses == Cpos.clauses == Cneg.clauses == []
            xb = boolize(x)
            xbpos = boolize(xpos)
            xbneg = boolize(xneg)
            assert xb == xbpos == xbneg == (fb or NoBool())
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert (fb or a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not (fb or a)

# Note xor is the same as !=
def test_Xor_clauses():
    # XXX: Is this i, j stuff necessary?
    for i in range(-1, 2, 2): # [-1, 1]
        for j in range(-1, 2, 2):
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.Xor(i*1, j*2)
            xpos = Cpos.Xor(i*1, j*2, polarity=True)
            xneg = Cneg.Xor(i*1, j*2, polarity=False)
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert (f != g)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                f = i*1 in sol
                g = j*2 in sol
                assert not (f != g)

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.Xor(1, 1)
    xpos = Cpos.Xor(1, 1, polarity=True)
    xneg = Cneg.Xor(1, 1, polarity=False)
    assert x == xpos == xneg == false # x xor x
    assert C.clauses == Cpos.clauses == Cneg.clauses == []

    C = Clauses(1)
    Cpos = Clauses(1)
    Cneg = Clauses(1)
    x = C.Xor(1, -1)
    xpos = Cpos.Xor(1, -1, polarity=True)
    xneg = Cneg.Xor(1, -1, polarity=False)
    assert x == xpos == xneg == true # x xor -x
    assert C.clauses == Cpos.clauses == Cneg.clauses == []

def test_Xor_bools():
    for f in [true, false]:
        for g in [true, false]:
            C = Clauses(2)
            Cpos = Clauses(2)
            Cneg = Clauses(2)
            x = C.Xor(f, g)
            xpos = Cpos.Xor(f, g, polarity=True)
            xneg = Cneg.Xor(f, g, polarity=False)
            assert x == xpos == xneg == (true if (boolize(f) != boolize(g)) else false)
            assert C.clauses == Cpos.clauses == Cneg.clauses == []

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.Xor(f, 1)
        xpos = Cpos.Xor(f, 1, polarity=True)
        xneg = Cneg.Xor(f, 1, polarity=False)
        fb = boolize(f)
        if x in [true, false] or xpos in [true, false] or xneg in [true, false]:
            assert False
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert (fb != a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not (fb != a)

        C = Clauses(1)
        Cpos = Clauses(1)
        Cneg = Clauses(1)
        x = C.Xor(1, f)
        xpos = Cpos.Xor(1, f, polarity=True)
        xneg = Cneg.Xor(1, f, polarity=False)
        if x in [true, false] or xpos in [true, false] or xneg in [true, false]:
            assert False
        else:
            for sol in chain(my_itersolve([(x,)] + C.clauses),
                my_itersolve([(xpos,)] + Cpos.clauses)):
                a = 1 in sol
                assert not (fb == a)
            for sol in chain(my_itersolve([(-x,)] + C.clauses),
                my_itersolve([(-xneg,)] + Cneg.clauses)):
                a = 1 in sol
                assert not not (fb == a)

def test_true_false():
    assert true == true
    assert false == false
    assert true != false
    assert false != true
    assert -true == false
    assert -false == true

    assert false < true
    assert not (true < false)
    assert not (false < false)
    assert not (true < true)
    assert false <= true
    assert true <= true
    assert false <= false
    assert true <= true

    assert not (false > true)
    assert true > false
    assert not (false > false)
    assert not (true > true)
    assert not (false >= true)
    assert (true >= true)
    assert false >= false
    assert true >= true


@pytest.mark.slow
def test_BDD():
    L = [
        ([(1, 1), (2, 2)], [0, 2], 10000),
        ([(1, 1), (2, -2)], [0, 2], 10000),
        ([(1, 1), (2, 2), (3, 3)], [3, 3], 10000),
        ([(0, 1), (1, 2), (2, 3), (0, 4), (1, 5), (0, 6), (1, 7)], [0, 2], 10000),
        ([(1, 15), (2, 16), (3, 17), (4, 18), (5, 6), (5, 19), (6, 7),
          (6, 20), (7, 8), (7, 21), (7, 28), (8, 9), (8, 22), (8, 29), (8, 41), (9,
          10), (9, 23), (9, 30), (9, 42), (10, 1), (10, 11), (10, 24), (10, 31),
          (10, 34), (10, 37), (10, 43), (10, 46), (10, 50), (11, 2), (11, 12), (11,
          25), (11, 32), (11, 35), (11, 38), (11, 44), (11, 47), (11, 51), (12, 3),
          (12, 4), (12, 5), (12, 13), (12, 14), (12, 26), (12, 27), (12, 33), (12,
          36), (12, 39), (12, 40), (12, 45), (12, 48), (12, 49), (12, 52), (12, 53),
          (12, 54)], [192, 204], 100),
        ([(0, 12), (0, 14), (0, 22), (0, 59), (0, 60), (0, 68), (0,
        102), (0, 105), (0, 164), (0, 176), (0, 178), (0, 180), (0, 182), (1,
            9), (1, 13), (1, 21), (1, 58), (1, 67), (1, 101), (1, 104), (1,
                163), (1, 175), (1, 177), (1, 179), (1, 181), (2, 6), (2, 20),
        (2, 57), (2, 66), (2, 100), (2, 103), (2, 162), (2, 174), (3, 11), (3,
            19), (3, 56), (3, 65), (3, 99), (3, 161), (3, 173), (4, 8), (4,
                18), (4, 55), (4, 64), (4, 98), (4, 160), (4, 172), (5, 5),
        (5, 17), (5, 54), (5, 63), (5, 97), (5, 159), (5, 171), (6, 10), (6,
            16), (6, 52), (6, 62), (6, 96), (6, 158), (6, 170), (7, 7), (7,
                15), (7, 50), (7, 61), (7, 95), (7, 157), (7, 169), (8, 4),
        (8, 48), (8, 94), (8, 156), (8, 168), (9, 3), (9, 46), (9, 93), (9,
            155), (9, 167), (10, 2), (10, 53), (10, 92), (10, 154), (10, 166),
        (11, 1), (11, 51), (11, 91), (11, 152), (11, 165), (12, 49), (12, 90),
        (12, 150), (13, 47), (13, 89), (13, 148), (14, 45), (14, 88), (14,
            146), (15, 39), (15, 87), (15, 144), (16, 38), (16, 86), (16,
                142), (17, 37), (17, 85), (17, 140), (18, 44), (18, 84), (18,
                    138), (19, 43), (19, 83), (19, 153), (20, 42), (20, 82),
        (20, 151), (21, 41), (21, 81), (21, 149), (22, 40), (22, 80), (22,
            147), (23, 36), (23, 79), (23, 145), (24, 32), (24, 70), (24,
                143), (25, 35), (25, 78), (25, 141), (26, 34), (26, 77), (26,
                    139), (27, 31), (27, 76), (27, 137), (28, 30), (28, 75),
        (28, 136), (29, 33), (29, 74), (29, 135), (30, 29), (30, 73), (30,
            134), (31, 28), (31, 72), (31, 133), (32, 27), (32, 71), (32,
                132), (33, 25), (33, 69), (33, 131), (34, 24), (34, 130), (35,
                    26), (35, 129), (36, 23), (36, 128), (37, 125), (38, 124),
        (39, 123), (40, 122), (41, 121), (42, 120), (43, 119), (44, 118), (45,
            117), (46, 116), (47, 115), (48, 114), (49, 113), (50, 127), (51,
                126), (52, 112), (53, 111), (54, 110), (55, 109), (56, 108),
        (57, 107), (58, 106)], [21, 40], 1000)
        ]
    for eq, rhs, max_iter in L:
        N = max(a for c,a in eq)
        C = Clauses(N)
        Cneg = Clauses(N)
        Cpos = Clauses(N)
        x = C.build_BDD(eq, rhs[0], rhs[1])
        xneg = Cneg.build_BDD(eq, rhs[0], rhs[1], polarity=False)
        xpos = Cpos.build_BDD(eq, rhs[0], rhs[1], polarity=True)
        for _, sol in zip(range(max_iter), my_itersolve([(x,)] + C.clauses)):
            assert rhs[0] <= evaluate_eq(eq,sol) <= rhs[1]
        for _, sol in zip(range(max_iter), my_itersolve([(xpos,)] + Cpos.clauses)):
            assert rhs[0] <= evaluate_eq(eq,sol) <= rhs[1]
        for _, sol in zip(range(max_iter), my_itersolve([(-x,)] + C.clauses)):
            assert not(rhs[0] <= evaluate_eq(eq,sol) <= rhs[1])
        for _, sol in zip(range(max_iter), my_itersolve([(-xneg,)] + Cneg.clauses)):
            assert not(rhs[0] <= evaluate_eq(eq,sol) <= rhs[1])

def test_sat():
    assert sat([[1]]) == [1]
    assert sat([[1], [-1]]) is None
    assert sat([]) == []

def test_minimal_unsatisfiable_subset():
    assert raises(ValueError, lambda: minimal_unsatisfiable_subset([[1]]))

    clauses = [[-10], [1], [5], [2, 3], [3, 4], [5, 2], [-7], [2], [3], [-2,
        -3, 5], [7, 8, 9, 10], [-8], [-9]]
    res = minimal_unsatisfiable_subset(clauses)
    assert sorted(res) == [[-10], [-9], [-8], [-7], [7, 8, 9, 10]]
    assert not sat(res)


    clauses = [[1, 3], [2, 3], [-1], [4], [3], [-3]]
    for perm in permutations(clauses):
        res = minimal_unsatisfiable_subset(clauses)
        assert sorted(res) == [[-3], [3]]
        assert not sat(res)

    clauses = [[1], [-1], [2], [-2], [3, 4], [4]]
    for perm in permutations(clauses):
        res = minimal_unsatisfiable_subset(perm)
        assert sorted(res) in [[[-1], [1]], [[-2], [2]]]
        assert not sat(res)
