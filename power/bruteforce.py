"""Brute-force oracles for small games. Used ONLY in tests to check the DP code."""
import itertools
import math

import numpy as np


def banzhaf_bruteforce(weights, q):
    """Normalised Banzhaf by enumerating all 2^(n-1) coalitions of the others."""
    n = len(weights)
    swings = np.zeros(n)
    for i in range(n):
        others = [j for j in range(n) if j != i]
        for r in range(len(others) + 1):
            for S in itertools.combinations(others, r):
                s = sum(weights[j] for j in S)
                if s < q <= s + weights[i]:
                    swings[i] += 1
    t = swings.sum()
    return swings / t if t > 0 else swings


def shapley_bruteforce_subsets(weights, q):
    """Shapley-Shubik by enumerating coalitions with weight |S|!(n-1-|S|)!/n!."""
    n = len(weights)
    phi = np.zeros(n)
    for i in range(n):
        others = [j for j in range(n) if j != i]
        for r in range(len(others) + 1):
            c = math.factorial(r) * math.factorial(n - 1 - r) / math.factorial(n)
            for S in itertools.combinations(others, r):
                s = sum(weights[j] for j in S)
                if s < q <= s + weights[i]:
                    phi[i] += c
    return phi


def shapley_bruteforce_permutations(weights, q):
    """Shapley-Shubik by enumerating all n! orderings (n <= 8)."""
    n = len(weights)
    piv = np.zeros(n)
    for order in itertools.permutations(range(n)):
        s = 0
        for i in order:
            if s < q <= s + weights[i]:
                piv[i] += 1
                break
            s += weights[i]
    return piv / math.factorial(n)
