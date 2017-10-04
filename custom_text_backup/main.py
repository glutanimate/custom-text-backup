# -*- coding: utf-8 -*-

"""
This file is part of the Custom Text Backup add-on for Anki

Main Module, hooks add-on methods into Anki

Copyright: (c) 2017 Glutanimate <https://glutanimate.com/>
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

from __future__ import unicode_literals

import sys, os
import copy
from aqt import mw
from anki.utils import json
from anki.hooks import addHook
from aqt.utils import tooltip

from anki import version as anki_version

from aqt.qt import *

anki21 = anki_version.startswith("2.1.")

if anki21:
    # DEBUG: access debug console; TODO: remove
    QShortcut(QKeySequence("Ctrl+Alt+Shift+D"), mw, activated=mw.onDebug)


default_config = {
    "searchTerm": "\"Note ID\":1* rated:350 Ba*",
    "noteTypeExceptions": {
        "Basic": ["Back", "Front"],
        "Cloze": ["Text"]
    },
    "dateFormat": "%Y-%M-%D",
    "exportFieldNames": False,
    "exportScheduling": False,
    "exportTags": False,
    "exportDeckName": False,
    "exportNotetypeName": False,
    "fieldSeparator": "<--FLDSEP-->",
    "fieldStarter": "<--FLDSTART-->",
    "fieldCloser": "<--FLDEND-->",
    "singleLinePerField": False,
    "singleLineFieldTitle": "<<<<field: {fieldname}>>>>",
    "singleFilePerNote": False,
    "singleFileNameFormat": "{nid}_{notetype}",
    "noteSeparator": "=====",
    "exportPath": "~/AnkiBackup",
    "execBeforeExport": "",
    "execAfterExport": ""
}

# snippet_format = """\
# nid: {nid}
# notetype: {notetype}
# deck: {deck}
# tags: {tags}
# created: {created}
# history: {history}
# forecast: {forecast}
# fieldnames: {fieldnames}
# fields: {fields}\
# """

def getConfig():
    if anki21:
        config = mw.addonManager.getConfig(__name__)
    else:
        sys_encoding = sys.getfilesystemencoding()
        addon_path = os.path.dirname(__file__).decode(sys_encoding)
        config_path = os.path.join(addon_path, "config.json")
        try:
            config = json.load(open(config_path))
        except (IOError, OSError):
            config = None
    return config if config else {}

def runCmd(command):
    pass




def performBackup():
    # start with default config and work from there:
    config = copy.deepcopy(default_config)
    config.update(getConfig())


    pre_command = config["execBeforeExport"]
    if pre_command:
        runCmd(pre_command)
    
    export_path = config["exportPath"]
    query = config["searchTerm"]
    
    if not os.path.isdir(export_path):
        os.makedirs(export_path)
    
    individual_files = config["singleFilePerNote"]
    if not individual_files:
        out_file = os.path.join(
            os.path.expanduser(export_path),
            "anki_custom_backup.txt")
        write_mode = "a+"
    else:
        filename_format = config["singleFileNameFormat"]
        write_mode = "w+"

    individual_field_lines = config["singleLinePerField"]


    fldsep = config["fieldSeparator"]
    flds_start = config["fieldStarter"]
    flds_close = config["fieldCloser"]
    notes = mw.col.findNotes(query)
    
    for note in notes:

        snippets = []

        nid = ""
        deck = ""
        created = ""

        tags = []
        history = []
        forecast = ""
        fieldnames = []
        fields = []
        notetype = ""

        format_fields = {var.__name__, var for var in 
                            (nid, notetype, deck, tags, created)
                        }



        # format_fields = {
        #     "nid": nid,
        #     "notetype": notetype,
        #     "deck": deck,
        #     "tags": tags,
        #     "created": created,
        #     "history": history,
        #     "forecast": forecast,
        #     "fieldnames": fieldnames,
        #     "fields": fields,
        # }

        if individual_files:
            file_name = filename_format.format(**format_fields)
            out_file = os.path.join(export_path, file_name)

        if individual_field_lines:
            title_format = config["singleLineFieldTitle"]
        
            annotated_fields = [flds_start]
            for fname, field in zip(fnames, fields):
                title = title_format.format(**format_fields)
                annotated_fields.append(title)
                annotated_fields.append(field)
                annotated_fields.append("")
            annotated_fields.append(flds_close)
            fields_string = "\n".join(annotated_fields)

        else:
            fields_string = flds_start + fldsep.join(fields) + flds_close

        fldsep = fldsep_format.format(**format_fields)



        with open(out_file, write_mode) as f:
            f.write("\n".join(snippets))




    post_command = config.get("execBeforeExport", None)
    if post_command:
        runCmd(pre_command)




# Set up menus and hooks
backup_action = QAction("Custom Backup", mw)
backup_action.setShortcut(QKeySequence("Ctrl+Alt+B"))
backup_action.triggered.connect(performBackup)
mw.form.menuTools.addAction(backup_action)