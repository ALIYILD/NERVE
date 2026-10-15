"""Runtime contract for archived, bit-exact macOS/Python 3.10 receipts.

These tests run without skips in the required historical-evidence CI job.
Current-runtime synthetic tests remain independent of these archived artifacts.
"""
import platform
import sys
import unittest

SUPPORTED = (sys.version_info[:2] == (3, 10)
             and platform.system() == 'Darwin' and platform.machine() == 'x86_64')
archived_receipt = unittest.skipUnless(
    SUPPORTED, 'bit-exact archived receipt: required historical-evidence CI uses macOS x86_64/Python 3.10')
