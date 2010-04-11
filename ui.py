# -*- coding: utf-8 -*-
"""Module containing the user interface implementation of the AnimIO library"""
__docformat__ = "restructuredtext"

import animio.lib as lib
import mrv.maya.nt as nt
import mrv.maya.ui as ui
import mrv.maya as mrvmaya
from mrv.path import Path
from mrv.maya.ns import Namespace, RootNamespace
from mrv.maya.util import noneToList

import maya.cmds as cmds
import maya.OpenMayaAnim as apianim

from itertools import chain
import logging
log = logging.getLogger("animio.ui")


class FloatRangeField( ui.RowLayout ):
	"""Implements a queryable range of integers
	:note: it uses text fields allowing them to be empty"""
	
	#{ Signals
	# none currently, but if this was a real element, it would surely allow changed
	# events to happen
	#} END signals
	
	def __new__(cls, *args, **kwargs):
		"""Assure we always have two columns with an appropriate size"""
		# bail out early, otherwise we have to verify all our creation flags
		if kwargs:
			raise ValueError("Configure me afterwards please")
			
		kwargs['nc'] =  2
		kwargs['cw2'] = (40,40)
		kwargs['adj'] = 2
		
		return super(FloatRangeField, cls).__new__(cls, *args, **kwargs)
		
		
	def __init__(self, *args, **kwargs):
		"""Build our interface"""
		
		ui.TextField(w=44)
		ui.TextField(w=38)
		
		# hide that we are a layout actually and restore the previous parent
		self.setParentActive()
		
		
	#{ Interface
	
	def get(self):
		""":return: Tuple(floatStartRance, floatEndRange)
		:raise ValueError: if one of the ranges is invalid"""
		fs, fe = self.children()
		return (float(fs.p_text), float(fe.p_text))
	
	def set(self, start, end):
		"""Set the range of this element
		:param start: start of the range as float
		:param end: end of the range as float)"""
		fs, fe = self.children()
		fs.p_text = "%g" % start
		fe.p_text = "%g" % end
	
	def clear(self):
		"""Don't display any value, clear out the existing ones"""
		for field in self.children():
			field.p_text = ""
		# END for each field
	
	def setEnabled(self, state):
		for field in reversed(self.children()):
			field.p_enable = state
			
			# refresh the UI basically, also good to have the focus where you want it
			field.setFocus()
		# END for each child
		
	#} END interface
	
	
