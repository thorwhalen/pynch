__author__ = 'thorwhalen'

from collections import Counter
import itertools


def combination_counts(df, subset_size=2):
    for columns_subset in itertools.combinations(df.columns, subset_size):
        yield columns_subset, Counter(map(tuple, df[list(columns_subset)].values))


