"""Exceptions used throughout Eelbrain"""


class DimensionMismatchError(Exception):
    "Trying to align NDVars with mismatching dimensions"


class OldVersionError(Exception):
    "Trying to load a file from a version that is no longer supported"


class ZeroVariance(Exception):
    "Trying to do test on data with zero variance"