class NodeSelector( ui.TextScrollList ):
	"""Element allowing the user to select nodes.
	Either selected ones, or by namespace. The interface provides methods to retrieve
	that information
	
	:note: requires update once the scene changes - the parent is responsible for this"""
	
	kSelectedNodes = "Selected Nodes"
	
	def __new__(cls, *args, **kwargs):
		"""Initialize the instance according to our needs
		
		:param **kwargs: Additional configuration
		
			* **show_selected_nodes** : If True, default True, the user may specify 
			to get the current node selection included in the managed set of nodes
		"""
		show_selected = kwargs.pop('show_selected_nodes', True)
		if kwargs:
			raise ValueError("Please do not specify any kwargs")
		# END input handling
		
		kwargs['allowMultiSelection'] = 1
		inst = super(NodeSelector, cls).__new__(cls, *args, **kwargs)
		
		inst._show_selected = show_selected
		return inst
		
	#{ Callbacks
	
	#} END callbacks
	
	#{ Interface
	
	def update(self):
		"""Call to force the element to update according to the contents of the
		scene"""
		curItems = noneToList(self.p_selectItem)
		self.p_removeAll = 1
		
		# add all items according to the scene and the configuration
		if self._show_selected:
			self.p_append = self.kSelectedNodes
		
		for ns in RootNamespace.children():
			self.p_append = ns
		# END for each namespace in scene
		
		# reselect previous items
		for sli in curItems:
			try:
				self.p_selectItem = sli
			except RuntimeError:
				pass
			# END ignore exceptions
		# END for each previously selected item
		
	def uses_selection(self):
		""":return: True if the user wants to handle selected nodes"""
		return self.kSelectedNodes in noneToList(self.p_selectItem)
		
	def set_uses_selection(self, state):
		"""Sets this element to return selected nodes when queried in 'iter_nodes' 
		if state is True
		:note: only works if set_show_selected was called with a True value
		:return: self"""
		if not self._show_selected:
			raise ValueError("This element does not allow to use 'Selected Nodes'")
			
		if state:
			self.p_selectItem = self.kSelectedNodes
		else:
			self.p_deselectItem = self.kSelectedNodes
		# END 
		return self
			
	def set_show_selected(self, state):
		"""If state is True, we will allow the user to pick 'selected nodes'
		:return: self"""
		self._show_selected = state
		self.update()
		return self
		
	def show_seleted(self):
		return self._show_selected
		
	def selected_namespaces(self):
		""":return: list(Namespace, ...) list of Namespace objects which have 
		been selected"""
		out = list()
		for item_name in noneToList(self.p_selectItem):
			if item_name == self.kSelectedNodes:
				continue
			# END skip sel node special item
			
			ns = Namespace(item_name)
			out.append(ns)
			assert ns.exists(), "Selected namespace did not exist: %s " % ns
		# END for each item
		return out
		
	def select_namespaces(self, iter_ns):
		"""Select the given namespaces on our list if they exist.
		:param iter_ns: iterable yielding namespace objects - they must be absolute
		:return: self"""
		for ns in iter_ns:
			assert str(ns) != self.kSelectedNodes, "Cannot change our node-selection state here"
			try:
				self.p_selectItem = ns
			except RuntimeError:
				pass
			# END ignore errors
		# END for each namespace to selet
		
		return self
		
	def iter_nodes(self, *args, **kwargs):
		"""
		:return: iterator yielding all selected nodes ( if set by the user )
			as well as all nodes in all selected namespaces
		:param *args: passed to ``Namespace.iterNodes``
		:param **kwargs: passed to ``Namespace.iterNodes``
		:note: *args and **kwargs are passed to ``iterSelectionList`` as good 
		as applicable"""
		iterators = list()
		
		# HANDLE SELECTIONs
		if self.uses_selection():
			# configure the selection list iterator as good as we can
			iterkwargs = dict()
			if args:
				iterkwargs['filterType'] = args[0]
			# END use type filter
			iterkwargs['asNode'] = kwargs.get('asNode', True)
			iterkwargs['handlePlugs'] = False
			
			iterators.append(nt.activeSelectionList().mtoIter(**iterkwargs))
		# END handle selected nodes
		
		# HANDLE NAMESPACES
		for ns in self.selected_namespaces():
			iterators.append(ns.iterNodes(*args, **kwargs))
		# END for each namespace
		
		return chain(*iterators)
	
	#} END interface
		

