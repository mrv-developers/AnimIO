# -*- coding: utf-8 -*-
"""
Intialize the byronimo maya UI testing suite



"""


import unittest
import mrv.test as common


def get_suite( ):
	""" @return: testsuite with all tests of this package"""
	import mrv.test.maya.ui as self
	import maya.cmds as cmds

	# each test has to check whether he can run in batch mode or not
	return common.get_package_suite( self )

def run( **runner_args ):
	"""Run all the tests"""
	testrunner = unittest.TextTestRunner( **runner_args )
	return testrunner.run( get_suite() )


def main( *args ):
	""" Run the tests if called with the start script """
	run( verbosity = 2 )


if __name__ == '__main__':
	""" run all tests if run directly """
	main( [] )

