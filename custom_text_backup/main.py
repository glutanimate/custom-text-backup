# -*- coding: utf-8 -*-

"""
This file is part of the Custom Text Backup add-on for Anki

Main Module, hooks add-on methods into Anki

Copyright: (c) 2017 Glutanimate <https://glutanimate.com/>
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

# TODO: Features that need completion
# - forecast, history
# - note type exceptions
# - date format
# - run commands
# - test on windows / anki2.1, etc.

from __future__ import unicode_literals

import sys
import os
import copy
import io

from aqt import mw
from anki.utils import json

from anki import version as anki_version

from aqt.utils import tooltip
from aqt.qt import *

anki21 = anki_version.startswith("2.1.")
sys_encoding = sys.getfilesystemencoding()

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
    "optionalEntries": {
        "noteTypeName": False,
        "deckName": False,
        "tags": False,
        "scheduling": False,
        "fieldNames": False
    },
    "optionalEntriesOrder": [
        "noteTypeName", "deckName", "tags", "scheduling", "fieldNames"],
    "fieldSeparator": "<--FLDSEP-->",
    "fieldStarter": "<--FLDSTART-->",
    "fieldCloser": "<--FLDEND-->",
    "singleLinePerField": False,
    "singleLineFieldTitle": "<<<<field: {fieldname}>>>>",
    "individualFilePerNote": False,
    "individualFilePerNoteNameFormat": "{nid}_{notetype}",
    "noteSeparator": "=====",
    "exportPath": "~/AnkiBackup",
    "exportFileName": "anki_custom_backup.txt",
    "execBeforeExport": "",
    "execAfterExport": ""
}

snippet_body = """\
nid: {{nid}}
created: {{created}}{snippet_extensions}
fields: {{fields_string}}\
"""

snippet_extensions_dict = {
    "fieldNames": "fieldnames: {fieldnames_string}",
    "deckName": "deck: {deck}",
    "tags": "tags: {tags_string}",
    "scheduling": "history: {history_string}\nforecast: {forecast}",
    "noteTypeName": "notetype: {notetype}"
}


def slugify(value):
    """Sanitize file name"""
    keepcharacters = (' ', '.', '_')
    return "".join(c for c in value if c.isalnum() or c in keepcharacters).rstrip()


class BackupWorker(object):

    # note_data entries safe for use in filenames, etc.
    note_data_formatkeys = ("nid", "notetype", "deck", "created")

    def __init__(self):
        # start with default config and work from there:
        self.config = copy.deepcopy(default_config)
        self.snippet_formatstr = snippet_body
        self.readConfig()
        self.constructSnippetFormatstr()

    def performBackup(self):

        pre_command = self.config["execBeforeExport"]
        post_command = self.config["execBeforeExport"]

        if pre_command:
            self.runCmd(pre_command)

        nids = self.findNids(self.config.get("searchTerm", ""))

        backup_data = self.getBackupData(nids)

        ret = self.writeBackup(backup_data)

        if not ret:
            return False

        if post_command:
            self.runCmd(pre_command)

        tooltip("Backup performed succesfully")

    def readConfig(self):
        if anki21:
            user_config = mw.addonManager.getConfig(__name__)
        else:
            addon_path = os.path.dirname(__file__).decode(sys_encoding)
            config_path = os.path.join(addon_path, "config.json")
            try:
                user_config = json.load(io.open(config_path, encoding="utf-8"))
            except (IOError, OSError, json.decoder.JSONDecodeError):
                user_config = {}
        if not user_config:
            self.writeConfig(default_config)
        self.config.update(user_config)

    def writeConfig(self, config):
        if anki21:
            mw.addonManager.writeConfig(__name__, config)
            return
        addon_path = os.path.dirname(__file__).decode(sys_encoding)
        config_path = os.path.join(addon_path, "config.json")
        with io.open(config_path, 'w', encoding="utf-8") as outfile:
            outfile.write(unicode(json.dumps(config, indent=4,
                                             sort_keys=True, ensure_ascii=False)))

    def constructSnippetFormatstr(self):
        snippet_extensions_list = [""]
        for key in self.config["optionalEntriesOrder"]:
            if not self.config["optionalEntries"][key]:
                continue
            snippet_extensions_list.append(snippet_extensions_dict[key])
        self.snippet_formatstr = self.snippet_formatstr.format(
            snippet_extensions="\n".join(snippet_extensions_list))

    def getBackupDirectory(self):
        export_path = os.path.expanduser(self.config["exportPath"])

        try:
            if not os.path.isdir(export_path):
                os.makedirs(export_path)
        except (IOError, OSError):
            export_path = None

        return export_path

    def getNoteData(self, nid):
        note = mw.col.getNote(nid)
        first_card = note.cards()[0]
        did = first_card.did
        model = note.model()

        note_data = {
            "nid": note.id,
            "did": did,
            "deck": mw.col.decks.name(did),
            "created": note.id,
            "fieldnames": mw.col.models.fieldNames(model),
            "fields": note.fields,
            "notetype": model["name"],
            "tags": note.tags,
            "history": [],
            "forecast": ""
        }

        return note_data

    def getBackupData(self, nids):
        """Get relevant backup data of supplied note IDs

        Arguments:
            nids {list} -- list of note IDs to back up

        Returns:
          backup_data {tuple} -- tuple of snippets list and
                                 format_dicts dictionary list
        """

        flds_sep = self.config["fieldSeparator"]
        flds_start = self.config["fieldStarter"]
        flds_close = self.config["fieldCloser"]
        title_formatstr = self.config["singleLineFieldTitle"]

        snippets = []
        format_dicts = []

        for idx, nid in enumerate(nids):

            note_data = self.getNoteData(nid)

            tags_string = flds_sep.join(note_data["tags"])
            history_string = flds_sep.join(note_data["history"])
            fieldnames_string = flds_sep.join(note_data["fieldnames"])

            if not self.config["singleLinePerField"]:
                fields_string = flds_start + \
                    flds_sep.join(note_data["fields"]) + flds_close

            else:
                annotated_fields = [flds_start]
                for fname, field in zip(note_data["fieldnames"], note_data["fields"]):
                    title = title_formatstr.format(fieldname=fname)
                    annotated_fields.append(title)
                    annotated_fields.append(field)
                    annotated_fields.append("")
                annotated_fields.append(flds_close)
                fields_string = "\n".join(annotated_fields)

            note_data.update({
                "tags_string": tags_string,
                "history_string": history_string,
                "fieldnames_string": fieldnames_string,
                "fields_string": fields_string
            })

            snippet = self.snippet_formatstr.format(**note_data)
            format_data = {key: note_data[key]
                           for key in self.note_data_formatkeys}

            snippets.append(snippet)
            format_dicts.append(format_data)

        backup_data = (snippets, format_dicts)

        return backup_data

    def findNids(self, query):
        return mw.col.findNotes(query)

    def writeBackup(self, backup_data):
        export_path = self.getBackupDirectory()

        if not export_path:
            tooltip("Export directory could not be found/created.<br>"
                    "Please check the config file and try again.")
            return False

        individual_files = self.config["individualFilePerNote"]
        note_sep = self.config["noteSeparator"]
        filename_formatstr = self.config["individualFilePerNoteNameFormat"]
        filename_default = self.config["exportFileName"]

        if not individual_files:
            out_file = os.path.join(export_path, slugify(filename_default))
            separator = "\n" + note_sep + "\n"
            out_text = separator.join(backup_data[0])
            with io.open(out_file, "w+", encoding="utf-8") as f:
                f.write(out_text)
            return

        for snippet, format_dict in zip(*backup_data):
            file_name = slugify(filename_formatstr.format(**format_dict))
            out_file = os.path.join(export_path, file_name)
            with io.open(out_file, "w+", encoding="utf-8") as f:
                f.write(snippet)

    def runCmd(command):
        pass


def createCustomBackup():
    worker = BackupWorker()
    worker.performBackup()


# Set up menus and hooks
backup_action = QAction("Custom Backup", mw)
backup_action.setShortcut(QKeySequence("Ctrl+Alt+B"))
backup_action.triggered.connect(createCustomBackup)
mw.form.menuTools.addAction(backup_action)
