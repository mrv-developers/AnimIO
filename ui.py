# -*- coding: utf-8 -*-
"""Module containing the user interface implementation of the AnimIO library"""

import mrv.maya.ui as ui

import maya.cmds as cmds
import maya.OpenMayaAnim as apianim

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


class ExportLayout( ui.FormLayout ):
	"""Layout encapsulating all export functionality"""
	
	#{ Annotations 
	aHelp = "...need Help?"
	aExport = "Export the current selection into a file of your choice"
	
	#} END annotations
	
	def __init__(self, *args, **kwargs):
		
		#{ members we care about 
		self._tsl = None
		self.range = None
		self.filetype = None
		self.rangetype = None
		#} END members 
		
		# CREATE UI
		############
		self._tsl = ui.TextScrollList(w=180, numberOfRows=5, allowMultiSelection=True)
		eBttn = ui.Button(label="Export...", ann=self.aExport)
		eHB = ui.Button(	label="?", ann=self.aHelp, w=22, h=22)
		
		# RIGHT HAND SIDE
		#################                         
		eClm = ui.ColumnLayout(adjustableColumn=True)
		if eClm:
			# TIME RANGE 
			############
			ui.Text(l="Timerange:", fn="boldLabelFont", al="left")
			self.rangetype = ui.RadioCollection()
			if self.rangetype:
				ui.RadioButton(l="complete anim.", sl=1)
				anim_mode_custom = ui.RadioButton(l="custom:")
			# END radio collection
			
			self.range = FloatRangeField()
			
			ui.Separator(h=40, style="none")
			
			# FILE TYPE
			###########
			ui.Text(l="Filetype", fn="boldLabelFont", align="left")
			self.filetype = ui.RadioCollection()
			if self.filetype:
				ui.RadioButton(l="mayaASCII", sl=1)
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
				(self._tsl, t, 0),
				(self._tsl, l, 0),
				(self._tsl, r, 95),
				
				(eBttn, l, 0),
				(eBttn, b, 0),
				
				(eHB, b, 0),
				(eHB, r, 2),
				
				(eClm, r, 2)], 
			
			attachControl=[
				(self._tsl, b, 5, eBttn),
				(eBttn, r, 0, eHB),
				
				(eClm, l, 5, self._tsl),
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
		pass
	
	def _show_help(self, sender, *args):
		print "TODO: link to offline docs once they are written"
		
	#} END callbacks
		
	
	
class ImportLayout( ui.FormLayout ):
	"""Layout encapsulating all import functionality"""
	
	def __init__(self, **kwargs):
		iRow1 = ui.RowLayout(cw=(1, 68), nc=2, adj=2)
		
		# prefix
		if iRow1:
			iPrefCB = ui.CheckBox(w=68, l="add prefix:")
			iPrefTF = ui.TextField()
		iRow1.setParentActive()
		
		# search and replace
		iRow2 = ui.RowLayout(nc=4, cw=(1, 55), adj=4)
		iRow2.p_cw = (2, 50)
		iRow2.p_cw = (3, 42)
		if iRow2:
			iSearchCB = ui.CheckBox(w=55, l="search:")
			iSearchTF = ui.TextField(w=50)
			ui.Text(w=42, l=" replace:")
			iReplaceTF = ui.TextField(w=45)
		iRow2.setParentActive()
		
		small = 20
		iAddBttn = ui.Button(h=small, l="Add")
		iTscl = ui.TextScrollList(name="AnimIOSearchReplace", w=190, numberOfRows=3, allowMultiSelection=True)
		iDelBttn = ui.Button(h=small, l="Remove Selected")
		
		# filter
		iFilterL = ui.TextScrollList(name="AnimIOFilter", w=180, numberOfRows=5, allowMultiSelection=True)
		iFilterCB = ui.CheckBox(w=100, l="filtered input:")
	
		# buttons
		iBttn = ui.Button(l="Import...")
		iHB = ui.Button(label="?", ann="...need help?", w=22, h=22)
		
		# options
		iCol = ui.ColumnLayout(w=90, rs=2, adjustableColumn=True)
		
		if iCol:
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
			iTrRadioG.append(ui.RadioButton(w=90, cl=iTrCol, l="firs pose", al="left"))
		# END column layout
		self.setActive()
	
		
		t, b, l, r = self.kSides
		self.setup(
			attachForm=[
				(iRow1, t, 0),
				(iRow1, r, 2),
				
				(iRow2, t, 25),
				(iRow2, r, 2),
				
				(iAddBttn, r, 2),
				(iDelBttn, r, 2),
				(iFilterCB, r, 2),
				
				(iBttn, l, 0),
				(iBttn, b, 0),
				
				(iHB, b, 0),
				(iHB, r, 2),
				
				(iCol, l, 0),
				(iFilterL, r, 2),
				(iTscl, r, 2)],
			
			attachControl=[
				(iRow1, b, 5, iRow2),
				(iRow1, l, 10, iCol),
				
				(iRow2, l, 10, iCol),
				
				(iAddBttn, t, 5, iRow2),
				(iAddBttn, l, 10, iCol),
				
				(iDelBttn, b, 5, iFilterCB),
				(iDelBttn, l, 10, iCol),
				(iBttn, r, 0, iHB),
				
				(iFilterCB, l, 10, iCol),
				(iFilterL, t, 5, iFilterCB),
				(iFilterL, b, 5, iBttn),
				(iFilterL, l, 10, iCol),
				
				(iTscl, t, 5, iAddBttn),
				(iTscl, b, 5, iDelBttn),
				(iTscl, l, 10, iCol)],
				
			attachNone=[
				(iDelBttn, t),
				(iFilterCB, b),
				(iBttn, t),
				(iHB, t),
				(iHB, l)],
				
			attachPosition=[
				(iFilterCB, t, 25, 50),
				(iCol, b, -110, 50)])
		

class AnimIO_UI( ui.Window ):
	
	def __init__(self, *args, **kwargs):
		self.p_title = "mfAnimIO v0.8.py"
		self.p_wh = (320, 362)
		
		tab = ui.TabLayout()
		if tab:
			eFrame = ui.FrameLayout(label="Export Animation Of", labelAlign="top", borderStyle="etchedOut", mw=2, mh=5)
			eFrame.p_mw = 2 
			
			if eFrame:
				eForm = ExportLayout()
			# END frame layout
			tab.setActive()
			
			iFrame = ui.FrameLayout(label="Import Animation", labelAlign="top", li=57, borderStyle="etchedOut", mw=2, mh=5)
			if iFrame:
				eForm = ImportLayout()
			# END frame layout
			tab.setActive()
		
		tab.p_tabLabel = ((eFrame, "EXPORT"), (iFrame, "IMPORT"))
		# END TabLayout
		