class ExportLayout( ui.FormLayout ):
	"""Layout encapsulating all export functionality"""
	
	#{ Annotations 
	aHelp = "...need Help?"
	aExport = "Export the current selection into a file of your choice"
	
	#} END annotations
	
	def __init__(self, *args, **kwargs):
		
		#{ members we care about 
		self.nodeselector = None
		self.range = None
		self.filetype = None
		self.rangetype = None
		#} END members 
		
		# CREATE UI
		############
		self.nodeselector = NodeSelector()
		eBttn = ui.Button(label="Export...", ann=self.aExport)
		eHB = ui.Button(	label="?", ann=self.aHelp, w=22, h=22)
		
		# RIGHT HAND SIDE
		#################                         
		eClm = ui.ColumnLayout(adjustableColumn=True)
		if eClm:
			# TIME RANGE 
			############
			# NOTE: for now we deactivate the range, as we do not yet support it
			ui.Text(l="Timerange:", fn="boldLabelFont", al="left").p_manage = False
			self.rangetype = ui.RadioCollection()
			if self.rangetype:
				ui.RadioButton(l="complete anim.", sl=1).p_manage = False
				anim_mode_custom = ui.RadioButton(l="custom:")
				anim_mode_custom.p_manage = False
			# END radio collection
			
			self.range = FloatRangeField()
			self.range.p_manage = False
			
			
			ui.Separator(h=40, style="none")
			
			# FILE TYPE
			###########
			ui.Text(l="Filetype", fn="boldLabelFont", align="left")
			self.filetype = ui.RadioCollection()
			if self.filetype:
				ui.RadioButton(l="mayaAscii", sl=1)
				ui.RadioButton(l="mayaBinary")
			# END radio collection
			
			ui.Separator(h=20, style="none")
		# END column layout
		self.setActive()

		# SETUP FORM
		############
		t, b, l, r = self.kSides
		self.setup(
			attachForm=[
				(self.nodeselector, t, 0),
				(self.nodeselector, l, 0),
				(self.nodeselector, r, 95),
				
				(eBttn, l, 0),
				(eBttn, b, 0),
				
				(eHB, b, 0),
				(eHB, r, 2),
				
				(eClm, r, 2)], 
			
			attachControl=[
				(self.nodeselector, b, 5, eBttn),
				(eBttn, r, 0, eHB),
				
				(eClm, l, 5, self.nodeselector),
				(eClm, b, 5, eBttn)],
			
			attachNone=[
				(eBttn, t),
				
				(eHB, t),
				(eHB, l),
				
				(eClm, t)] )
		
		
		# SETUP CONNECTIONS
		###################
		# connections we setup here as we don't need to keep the elements around
		# for this simple secondary behaviour
		anim_mode_custom.e_changeCommand = self._range_mode_changed
		eBttn.e_released = self._on_export
		eHB.e_released = self._show_help
		
		# SET INITIAL STATE
		###################
		self._range_mode_changed(anim_mode_custom)
		self.update()
		
		
	#{ Callbacks
	
	def _range_mode_changed(self, sender, *args):
		"""React if the animation mode changes, either enable our custom entry
		field, or disable it"""
		enable = sender.p_select
		self.range.setEnabled(enable)
		
		# set to playback range or clear the field
		if enable:
			self.range.set(	apianim.MAnimControl.animationStartTime().value(), 
							apianim.MAnimControl.animationEndTime().value())
		else:
			self.range.clear()
		# END additional setop
			
	def _on_export(self, sender, *args):
		"""Perform the actual export after gathering UI data"""
		# NOTE: Ignores timerange for now
		if not self.nodeselector.uses_selection() and not self.nodeselector.selected_namespaces():
			raise ValueError("Please select what to export from the scroll list")
		# END handle invalid input
		
		# GET FILEPATH
		# on linux, only one filter is possible - it would be good to have a 
		# capable file dialog coming from MRV ( in 2011 maybe just an adapter to 
		# fileDialog2 )
		file_path = cmds.fileDialog(mode=1,directoryMask="*.mb")
		if not file_path:
			return
		# END bail out
		
		extlist = ( ".ma", ".mb" )
		collection = [ p.basename() for p in ui.UI(self.filetype.p_collectionItemArray) ]
		target_ext = extlist[collection.index(self.filetype.p_select)]
		
		file_path = Path(file_path)
		file_path = file_path.stripext() + target_ext
		
		lib.AnimInOutLibrary.export(file_path, self.nodeselector.iter_nodes(asNode=False))
		
	def _show_help(self, sender, *args):
		print "TODO: link to offline docs once they are written"
		
	#} END callbacks
	
	#{ Interface 
	def update(self):
		"""Refresh our elements to represent the current scene state"""
		self.nodeselector.update()
	
	#} END interface


