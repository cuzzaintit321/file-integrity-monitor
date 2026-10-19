# File Integrity Monitor

A dependency-free **Python** CLI that snapshots SHA-256 checksums and file permissions, then reports added, missing, and changed files. A new learning and portfolio project built for Jason Edwards, not a claim of production deployment or employer use.

## Run a complete example

Requires Linux and Python 3.11+. No pip packages or administrator privileges are needed.

```bash
mkdir -p demo/source baselines reports
printf 'original\n' > demo/source/settings.txt
python3 integrity.py baseline demo/source baselines/demo.baseline.json
python3 integrity.py check demo/source baselines/demo.baseline.json
printf 'changed\n' > demo/source/settings.txt
python3 integrity.py check demo/source baselines/demo.baseline.json --report reports/drift.report.json
```

The first check exits 0. The second reports `settings.txt` as changed and exits **1** intentionally. It does not restore the file or update your baseline. Choose new baseline/report names when running the example again: existing files are never overwritten.

## Behavior

- Streams each regular file through SHA-256 and records its size and POSIX permission bits.
- Detects content changes, permission changes, added paths, and missing paths.
- Reports symlinks and special entries as skipped, never silently claiming complete coverage.
- Fails on unreadable directory traversal, file access failure, or a file changing during its read.
- Keeps the baseline portable: it records relative paths, not the original absolute root path.
- Requires baseline/report paths to be outside the monitored tree, avoiding self-generated drift.

| Exit | Meaning |
| --- | --- |
| 0 | Baseline created or check completed without drift or skipped entries |
| 1 | Drift found; report includes added/missing/changed files |
| 2 | Invalid input, access/write failure, or skipped coverage without detected drift |

When a baseline has skipped entries, the baseline is still saved but creation exits 2. Check reports include both baseline and current skipped lists. A previously tracked file replaced by a symlink is reported missing and skipped, with drift exit 1. Empty directories, ownership, timestamps, ACLs, extended attributes, hardlink relationships, and symlink targets are not monitored.

The JSON baseline format is versioned and validated before comparison. A check scans only the directory you explicitly provide; it does not open paths taken from the manifest. New output files use exclusive creation and mode `0600`. The JSON report is printed to the terminal even when also saved to a file.

## Limits and safe interpretation

Use static trees under your own control. This is not a filesystem snapshot; edits across multiple files are not captured transactionally. Detected concurrent file edits cause failure, but concurrent directory/path manipulation is not comprehensively protected. It is not intended for adversarial local users or rapidly changing databases. Run it as your normal user against a small lab tree first.

A changed checksum is evidence of changed bytes, **not proof of malware**. The baseline is not signed. Someone able to modify both files and baseline could conceal changes. Keep trusted baselines separately, review changes, and create a new baseline deliberately. There is no daemon, automatic remediation, alert delivery, or scheduled scan in this version.

Baseline/report files reveal directory structure and file hashes. Store them in ignored `baselines/` and `reports/` folders and review before sharing. Do not publish real configuration paths or hashes of confidential files. Very large trees can require substantial I/O, memory for metadata, and a large baseline; resource caps and baseline authentication are not implemented.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Seven tests exercise unchanged files, content/permission drift, additions/deletions, skipped symlinks, output placement, exclusive file creation, baseline path validation, and actual CLI exit/report behavior. Tests run on temporary Linux filesystem trees, not on Jason's computers. CI repeats the checks on Python 3.11 and 3.12 after publication.

## Publish

With GitHub CLI signed in, `bash publish.sh` creates public repository `cuzzaintit321/file-integrity-monitor`, adds its description, commits files, and pushes. It stops if a local checkout or repository already exists; inspect partial results before retrying. No software license has been chosen on your behalf.
