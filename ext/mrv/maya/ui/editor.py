# -*- coding: utf-8 -*-
"""
Contains implementations of maya editors
"""
__docformat__ = "restructuredtext"
import base as uibase
import util as uiutil


class EditorBase( uibase.NamedUI, uiutil.UIContainerBase ):
	""" Structural base  for all Layouts allowing general queries and name handling
	Layouts may track their children """

	_properties_ = (
						"panel", "pnl",
						"control", "ctl",
						"mainListConnection", "mlc",
						"forceMainConnection", "fmc",
						"selectionConnection", "slc",
						"highlightConnection", "hlc",
						"filter", "f",
						"lockMainConnection", "lck",
						"stateString", "sts",
						"unlockMainConnection", "ulk",
						"updateMainConnection", "upd",
						"docTag", "dtg"
					)


class ColorEditor( uibase.NamedUI ):
	_properties_ = (
						"rgbValue", "rgb",
						"hsvValue", "hsv",
						"alpha", "a",
						"result", "r"
					)

class BlendShapeEditor( EditorBase ):
	_properties_ = (
						"verticalSliders", "vs",
						"targetControlList", "tcl",
						"targetList", "tl"
					)

class OutlinerEditor( EditorBase ):
	_properties_ = (
						"showShapes", "shp",
						"attrFilter", "af",
						"showAttributes", "atr",
						"showConnected", "con",
						"showAnimCurvesOnly", "aco",
						"showTextureNodesOnly", "tno",
						"showDagOnly", "dag",
						"ignoreDagHierarchy", "hir",
						"autoExpand", "xpd",
						"expandConnections", "xc",
						"showUnitlessCurves", "su",
						"showCompounds", "cmp",
						"showLeafs", "laf",
						"showNumericAttrsOnly", "num",
						"editAttrName", "ean",
						"showUVAttrsOnly", "uv",
						"highlightActive", "ha",
						"highlightSecondary", "hs",
						"autoSelectNewObjects", "as",
						"doNotSelectNewObjects", "dns",
						"dropIsParent", "dip",
						"transmitFilters", "tf",
						"showSelected", "sc",
						"setFilter", "sf",
						"showSetMembers", "ssm",
						"allowMultiSelection", "ams",
						"alwaysToggleSelect", "ats",
						"directSelect", "ds",
						"object", "Obj",
						"displayMode", "dm",
						"expandObjects", "eo",
						"setsIgnoreFilters", "sif",
						"showAttrValues", "av",
						"masterOutliner", "mst",
						"isChildSelected", "ics",
						"attrAlphaOrder", "aao",
						"sortOrder", "so",
						"longNames", "ln",
						"niceNames", "nn",
						"showNamespace", "sn"
					)
	_events_ = 		( "selectCommand", "sec" )

class AnimEditorBase( EditorBase ):
	_properties_ = (
					"displayKeys", "dk",
					"displayTangents", "dtn",
					"displayActiveKeys", "dak",
					"displayActiveKeyTangents", "dat",
					"displayInfinities", "di",
					"autoFit", "af",
					"lookAt", "la",
					"snapTime", "st",
					"snapValue", "sv"
					)

class AnimCurveEditor( AnimEditorBase ):
	_properties_ =	(
					"showResults", "sr",
					"showBufferCurves", "sb",
					"smoothness", "s",
					"resultScreenSamples", "rss",
					"resultUpdate", "ru",
					"clipTime", "ct",
					"curvesShown", "cs"
					)
	_events_ = 		(
					 "normalizeCurvesCommand", "ncc",
					 "denormalizeCurvesCommand", "dcc"
					 )


class RenderEditorBase( EditorBase ):
	_properties_ = (
					"scaleRed", "sr",
					"scaleGreen", "sg",
					"scaleBlue", "sb",
					"singleBuffer", "sbf",
					"doubleBuffer", "dbf",
					"displayImage", "di",
					"loadImage", "li",
					"writeImage", "wi",
					"displayStyle", "dst",
					"removeImage", "ri",
					"removeAllImages", "ra",
					"saveImage", "si",
					"nbImages", "nim"
					)