class ConverterControl(ui.FormLayout):
	"""Implements an interface to a layout allowing the user to enter search and replace
	tokens"""
	
	def __init__(self):
		"""initialize our child controls"""
		self.tfsearch = None
		self.tfreplace = None
		self.tfprefix = None
		self.cbprefix = None
		
		
		# PREFIX
		#########
		rlPref = ui.RowLayout(nc=2, adj=2)
		if rlPref:
			cbPref = self.cbprefix = ui.CheckBox(l="add prefix:")
			tfPref = self.tfprefix = ui.TextField()
			rlPref.p_cw = (1, cbPref.p_w)
			
			# initial setup 
			cbPref.p_value = False
			tfPref.p_enable = cbPref.p_value
		rlPref.setParentActive()
		
		# SEARCH AND REPLACE
		####################
		cbSearch = ui.CheckBox(l="search:")
		tfSearch = self.tfsearch = ui.TextField()
		tReplace = ui.Text(l=" replace:")
		tfReplace = self.tfreplace = ui.TextField()
		
		# initial setup
		cbSearch.p_value = False
		tfSearch.p_enable = cbSearch.p_value
		tfReplace.p_enable = cbSearch.p_value
		
			
		# TEXTSCROLLLIST + BUTTONS
		###########################
		small = 20
		btnAdd = ui.Button(h=small, l="Add")
		tslSR = ui.TextScrollList(name="AnimIOSearchReplace", w=190, numberOfRows=3, allowMultiSelection=True)
		btnDel = ui.Button(h=small, l="Remove Selected")
		
		k = 0
		lk = 10
		t, b, l, r = self.kSides
		
		self.setup( attachForm=[ 
						(rlPref, t, 0),
						(rlPref, r, k),
						(rlPref, l, k),
						(cbSearch, l, k),
						(tfReplace, r, k),
						(btnAdd, l, k), 
						(btnAdd, r, k),
						(tslSR, l, k),
						(tslSR, r, k),
						(btnDel, l, k),
						(btnDel, r, k),
						(btnDel, b, k),
						], # attach form
						
						attachPosition=[
						(tReplace, l, k, 50)
						],  # attach position
						
						attachNone=[
						(tReplace, r), 
						(cbSearch, r),
						(btnAdd, b),
						(btnDel, t),
						], # attach none
						
						attachControl=[
						(tfSearch, l, k, cbSearch),
						(cbSearch, t, lk, rlPref),
						(tfSearch, t, lk, rlPref),
						(tReplace, t, lk, rlPref),
						(tfReplace, t, lk, rlPref),
						(tfSearch, r, k, tReplace),
						(tfReplace, l, k, tReplace),
						(btnAdd, t, k, cbSearch),
						(tslSR, t, k, btnAdd), 
						(tslSR, b, k, btnDel),
						]) # attach control
		# END setup form
		self.setParentActive()
		
		# SETUP CONNECTIONS
		###################
		cbSearch.e_changeCommand = self._search_state_changed
		cbPref.e_changeCommand = self._prefix_state_changed
		
		
	#{ Callbacks
	def _search_state_changed(self, sender, *args):
		self.tfsearch.p_enable = sender.p_value
		self.tfreplace.p_enable = sender.p_value
		if sender.p_value:
			self.tfsearch.setFocus()
	
	def _prefix_state_changed(self, sender, *args):
		self.tfprefix.p_enable = sender.p_value
		if sender.p_value:
			self.tfprefix.setFocus()
		
	#} END callbacks
		
	#{ Interface 
	def update(self):
		"""Setup this control to represent the actual scene state"""
		
		
	#} END interface 
	
