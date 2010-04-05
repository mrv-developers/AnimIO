# -*- coding: utf-8 -*-
import mrv.maya.ui as ui
import maya.cmds as cmds

class ExportLayout( ui.FormLayout ):
	"""Layout encapsulating all export functionality"""
	
	def __init__(self, **kwargs):
		eTscl = ui.TextScrollList(w=180, numberOfRows=5, allowMultiSelection=True)
		eBttn = ui.Button(label="Export...")
		eHB = ui.Button(label="?", ann="...need help?", w=22, h=22)
		eClm = ui.ColumnLayout(adjustableColumn=True)
		
		if eClm:
			ui.Text(l="timerange:", fn="boldLabelFont", al="left")
			eGr0 = ui.RadioButtonGrp(nrb=1, l1="complete anim.", sl=1)
			ui.RadioButtonGrp(nrb=1, scl=eGr0, l1="custom:")
			eRowTR = ui.RowLayout(nc=2, cw=(1, 45), adj=2)
			eRowTR.p_cw=(2, 40)
			
			if eRowTR:
				eSTrTf = ui.TextField(en=0, w=44)
				eETrTf = ui.TextField(en=0, w=38)
			eRowTR.setParentActive()
			
			ui.Text(l="")
			ui.Text(l="")
			ui.Text(l="filetype", fn="boldLabelFont", align="left")
			eGr1 = ui.RadioButtonGrp(nrb=1, l1="mayaASCII", sl=1)
			ui.RadioButtonGrp(nrb=1, scl=eGr1, l1="mayaBinary")
			ui.Text(l="")
		# END column layout
		self.setActive()

		# setup 
		t, b, l, r = self.kSides
		self.setup(
			attachForm=[
				(eTscl, t, 0),
				(eTscl, l, 0),
				(eTscl, r, 95),
				
				(eBttn, l, 0),
				(eBttn, b, 0),
				
				(eHB, b, 0),
				(eHB, r, 2),
				
				(eClm, r, 2)], 
			
			attachControl=[
				(eTscl, b, 5, eBttn),
				(eBttn, r, 0, eHB),
				
				(eClm, l, 5, eTscl),
				(eClm, b, 5, eBttn)],
			
			attachNone=[
				(eBttn, t),
				
				(eHB, t),
				(eHB, l),
				
				(eClm, t)] )
	
	
class ImportLayout( ui.FormLayout ):
	"""Layout encapsulating all import functionality"""
	
	def __init__(self, **kwargs):
		iRow1 = ui.RowLayout(cw=(1, 68), nc=2, adj=2)
		
		# prefix
		if iRow1:
			iPrefCB = ui.CheckBox(w=68, l="add prefix:")
			iPrefTF = ui.TextField(en=0)
		iRow1.setParentActive()
		
		# search and replace
		iRow2 = ui.RowLayout(nc=4, cw=(1, 55), adj=4)
		iRow2.p_cw = (2, 50)
		iRow2.p_cw = (3, 42)
		if iRow2:
			iSearchCB = ui.CheckBox(w=55, l="search:")
			iSearchTF = ui.TextField(en=0, w=50)
			ui.Text(w=42, l=" replace:")
			iReplaceTF = ui.TextField(en=0, w=45)
		iRow2.setParentActive()
		
		iAddBttn = ui.Button(en=0, h=15, l="Add")
		iTscl = ui.TextScrollList(name="AnimIOSearchReplace", en=0, w=190, numberOfRows=3, allowMultiSelection=True)
		iDelBttn = ui.Button(en=0, h=15, l="remove selected")
		
		# filter
		iFilterL = ui.TextScrollList(name="AnimIOFilter", w=180, en=0, numberOfRows=5, allowMultiSelection=True)
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
				iSTrTf = ui.TextField(en=0, w=44)
				iETrTf = ui.TextField(en=0, w=38)
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
		self.p_width = 320
		self.p_height = 362
		
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
		