#!/usr/bin/env python3
"""Discover and run all project unit tests.

    python3 run_tests.py

Discovers test_*.py under backtest/ and exits non-zero if anything fails
(CI-friendly). Equivalent to: python3 -m unittest discover -s backtest.
"""
import sys
import unittest

if __name__ == "__main__":
    suite = unittest.TestLoader().discover(start_dir="backtest", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