class ImportLayout( ui.FormLayout ):
	"""Layout encapsulating all import functionality"""
	
	def __init__(self, **kwargs):
		self.nodeselector = None
		self.converter = None
		
		# Converter
		####################
		convControl = self.converter = ConverterControl()
		
		# filter
		selector = self.nodeselector = NodeSelector()
		cbFilter = ui.CheckBox(w=100, l="filtered input:")
		
		# initial setup, this way we don't have to store cbFilter
		cbFilter.p_value = False
		selector.p_enable = cbFilter.p_value
	
		# buttons
		btnImport = ui.Button(l="Import...")
		btnIHlp = ui.Button(label="?", ann="...need help?", w=22, h=22)
		
		# OPTIONS
		#########
		# Currently disabled as we don't yet support anything special yet
		clOpts = ui.ColumnLayout(w=90, rs=2, adjustableColumn=True)
		# if its  managed again, adjust the setup of the formlayout, it doesnt work
		# in this case ( although it should )
		clOpts.p_manage=False
		
		if clOpts:
			ui.Text(w=90, h=20, l="options:", fn="boldLabelFont", align="left")
			iAniRepGr = ui.RadioButtonGrp(w=90, nrb=1, l1="replace", sl=1)
			ui.RadioButtonGrp(nrb=1, scl=iAniRepGr, w=90, l1="insert")
			ui.Text(w=90, h=20, l="import at...", fn="boldLabelFont", align="left")
			iOriTimeGr = ui.RadioButtonGrp(w=90, nrb=1, l1="original time", sl=0)
			ui.RadioButtonGrp(w=90, nrb=1, scl=iOriTimeGr, l1="current time", sl=1)
			ui.Text(w=90, h=20, l="load timerange:", fn="boldLabelFont", align="left")
			
			iTrCol = ui.RadioCollection()
			iTrRadioG = list()
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="complete anim.", al="left"))
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="from file", al="left", sl=True))
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="custom:", al="left"))
			iRow3 = ui.RowLayout(nc=2, cw=(1, 45), adj=2)
			iRow3.p_cw=(2, 40)
			if iRow3:
				iSTrTf = ui.TextField(w=44)
				iETrTf = ui.TextField(w=38)
			iRow3.setParentActive()
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="last pose", al="left"))
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="first pose", al="left"))
		# END column layout
		self.setActive()
	
		t, b, l, r = self.kSides
		lk = 10
		sk = 2
		self.setup(
			attachForm=[
				(convControl, t, lk),
				(convControl, l, sk),
				(cbFilter, l, sk),
				(btnImport, l, 0),
				(btnImport, b, 0),
				(btnIHlp, b, 0),
				(btnIHlp, r, sk),
				(clOpts, r, 0),
				(clOpts, b, 0),
				(clOpts, t, 0),
				(selector, l, sk),
				
				# remove once clOpts is managed again
				(convControl, r, sk), 
				(selector, r, sk), 
				(cbFilter, r, sk)
				],  # attach form
			
			attachControl=[
				(convControl, b, lk, cbFilter),
				(btnImport, r, 0, btnIHlp),
				(selector, t, 5, cbFilter),
				(selector, b, 5, btnImport),
				
				# enable once clOpts is manaaged again
				#(cbFilter, r, lk, clOpts),
				#(convControl, r, lk, clOpts),
				#(selector, r, lk, clOpts),
				], # attach control
				
			attachNone=[
				(clOpts, l),
				(cbFilter, b),
				(btnImport, t),
				(btnIHlp, t),
				(btnIHlp, l),
				], # attach None
				
			attachPosition=[
				(cbFilter, t, 25, 50),
				] # attach position
				)# END setup
		
		
		# SETUP CONNECTIONS
		###################
		cbFilter.e_changeCommand = self._filter_enable_state_changed
		
		
		# initialize
		self.update()
		
		
	#{ Callbacks 
	def _filter_enable_state_changed(self, sender, *args):
		self.nodeselector.p_enable = sender.p_value
	
	#} END callbacks
	
	#{ Interface 
	def update(self):
		"""Trigger an update of the full import UI"""
		self.converter.update()
		self.nodeselector.update()
		
	#} END interface
		

class AnimIOLayout( ui.TabLayout ):
	"""Represents a layout for exporting and importing animation"""
	
	def __init__(self, *args, **kwargs):
		"""Initialize ourselves with ui elements"""
		# CREATE ELEMENTS
		#################
		eFrame = ui.FrameLayout(label="Export Animation Of", labelAlign="top", borderStyle="etchedOut", mw=2, mh=5)
		eFrame.p_mw = 2 
		
		if eFrame:
			self.exportctrl = ExportLayout()
		# END frame layout
		self.setActive()
		
		iFrame = ui.FrameLayout(label="Import Animation", labelAlign="top", li=57, borderStyle="etchedOut", mw=2, mh=5)
		if iFrame:
			self.importctrl = ImportLayout()
		# END frame layout
		self.setActive()
			
		self.p_tabLabel = ((eFrame, "EXPORT"), (iFrame, "IMPORT"))
		
		# SETUP CALLBACKS
		#################
		mrvmaya.Scene.afterOpen = self.update
		mrvmaya.Scene.afterNew = self.update
		
		
	#{ Callbacks
	def uiDeleted(self):
		"""Deregister our scene callbacks"""
		mrvmaya.Scene.afterOpen.remove(self.update)
		mrvmaya.Scene.afterNew.remove(self.update)
	
	def update(self, *args):
		"""Update to represent the latest state of the scene"""
		self.exportctrl.update()
	#} END callbacks
		

class AnimIO_UI( ui.Window ):
	
	def __init__(self, *args, **kwargs):
		self.p_title = "mfAnimIO v0.8.py"
		self.p_wh = (320, 362)
		
		self.main = AnimIOLayout()
		