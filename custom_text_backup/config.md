## Configuring 'Custom Text Backup'

#### Available Options

**searchTerm**

String defining search term:

```json
"searchTerm": "deck:current
```

**optionalEntries**

Dictionary of Boolean values.

Keys: "scheduling", "noteTypeName", "fieldNames", "deckName", "tags"

Optional note data to include in backup:

```json
"optionalEntries": {
    "scheduling": true,
    "noteTypeName": true,
    "fieldNames": true,
    "deckName": true,
    "tags": true
}
```

**optionalEntriesOrder**

List of `optionalEntries` keys (strings).

Allows defining a custom order for `optionalEntries`:

```json
"optionalEntriesOrder": [
    "noteTypeName",
    "deckName",
    "tags",
    "scheduling",
    "fieldNames"
]
```


**noteTypeExceptions**

Dictionary of Lists. Each key should correspond to a note type you want to customize.

Lists govern which fields to include in each case:

```json
"noteTypeExceptions": {
    "Cloze": [
        "Text",
        "Extra"
    ],
    "Basic": [
        "Back",
        "Front"
    ]
},
```

**dateFormat**

String that defines the strftime format used by all date specifications in the backup:

```json
"dateFormat": "%Y-%m-%d",
```

This controls the date format of the `history` data, `forecast` data, and `created` date.

**fieldStart, fieldClose, fieldSeparator**

Strings that control the starting tag, ending tag, and separator between fields:

```json
"fieldStarter": "<--FLDSTART-->",
"fieldCloser": "<--FLDEND-->",
"fieldSeparator": "<--FLDSEP-->",
```

**noteSeparator**

String that separates each note when exporting multiple notes to a single backup file:

```json
"noteSeparator": "===================="
```

**singleLinePerField**

Boolean that controls whether or not to put each field on a separate line:

```json
"singleLinePerField": false
```

**singleLineFieldTitle**

String that separates each field when `singleLinePerField` is `true`. Note that the supplied String will always be surrounded by linebreaks before and after.

```json
"singleLineFieldTitle": "<<<<field: {fieldname}>>>>"
```

**individualFilePerNote**

Boolean that controls whether to export each respective note to a separate text file:

```json
"individualFilePerNote": false
```

**individualFilePerNoteNameFormat**

Format String that controls file names of individual files when `individualFilePerNote` is active:

```json
"individualFilePerNoteNameFormat": "{nid}_{notetype}.txt"
```

Available format variables include: `{nid}`, `{notetype}`, `{deck}`, `{created}`.

**exportPath**

String pointing to the directory the backup files should be saved at. If the path does not exist, the add-on wil create it automatically.

```json
"exportPath": "~/AnkiBackup"
```

**exportFileName**

String describing the filename to use when exporting to a single file

```json
"exportFileName": "anki_custom_backup.txt"
```

This string setting does not support specifying any format variables.


**execBeforeExport**

List describing a command and its arguments that is to be run before performing a backup. This is empty by default, but an example could look as follows:

```json
"execBeforeExport": ["notify-send", "execBeforeExport {export_path}"]
```

The following format variables are supported:

- `{export_path}`: backup directory
- `{export_file}`: backup file name when exporting to a single file 

**execAfterExport**

Just like `execBeforeExport`, but executed after exporting.

E.G.:

```json
"execAfterExport": ["notify-send", "execAfterExport {export_path}"]
```
