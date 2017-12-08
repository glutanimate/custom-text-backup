# -*- coding: utf-8 -*-

"""
This file is part of the Custom Text Backup add-on for Anki

Main Module

Copyright: (c) 2017 Glutanimate <https://glutanimate.com/>
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

from __future__ import unicode_literals

import sys
import os
import copy
import io
import subprocess
import time
from datetime import datetime

from aqt import mw

from anki.utils import json
from anki import version as anki_version

from aqt.utils import tooltip
from aqt.qt import *

anki21 = anki_version.startswith("2.1.")
sys_encoding = sys.getfilesystemencoding()

default_config = {
    "searchTerm": "",
    "noteTypeExceptions": {
        "Basic": ["Back", "Front"],
        "Cloze": ["Text"]
    },
    "optionalEntries": {
        "noteTypeName": False,
        "deckName": False,
        "tags": False,
        "scheduling": False,
        "fieldNames": False
    },
    "optionalEntriesOrder": [
        "noteTypeName", "deckName", "tags", "scheduling", "fieldNames"],
    "dateFormat": "%Y-%M-%d",
    "fieldStarter": "<--FLDSTART-->",
    "fieldCloser": "<--FLDEND-->",
    "fieldSeparator": "<--FLDSEP-->",
    "singleLinePerField": False,
    "singleLineFieldTitle": "<<<<field: {fieldname}>>>>",
    "individualFilePerNote": False,
    "individualFilePerNoteNameFormat": "{nid}_{notetype}",
    "noteSeparator": "=================",
    "exportPath": "~/AnkiBackup",
    "exportFileName": "anki_custom_backup.txt",
    "execBeforeExport": [],
    "execAfterExport": []
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


def unixToDate(timestamp, date_fmt):
    return datetime.fromtimestamp(timestamp / 1000.0).strftime(date_fmt)


def nextDue(c, date_fmt):
    """Return next due date string
    Adapted from aqt.browser
    """
    if c.odid:
        return "(filtered)"
    elif c.queue == 1:
        date = c.due
    elif c.queue == 0 or c.type == 0:
        return "new"
    elif c.queue in (2, 3) or (c.type == 2 and c.queue < 0):
        date = time.time() + ((c.due - mw.col.sched.today) * 86400)
    else:
        return ""
    return time.strftime(date_fmt, time.localtime(date))


def slugify(value):
    """Return sanitized file name"""
    preserve = (' ', '.', '_')
    return "".join(c for c in value if c.isalnum() or c in preserve).rstrip()


class BackupWorker(object):
    """Exports Anki notes to custom-formatted text files

    Initiliaze and call with:
    ```python
    worker = BackupWorker()
    worker.performBackup()
    ```
    """

    # note_data entries safe for use in filenames, etc.
    note_data_formatkeys = ("nid", "notetype", "deck", "created")

    def __init__(self):
        self.readConfig()
        self.constructSnippetFormatStr()
        self.setExportVariables()

    def performBackup(self):
        """Main backup method"""

        if not self.export_path:
            tooltip("Export directory could not be found/created.<br>"
                    "Please check the config file and try again.")
            return False

        pre_command = self.config.get("execBeforeExport", None)
        post_command = self.config.get("execAfterExport", None)

        if pre_command:
            self.runCmd(pre_command)

        nids = self.findNids(self.config.get("searchTerm", ""))
        backup_data = self.getBackupData(nids)
        ret = self.writeBackup(backup_data)

        if ret is False:
            return False

        if post_command:
            self.runCmd(post_command)

        tooltip("Backup performed succesfully")

    def readConfig(self):
        """Parse user-supplied config file or fall back to defaults"""
        # start with default config and work from there:
        config = copy.deepcopy(default_config)
        if anki21:  # use Anki 2.1's inbuilt config management when available
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
        config.update(user_config)
        self.config = config

    def writeConfig(self, config):
        """Save config file in add-on diretory"""
        if anki21:  # use Anki 2.1's inbuilt config management when available
            mw.addonManager.writeConfig(__name__, config)
            return
        addon_path = os.path.dirname(__file__).decode(sys_encoding)
        config_path = os.path.join(addon_path, "config.json")
        with io.open(config_path, 'w', encoding="utf-8") as outfile:
            outfile.write(unicode(json.dumps(config, indent=4,
                                             sort_keys=True,
                                             ensure_ascii=False)))

    def constructSnippetFormatStr(self):
        """Assemble format string for note backup snippets"""
        snippet_extensions_list = [""]
        entries_status = self.config.get("optionalEntries", None)
        entries_order = self.config.get("optionalEntriesOrder", None)
        
        if entries_status:
            if entries_order:
                for key in entries_order:
                    if not entries_status.get(key, False):
                        continue
                    snippet_extensions_list.append(snippet_extensions_dict[key])
            else:
                snippet_extensions_list += list(snippet_extensions_dict.values())

        self.snippet_formatstr = snippet_body.format(
            snippet_extensions="\n".join(snippet_extensions_list))

    def setExportVariables(self):
        self.export_path = self.getBackupDirectory()
        self.run_args = {
            "export_path": self.export_path,
            "export_file": self.config["exportFileName"]
        }

    def getBackupDirectory(self):
        """Check if backup folder exists. Create it if necessary"""
        if not anki21:
            # python2 requires some extra attention when handling paths
            enc_conf_path = self.config["exportPath"].encode("utf-8")
            export_path = os.path.expanduser(enc_conf_path).decode(sys_encoding)
        else:
            export_path = os.path.expanduser(self.config["exportPath"])
        try:
            if not os.path.isdir(export_path):
                os.makedirs(export_path)
        except (IOError, OSError):
            export_path = None
        return export_path

    def getNoteData(self, nid):
        """Get data dictionary for note id"""
        date_fmt = self.config.get("dateFormat", "%Y-%M-%d")

        note = mw.col.getNote(nid)
        model = note.model()
        notetype = model["name"]
        fields = note.fields
        fieldnames = mw.col.models.fieldNames(model)

        if notetype in self.config.get("noteTypeExceptions", {}):
            fieldnames = self.config["noteTypeExceptions"][notetype]
            fields = [note[i] for i in fieldnames if i in note]

        # TODO? support for multi-card notes
        first_card = note.cards()[0]
        did = first_card.did
        rev_dates = mw.col.db.list(
            "select id from revlog where cid = ?", first_card.id)
        history = [unixToDate(unix, date_fmt) for unix in rev_dates]
        forecast = nextDue(first_card, date_fmt)

        note_data = {
            "nid": nid,
            "did": did,
            "deck": mw.col.decks.name(did),
            "created": unixToDate(nid, date_fmt),
            "fieldnames": fieldnames,
            "fields": fields,
            "notetype": model["name"],
            "tags": note.tags,
            "history": history or ["new"],
            "forecast": forecast or "new"
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
        """Query Anki's collection for a search string, return matching nids"""
        return mw.col.findNotes(query)

    def writeBackup(self, backup_data):
        """Write backup to disk"""

        individual_files = self.config["individualFilePerNote"]
        note_sep = self.config["noteSeparator"]
        filename_formatstr = self.config["individualFilePerNoteNameFormat"]
        filename_default = self.config["exportFileName"]

        if not individual_files:
            # pack note snippets into a single file
            out_file = os.path.join(self.export_path, slugify(filename_default))
            separator = "\n" + note_sep + "\n"
            out_text = separator.join(backup_data[0])
            with io.open(out_file, "w+", encoding="utf-8") as f:
                f.write(out_text)
        else:
            # individual files for each note snippet
            for snippet, format_dict in zip(*backup_data):
                file_name = slugify(filename_formatstr.format(**format_dict))
                out_file = os.path.join(self.export_path, file_name)
                with io.open(out_file, "w+", encoding="utf-8") as f:
                    f.write(snippet)

    def runCmd(self, command_array):
        run_args = self.run_args
        if not anki21:
            args = [i.format(**run_args).encode(sys_encoding) 
                    for i in command_array]
        else:
            args = [i.format(**run_args) for i in command_array]
        try:
            subprocess.Popen(args)
        except OSError:
            tooltip("External command produced an error.<br>"
                    "Please confirm that it is assigned correctly.")


def createCustomBackup():
    """Glue function between Anki menu and BackupWorker"""
    worker = BackupWorker()
    worker.performBackup()


# Set up menus and hooks
backup_action = QAction("Custom Backup", mw)
backup_action.setShortcut(QKeySequence("Ctrl+Alt+B"))
backup_action.triggered.connect(createCustomBackup)
mw.form.menuTools.addAction(backup_action)
