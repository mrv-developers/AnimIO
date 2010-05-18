# -*- coding: utf-8 -*-
"""
Provides methodes to query and alter the currently loaded scene. It covers
most of the functionality of the 'file' command, but has been renamed to scene
as disambiguation to a filesystem file.
"""
__docformat__ = "restructuredtext"

import util as mutil
import mrv.util as util
import maya.OpenMaya as api
import maya.cmds as cmds
from mrv.path import Path

import inspect

__all__ = [ 'Scene' ]


class _SceneEvent( mutil.CallbackEventBase ):
	""" Implements Scene Callbacks"""

	_checkCBSet = set( ( 	api.MSceneMessage.kBeforeNewCheck,
							api.MSceneMessage.kBeforeSaveCheck ) )

	_checkFileCBSet = set( ( 	api.MSceneMessage.kBeforeImportCheck,
							  	api.MSceneMessage.kBeforeOpenCheck,
								api.MSceneMessage.kBeforeExportCheck,
								api.MSceneMessage.kBeforeReferenceCheck,
								api.MSceneMessage.kBeforeLoadReferenceCheck  ) )

	#( Configuration
	use_weakref = False
	remove_on_error = True
	
	weakref_sender = True
	#) END configuration

	# get the proper registration method
	def _getRegisterFunction(self, eventID):
		reg_method = api.MSceneMessage.addCallback
		if eventID in self._checkCBSet:
			reg_method = api.MSceneMessage.addCheckCallback
		elif eventID in self._checkFileCBSet:
			reg_method = api.MSceneMessage.addCheckFileCallback
		# END find registration method
		return reg_method
		
# END SceneEvent



