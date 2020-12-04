# This package implements event log checking.
# Currently, the PCR contents are not checked;
# what is checked is that the sequence of events is acceptable.
# This checking is factored into two stages:
# 1. a policy maps a convenient expression of intended state into
#    a test to apply to event logs;
# 2. that test is applied (perhaps to several logs in series).

# At the current level of development, the set of policies is built into
# this package at development time.  In the future, there could be a way
# to dynamically load policies.

from . import nextgen2