class RenderWindowEditor( RenderEditorBase ):
	_properties_ = 	(
					"toggle", "tgl",
					"marquee", "mq",
					"resetRegion", "rr",
					"autoResize", "ar",
					"showRegion", "srg",
					"snapshot", "snp",
					"currentCamera", "crc",
					"clear", "cl",
					"frameImage", "fi",
					"frameRegion", "fr",
					"realSize", "rs",
					"caption", "cap",
					"pcaption", "pca",
					"compDisplay", "cd",
					"blendMode", "blm",
					"compImageFile"
					)
	_events_ = 		( "changedCommand", "cc" )


class GlRenderEditor( EditorBase ):
	_properties_ = 	(
					 "viewCameraName", "vcn",
					 "lookThru", "lt",
					 "modelViewName",
					 "glRenderViewName", "rvn"
					 )

class ModelEditor( EditorBase ):
	_properties_ =	(
					 "camera", "cam",
					 "cameraName", "cn",
					 "displayLights", "dl",
					 "bufferMode", "bm",
					 "activeOnly", "ao",
					 "interactive", "i",
					 "twoSidedLighting", "tsl",
					 "displayAppearance", "da",
					 "wireframeOnShaded", "wos",
					 "headsUpDisplay", "hud",
					 "selectionHiliteDisplay", "sel",
					 "useDefaultMaterial", "udm",
					 "useColorIndex", "uci",
					 "wireframeBackingStore", "wbs",
					 "useRGBImagePlane", "ip",
					 "updateColorMode", "ucm",
					 "colorMap", "cm",
					 "backfaceCulling", "bfc",
					 "xray", "xr",
					 "maxConstantTransparency", "mct",
					 "displayTextures", "dtx",
					 "smoothWireframe", "swf",
					 "textureMaxSize", "tms",
					 "textureMemoryUsed", "tmu",
					 "textureAnisotropic", "ta",
					 "textureSampling", "ts",
					 "textureDisplay", "td",
					 "textureHighlight", "th",
					 "fogging", "fg",
					 "fogSource", "fsc",
					 "fogMode", "fmd",
					 "fogDensity", "fdn",
					 "fogEnd", "fen",
					 "fogStart", "fst",
					 "fogColor", "fcl",
					 "shadows", "sdw",
					 "rendererName", "rnm",
					 "rendererList", "rls",
					 "rendererListUI", "rlu",
					 "colorResolution", "crz",
					 "bumpResolution", "brz",
					 "transparencyAlgorithm", "tal",
					 "transpInShadows", "tis",
					 "cullingOverride", "cov",
					 "lowQualityLighting", "lql",
					 "occlusionCulling", "ocl",
					 "useBaseRenderer", "ubr",
					 "nurbsCurves", "nc",
					 "nurbsSurfaces", "ns",
					 "polyMeshes", "pm",
					 "subdivSurfaces", "sds",
					 "planes", "pl",
					 "lights", "lt",
					 "cameras", "ca",
					 "controlVertices", "cv",
					 "grid", "gr",
					 "hulls", "hu",
					 "joints", "j",
					 "ikHandles", "ikh",
					 "deformers", "df",
					 "dynamics", "dy",
					 "fluids", "fl",
					 "hairSystems", "hs",
					 "follicles", "fo",
					 "nCloths", "ncl",
					 "nRigids", "nr",
					 "dynamicConstraints", "dc",
					 "locators", "lc",
					 "manipulators", "mlocators",
					 "dimensions", "dim",
					 "handles", "ha",
					 "pivots", "pv",
					 "textures", "tx",
					 "strokes", "str",
					 "allObjects", "alo",
					 "useInteractiveMode", "ui",
					 "activeView", "av",
					 "sortTransparent", "st",
					 "viewSelected", "vs",
					 "setSelected", "ss",
					 "addSelected", "as",
					 "addObjects", "aob",
					 "viewObjects", "vo",
					 "noUndo", "nud"
					 )


class ClipEditor( AnimEditorBase ):
	_properties_ = 	(
					 "characterOutline", "co",
					 "highlightedBlend", "hb",
					 "highlightedClip", "hc",
					 "selectBlend", "sb",
					 "selectClip", "sc",
					 "deselectAll", "da",
					 "frameAll", "fa",
					 "listAllCharacters", "lac",
					 "listCurrentCharacters", "lc",
					 "menuContext", "mc",
					 "allTrackHeights", "th"
					 )

	_events_ = 		(
					 "clipDropCmd", "cd",
					 "deleteCmd", "dc"
					 )