class Scene( util.Singleton, util.EventSender ):
	"""Singleton Class allowing access to the maya scene
	
	You can register all events available in MSceneMessage easily usnig the following 
	syntax:
	
		>>> scene.kBeforeSoftwareRender = myFunctionObject
	
	"""


	kFileTypeMap = { 	""	  : "mayaAscii",		# treat untitled scenes as ma
						".ma" : "mayaAscii",
						".mb" : "mayaBinary" }

	#{ Events 
	sender_as_argument = False
	
	# create events from 'kEventName', creating a corresponding event named 
	# 'eventName'
	for eidName, eid in ((n,v) for n,v in inspect.getmembers(api.MSceneMessage) if n.startswith('k')):
		locals()[util.uncapitalize(eidName[1:])] = _SceneEvent(eid)
	# END for each message id to create
	
	#} END events

	

	#{ Edit Methods
	@classmethod
	def open( cls, scenepath=None, force=False, **kwargs ):
		""" Open the scene at the given scenepath
		
		:param scenepath: The path to the file to be opened
			If None, the currently loaded file will reopened
		:param force: if True, the new scene will be loaded although currently
			loaded contains unsaved changes
		:param kwargs: passed to *cmds.file*
		:return: a Path to the loaded scene"""
		if not scenepath:
			scenepath = cls.name()

		# NOTE: it will return the last loaded reference instead of the loaded file - lets fix this !
		sourcePath = Path( scenepath )
		kwargs.pop('open', kwargs.pop('o', None))
		kwargs.pop('force', kwargs.pop('f', None))
		lastReference = cmds.file( sourcePath.abspath(), open=1, force=force, **kwargs )
		return Path( sourcePath )

	@classmethod
	def new( cls, force = False, **kwargs ):
		""" Create a new scene
		
		:param force: if True, the new scene will be created even though there
			are unsaved modifications
		:param kwargs: passed to *cmds.file*
		:return: Path with name of the new file"""
		kwargs.pop('new', kwargs.pop('n', None))
		kwargs.pop('force', kwargs.pop('f', None))
		return Path( cmds.file( new = True, force = force, **kwargs ) )

	@classmethod
	def rename( cls, scenepath ):
		"""Rename the currently loaded file to be the file at scenepath
		
		:param scenepath: string or Path pointing describing the new location of the scene.
		:return: Path to scenepath
		:note: as opposed to the normal file -rename it will also adjust the extension
		:raise RuntimeError: if the scene's extension is not supported."""
		scenepath = Path(scenepath)
		try:
			cmds.file( rename = scenepath.expandvars() )
			cmds.file( type = cls.kFileTypeMap[ scenepath.ext() ] )
		except KeyError:
			raise RuntimeError( "Unsupported filetype of: " + scenepath  )
		# END exception handling
		
		return scenepath

	@classmethod
	def save( cls, scenepath=None, autodeleteUnknown = False, **kwargs ):
		"""Save the currently opened scene under scenepath in the respective format
		
		:param scenepath: if None, the currently opened scene will be saved, otherwise 
			the name will be changed. Paths leading to the file will automatically be created.
		:param autodeleteUnknown: if true, unknown nodes will automatically be deleted
			before an attempt is made to change the maya file's type
		:param kwargs: passed to cmds.file
		:return: Path at which the scene has been saved."""
		if scenepath is None or scenepath == "":
			scenepath = cls.name( )

		scenepath = Path( scenepath )
		curscene = cls.name()
		try :
			filetype = cls.kFileTypeMap[ scenepath.ext() ]
			curscenetype = cls.kFileTypeMap[ curscene.ext() ]
		except KeyError:
			raise RuntimeError( "Unsupported filetype of: " + scenepath  )

		# is it a save as ?
		if curscene != scenepath:
			cls.rename(scenepath)

		# assure path exists
		parentdir = scenepath.dirname( )
		if not parentdir.exists( ):
			parentdir.makedirs( )
		# END assure parent path exists

		# delete unknown before changing types ( would result in an error otherwise )
		if autodeleteUnknown and curscenetype != filetype:
			cls.deleteUnknownNodes()
		# END handle unkonwn nodes

		# safe the file
		kwargs.pop('save', kwargs.pop('s', None))
		kwargs.pop('type', kwargs.pop('typ', None))
		return Path( cmds.file( save=True, type=filetype, **kwargs ) )

	@classmethod
	def export(cls, outputFile, nodeListOrIterable=None, **kwargs):
		"""Export the given nodes or everything into the file at path
		
		:param outputFile: Path object or path string to which the data should 
			be written to. Parent directories will be created as needed
		:param nodeListOrIterable: if None, everything will be exported. 
			Otherwise it may be an MSelectionList ( recommended ), or a list of
			Nodes, MObjects or MDagPaths
		:param kwargs: passed to cmds.file, see the mel docs for modifying flags
		:return: Path to which the data was exported"""
		outputFile = Path(outputFile) 
		if not outputFile.dirname().isdir():
			outputFile.dirname().makedirs()
		# END create parent dirs
		
		prev_selection = None
		if nodeListOrIterable is None:
			kwargs['exportAll'] = True
		else:
			# export selected mode
			kwargs['exportSelected'] = True
			prev_selection = api.MSelectionList()
			api.MGlobal.getActiveSelectionList(prev_selection)
			
			import nt
			nt.select(nt.toSelectionList(nodeListOrIterable))
		# END handle nodes
		
		typ = kwargs.pop('type', kwargs.pop('typ', cls.kFileTypeMap.get(outputFile.ext(), None)))
		if typ is None:
			raise RuntimeError("Invalid type in %s" % outputFile)
		# END handle type 
		
		try:
			cmds.file(outputFile, type=typ, **kwargs)
			return outputFile
		finally:
			if prev_selection is not None:
				api.MGlobal.setActiveSelectionList(prev_selection)
			# END if we have a selection to restore
		# END handle selection
		
	#} END edit methods

	#{ Utilities
	@classmethod
	def deleteUnknownNodes( cls ):
		"""Deletes all unknown nodes in the scene
		
		:note: only do this if you are about to change the type of the scene during
			save or export - otherwise the operation would fail if there are still unknown nodes
			in the scene"""
		unknownNodes = cmds.ls( type="unknown" )		# using mel is the faatest here
		if unknownNodes:
			cmds.delete( unknownNodes )

	#} END utilities

	#{ Query Methods
	@classmethod
	def name( cls ):
		return Path( cmds.file( q=1, exn=1 ) )

	@classmethod
	def isModified( cls ):
		return cmds.file( q=1, amf=True )
	#} END query methods


# END SCENE

