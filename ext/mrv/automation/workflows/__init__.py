# -*- coding: utf-8 -*-
"""Keeps all workflows specific to maya

:note: ``createWorkflow`` method must be supported in a module keeping workflows
:todo: it would be better to have the createWorkflow method in some sort of workflowManager,
	for now that appears like overkill though 
"""
__docformat__ = "restructuredtext"

from mrv.path import Path
_this_module = __import__( "mrv.automation.workflows", globals(), locals(), ['workflows'] )
import pydot
import mrv.automation.processes


#{ Initialization
import mrv.automation.base as common

# load all workflows at once
common.addWorkflowsFromDotFiles( _this_module, Path( __file__ ).parent().glob( "*.dot" ) )

#} END initialization





