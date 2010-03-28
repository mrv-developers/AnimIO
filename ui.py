# -*- coding: utf-8 -*-
import mrv.maya.ui as ui
import maya.cmds as cmds

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
				eForm = ui.FormLayout(numberOfDivisions=100)
				
				if eForm:
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
			
				cmds.formLayout( eForm,	e=1,
					attachForm=[
						(eTscl, "top", 0),
						(eTscl, "left", 0),
						(eTscl, "right", 95),
						
						(eBttn, "left", 0),
						(eBttn, "bottom", 0),
						
						(eHB, "bottom", 0),
						(eHB, "right", 2),
						
						(eClm, "right", 2)], 
					
					attachControl=[
						(eTscl, "bottom", 5, eBttn),
						(eBttn, "right", 0, eHB),
						
						(eClm, "left", 5, eTscl),
						(eClm, "bottom", 5, eBttn)],
					
					attachNone=[
						(eBttn, "top"),
						
						(eHB, "top"),
						(eHB, "left"),
						
						(eClm, "top")])
			# END export
			
			tab.setActive()
			iFrame = ui.FrameLayout(label="Import Animation", labelAlign="top", li=57, borderStyle="etchedOut", mw=2, mh=5)
			
			if iFrame:
				iForm =  ui.FormLayout(numberOfDivisions=100)
				
				if iForm:
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
				
				cmds.formLayout( iForm,	e=1,
					attachForm=[
						(iRow1, "top", 0),
						(iRow1, "right", 2),
						
						(iRow2, "top", 25),
						(iRow2, "right", 2),
						
						(iAddBttn, "right", 2),
						(iDelBttn, "right", 2),
						(iFilterCB, "right", 2),
						
						(iBttn, "left", 0),
						(iBttn, "bottom", 0),
						
						(iHB, "bottom", 0),
						(iHB, "right", 2),
						
						(iCol, "left", 0),
						(iFilterL, "right", 2),
						(iTscl, "right", 2)],
					
					attachControl=[
						(iRow1, "bottom", 5, iRow2),
						(iRow1, "left", 10, iCol),
						
						(iRow2, "left", 10, iCol),
						
						(iAddBttn, "top", 5, iRow2),
						(iAddBttn, "left", 10, iCol),
						
						(iDelBttn, "bottom", 5, iFilterCB),
						(iDelBttn, "left", 10, iCol),
						(iBttn, "right", 0, iHB),
						
						(iFilterCB, "left", 10, iCol),
						(iFilterL, "top", 5, iFilterCB),
						(iFilterL, "bottom", 5, iBttn),
						(iFilterL, "left", 10, iCol),
						
						(iTscl, "top", 5, iAddBttn),
						(iTscl, "bottom", 5, iDelBttn),
						(iTscl, "left", 10, iCol)],
						
					attachNone=[
						(iDelBttn, "top"),
						(iFilterCB, "bottom"),
						(iBttn, "top"),
						(iHB, "top"),
						(iHB, "left")],
						
					attachPosition=[
						(iFilterCB, "top", 25, 50),
						(iCol, "bottom", -110, 50)])
				tab.setActive()
			#END import
		
		tab.p_tabLabel = ((eFrame, "EXPORT"), (iFrame, "IMPORT"))
		# END TabLayout
		