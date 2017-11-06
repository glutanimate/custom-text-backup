# -*- coding: utf-8 -*-

"""
This file is part of the Custom Text Backup add-on for Anki

Main Module, hooks add-on methods into Anki

Copyright: (c) 2017 Glutanimate <https://glutanimate.com/>
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

# TODO: Features that need completion
# - forecast, history
# - make various fields optional
# - note type exceptions
# - date format
# - run commands
# - test on windows / anki2.1, etc.
# - default config handling

from __future__ import unicode_literals

import sys
import os
import copy
import io

from aqt import mw
from anki.utils import json
from aqt.utils import tooltip

from anki import version as anki_version

from aqt.qt import *

anki21 = anki_version.startswith("2.1.")

if anki21:
    # DEBUG: access debug console; TODO: remove
    QShortcut(QKeySequence("Ctrl+Alt+Shift+D"), mw, activated=mw.onDebug)


default_config = {
    "searchTerm": "",
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

snippet_format = """\
nid: {nid}
notetype: {notetype}
deck: {deck}
tags: {tags_string}
created: {created}
history: {history_string}
forecast: {forecast}
fieldnames: {fieldnames_string}
fields: {fields_string}\
"""


def getConfig():
    if anki21:
        config = mw.addonManager.getConfig(__name__)
    else:
        sys_encoding = sys.getfilesystemencoding()
        addon_path = os.path.dirname(__file__).decode(sys_encoding)
        config_path = os.path.join(addon_path, "config.json")
        try:
            config = json.load(io.open(config_path, encoding="utf-8"))
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

    export_path = os.path.expanduser(config["exportPath"])
    query = config["searchTerm"]

    if not os.path.isdir(export_path):
        os.makedirs(export_path)

    individual_files = config["singleFilePerNote"]
    if not individual_files:
        out_file = os.path.join(
            export_path,
            "anki_custom_backup.txt")
        write_mode = "a+"
    else:
        filename_format = config["singleFileNameFormat"]
        write_mode = "w+"

    individual_field_lines = config["singleLinePerField"]

    fldsep_format = config["fieldSeparator"]
    flds_start = config["fieldStarter"]
    flds_close = config["fieldCloser"]
    nids = mw.col.findNotes(query)

    end = len(nids) - 1
    for idx, nid in enumerate(nids):
        note = mw.col.getNote(nid)
        first_card = note.cards()[0]
        model = note.model()

        nid = note.id
        did = first_card.did
        deck = mw.col.decks.name(did)
        created = nid

        tags = note.tags
        history = []
        forecast = ""
        fieldnames = mw.col.models.fieldNames(model)
        fields = note.fields
        notetype = model["name"]

        # TODO: switch to f-strings once Anki 2.0 becomes obsolete
        format_fields = {
            "nid": nid, "notetype": notetype,
            "deck": deck, "created": created
        }

        fldsep = fldsep_format.format(**format_fields)
        tags_string = fldsep.join(tags)
        history_string = fldsep.join(history)
        fieldnames_string = fldsep.join(fieldnames)

        if individual_files:
            file_name = filename_format.format(**format_fields)
            out_file = os.path.join(export_path, file_name)

        if individual_field_lines:
            title_format = config["singleLineFieldTitle"]

            annotated_fields = [flds_start]
            for fname, field in zip(fieldnames, fields):
                title = title_format.format(fieldname=fname, **format_fields)
                annotated_fields.append(title)
                annotated_fields.append(field)
                annotated_fields.append("")
            annotated_fields.append(flds_close)
            fields_string = "\n".join(annotated_fields)

        else:
            fields_string = flds_start + fldsep.join(fields) + flds_close

        print(fields_string)
        print(type(fields_string))
        data_fields = {
            "nid": nid, "notetype": notetype,
            "deck": deck, "created": created,
            "forecast": forecast,
            "tags_string": tags_string,
            "history_string": history_string,
            "fieldnames_string": fieldnames_string,
            "fields_string": fields_string
        }

        print(data_fields)
        print(snippet_format)

        with io.open(out_file, write_mode, encoding="utf-8") as f:
            res = snippet_format.format(**data_fields)
            f.write(res)
            if not individual_files and idx != end:
                note_separator_format = config["noteSeparator"]
                note_separator = note_separator_format.format(**format_fields)
                f.write("\n" + note_separator + "\n")

    post_command = config.get("execBeforeExport", None)
    if post_command:
        runCmd(pre_command)


# Set up menus and hooks
backup_action = QAction("Custom Backup", mw)
backup_action.setShortcut(QKeySequence("Ctrl+Alt+B"))
backup_action.triggered.connect(performBackup)
mw.form.menuTools.addAction(backup_action)
