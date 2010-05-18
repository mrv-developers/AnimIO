# -*- coding: utf-8 -*-
"""
Contains implementations of maya editors
"""
__docformat__ = "restructuredtext"
import base as uibase
import util as uiutil


class Panel( uibase.NamedUI, uiutil.UIContainerBase ):
	""" Structural base  for all Layouts allowing general queries and name handling
	Layouts may track their children """

