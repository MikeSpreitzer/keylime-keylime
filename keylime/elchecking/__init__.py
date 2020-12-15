# This package implements event log checking.
# This checking is factored into two stages:
# 1. a policy maps a convenient expression of intended state into
#    a test to apply to event logs and PCR contents;
# 2. that test is applied to various log&PCRs pairs.

# At the current level of development, the set of policies is built into
# this package at development time.  In the future, there could be a way
# to dynamically load policies.

from . import nextgen2