class DeviceEditor( EditorBase ):
	_properties_ = 	( "takePath", "tp" )


class DynPaintEditor( RenderEditorBase ):
	_properties_ = 	(
					 "clear", "cl",
					 "displayAppearance", "dsa",
					 "displayLights", "dsl",
					 "displayTextures", "dtx",
					 "menu", "mn",
					 "newImage", "ni",
					 "wrap", "wr",
					 "zoom", "zm",
					 "camera", "cam",
					 "paintAll", "pa",
					 "rollImage", "rig",
					 "tileSize", "ts",
					 "snapShot", "snp",
					 "undoCache", "uc",
					 "canvasUndo", "cu",
					 "canvasMode", "cm",
					 "redrawLast", "rl",
					 "refreshMode", "rmd",
					 "autoSave", "as",
					 "saveAlpha", "sa",
					 "drawContext", "drc",
					 "activeOnly", "ao",
					 "fileName", "fil",
					 "saveBumpmap", "sbm",
					 "iconGrab", "ig",
					 "displayFog", "dfg",
					 "currentCanvasSize", "ccs"
					 )


class ComponentEditor( EditorBase ):
	_properties_ = 	(
					 "lockInput", "li",
					 "precision", "pre",
					 "setOperationLabel", "sol",
					 "operationLabels", "ol",
					 "operationCount", "oc",
					 "operationType", "ot",
					 "hideZeroColumns", "hzc",
					 "sortAlpha", "sa",
					 "showObjects", "so",
					 "showSelected", "ss",
					 "floatSlider", "fs",
					 "floatField", "ff",
					 "hidePathName", "hpn",
					 "newTab", "nt",
					 "removeTab", "rt",
					 "selected", "sl"
					)


class SelectionConnection( uibase.NamedUI ):
	_properties_ = 	(
					 "filter", "f",
					 "global", "g",
					 "object", "obj",
					 "connectionList", "lst",
					 "switch", "sw",
					 "editor", "ed",
					 "addTo", "add"
					 "remove", "rm",
					 "findObject", "fo",
					 "identify", "id",
					 "lock", "lck",
					 "clear", "clr",
					 "select", "s",
					 "deselect", "d"
					)

	_events_ = 		(
					 "addScript", "as",
					 "removeScript", "rs"
					)


class ItemFilterBase( uibase.BaseUI ):
	_properties_ = 	(
					 "byName", "bn",
					 "union", "un",
					 "intersect", "in",
					 "difference", "di",
					 "negate", "neg",
					 "text", "t",
					 "classification", "cls",
					 "listBuiltInFilters", "lbf",
					 "listUserFilters", "luf",
					 "listOtherFilters", "lof"
					)

	_events_	= 	(
					 "byScript", "bs",
					 "secondScript", "ss"
					)


class ItemFilter( ItemFilterBase ):
	_properties_ = (
					"byType", "bt",
					"clearByType", "cbt",
					"byBin", "bk",
					"clearByBin", "cbk",
					"category", "cat",
					"uniqueNodeNames", "unn"
					)

class ItemFilterAttr( ItemFilterBase ):
	_properties_ = (
					"hidden", "h",
					"writable", "w",
					"readable", "r",
					"keyable", "k",
					"scaleRotateTranslate", "srt",
					"hasExpression", "he",
					"byNameString", "bns"
					)

class ItemFilterRender( ItemFilterBase ):
	_properties_ = 	(
					 "category", "cat",
					 "shaders", "s",
					 "anyTextures", "at",
					 "textures2d", "t2d",
					 "textures3d", "t3d",
					 "lights", "l",
					 "postProcess", "pp",
					 "renderUtilityNode", "run",
					 "exclusiveLights", "exl",
					 "linkedLights", "ls",
					 "lightSets", "ls",
					 "nonIlluminatingLights", "nil"
					 "nonExclusiveLights", "nxl",
					 "renderableObjectSets", "ros",
					 "texturesProcedural", "tp"
					)
