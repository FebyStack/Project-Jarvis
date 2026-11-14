"""Spike 6: build the Jarvis iPhone shortcut as a file (no token inside), then sign it with `shortcuts sign`.

usage: make_shortcut.py URL OUT_UNSIGNED
The Authorization header holds the placeholder PASTE_TOKEN_HERE; Febriel replaces it himself.
"""
import plistlib, sys, uuid

url, out = sys.argv[1], sys.argv[2]
U = lambda: str(uuid.uuid4()).upper()
dict_id, url_id, say_id, loop_id, rep, cond = U(), U(), U(), U(), U(), U()

def text(s):
    return {"Value": {"string": s}, "WFSerializationType": "WFTextTokenString"}

def var_text(uid, name):  # a text field holding only one action's output
    return {"Value": {"string": "￼", "attachmentsByRange": {"{0, 1}": {"OutputUUID": uid, "OutputName": name, "Type": "ActionOutput"}}},
            "WFSerializationType": "WFTextTokenString"}

def var(uid, name):
    return {"Value": {"OutputUUID": uid, "OutputName": name, "Type": "ActionOutput"}, "WFSerializationType": "WFTextTokenAttachment"}

def fields(*pairs):
    return {"Value": {"WFDictionaryFieldValueItems": [{"WFItemType": 0, "WFKey": text(k), "WFValue": v} for k, v in pairs]},
            "WFSerializationType": "WFDictionaryFieldValue"}

def act(ident, **p):
    return {"WFWorkflowActionIdentifier": ident, "WFWorkflowActionParameters": p}

actions = [
    act("is.workflow.actions.repeat.count", GroupingIdentifier=rep, WFControlFlowMode=0, WFRepeatCount=10),
    act("is.workflow.actions.dictatetext", UUID=dict_id, WFSpeechLanguage="en-US", WFDictateTextStopListening="After Pause"),
    act("is.workflow.actions.downloadurl", UUID=url_id, WFURL=url, WFHTTPMethod="POST", ShowHeaders=True,
        WFHTTPHeaders=fields(("Authorization", text("Bearer PASTE_TOKEN_HERE"))),
        WFHTTPBodyType="JSON", WFJSONValues=fields(("text", var_text(dict_id, "Dictated Text")))),
    act("is.workflow.actions.getvalueforkey", UUID=say_id, WFGetDictionaryValueType="Value", WFDictionaryKey="say",
        WFInput=var(url_id, "Contents of URL")),
    act("is.workflow.actions.speaktext", WFText=var_text(say_id, "Dictionary Value"), WFSpeakTextWait=True),
    act("is.workflow.actions.getvalueforkey", UUID=loop_id, WFGetDictionaryValueType="Value", WFDictionaryKey="loop",
        WFInput=var(url_id, "Contents of URL")),
    # 101 = "does not have any value": the server omits "loop" when the exchange is done. (A text comparison,
    # WFCondition 4 + WFConditionalActionString, loses its value on import in macOS 26 Shortcuts.)
    act("is.workflow.actions.conditional", GroupingIdentifier=cond, WFControlFlowMode=0, WFCondition=101,
        WFInput={"Type": "Variable", "Variable": var(loop_id, "Dictionary Value")}),
    act("is.workflow.actions.exit"),
    act("is.workflow.actions.conditional", GroupingIdentifier=cond, WFControlFlowMode=2),
    act("is.workflow.actions.repeat.count", GroupingIdentifier=rep, WFControlFlowMode=2),
]
shortcut = {"WFWorkflowActions": actions, "WFWorkflowClientVersion": "2700", "WFWorkflowMinimumClientVersion": 900,
            "WFWorkflowMinimumClientVersionString": "900", "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4292093695, "WFWorkflowIconGlyphNumber": 59511},
            "WFWorkflowImportQuestions": [], "WFWorkflowTypes": [], "WFWorkflowInputContentItemClasses": [], "WFWorkflowOutputContentItemClasses": [],
            "WFWorkflowHasShortcutInputVariables": False, "WFQuickActionSurfaces": []}
with open(out, "wb") as f:
    plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
print("wrote", out)
