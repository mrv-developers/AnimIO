# -*- coding: utf-8 -*-
"""
Allows to query the maya environment, like variables, version numbers and system
paths.
"""
__docformat__ = "restructuredtext"

from maya import cmds

__all__ = ("appVersion", )

def appVersion( ):
	"""
	:return: tuple( float( version ), int( bits ), string( versionString ) ), the
		version will be truncated to *not* include sub-versions
	:note: maya.cmds.about() will crash if called with an external interpreter
	"""
	bits = 32
	if cmds.about( is64=1 ):
		bits = 64

	versionString = cmds.about( v=1 )
	version = versionString.split( ' ' )[0]
	if version.find( '.' ) != -1:
		version = version[0:3]

	# truncate to float
	version = float( version )
	return ( version, bits, versionString )
