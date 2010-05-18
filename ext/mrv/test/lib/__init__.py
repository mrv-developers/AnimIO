# -*- coding: utf-8 -*-
"""Imports all utility functions into the same module """
from util import *
# needs to stay in a module, otherwise nose will pick up the runTest method 
# from the TestCase class which is just a string - its odd 
import unittest 