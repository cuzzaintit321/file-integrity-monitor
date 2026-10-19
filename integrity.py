"""Compare a static directory tree to a SHA-256 baseline. Standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def scan(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Target must be a directory')
    files, skipped = {}, []
    # Abort on unreadable directories instead of treating their files as deleted.
    def fail(error):
        raise error
    for parent, directories, names in os.walk(root, followlinks=False, onerror=fail):
        directories.sort()
        names.sort()
        for name in list(directories):
            path = Path(parent) / name
            if path.is_symlink():
                skipped.append(path.relative_to(root).as_posix())
                directories.remove(name)
        for name in names:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                skipped.append(relative)
                continue
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    skipped.append(relative)
                    continue
                checksum = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    checksum.update(block)
                after = os.fstat(stream.fileno())
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise ValueError(f'File changed while reading: {relative}')
                files[relative] = {'sha256': checksum.hexdigest(), 'size': before.st_size,
                                   'mode': stat.S_IMODE(before.st_mode)}
    return {'version': 1, 'algorithm': 'sha256', 'captured_at': utc_now(),
            'files': files, 'skipped': sorted(skipped)}


def validate(baseline):
    if not isinstance(baseline, dict) or baseline.get('version') != 1 or baseline.get('algorithm') != 'sha256' or not isinstance(baseline.get('files'), dict):
        raise ValueError('Unsupported baseline format')
    for name, item in baseline['files'].items():
        p = PurePosixPath(name)
        if not name or p.is_absolute() or '..' in p.parts or str(p) != name or name == '.' or '\\' in name:
            raise ValueError('Unsafe baseline filename')
        if not isinstance(item, dict) or not isinstance(item.get('sha256'), str) or len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256']):
            raise ValueError('Invalid baseline checksum')
        if type(item.get('size')) is not int or item['size'] < 0 or type(item.get('mode')) is not int or not 0 <= item['mode'] <= 0o7777:
            raise ValueError('Invalid baseline metadata')
    if not isinstance(baseline.get('skipped'), list) or any(not isinstance(x, str) for x in baseline['skipped']):
        raise ValueError('Invalid skipped-entry list')
    return baseline


def compare(baseline, current):
    validate(baseline)
    old, new = baseline['files'], current['files']
    changed = []
    unchanged = 0
    for name in sorted(old.keys() & new.keys()):
        reasons = []
        if old[name]['sha256'] != new[name]['sha256']:
            reasons.append('content')
        if old[name]['mode'] != new[name]['mode']:
            reasons.append('permissions')
        if reasons:
            changed.append({'path': name, 'reasons': reasons})
        else:
            unchanged += 1
    result = {'checked_at': utc_now(), 'added': sorted(new.keys()-old.keys()),
              'missing': sorted(old.keys()-new.keys()), 'changed': changed,
              'unchanged_count': unchanged, 'skipped': current['skipped'],
              'baseline_skipped': baseline['skipped']}
    result['has_changes'] = bool(result['added'] or result['missing'] or result['changed'])
    result['incomplete'] = bool(result['skipped'] or result['baseline_skipped'])
    return result


def outside_tree(path, root):
    destination, source = Path(path).resolve(), Path(root).resolve()
    if destination == source or source in destination.parents:
        raise ValueError('Baseline and report files must be outside the monitored tree')


def write_json(path, payload):
    # Atomic exclusive creation: never overwrite a baseline or report.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(payload, stream, indent=2)
            stream.write('\n')
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('baseline', 'check'):
        item = sub.add_parser(action)
        item.add_argument('directory')
        item.add_argument('baseline_file')
        if action == 'check':
            item.add_argument('--report')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        outside_tree(args.baseline_file, args.directory)
        if args.action == 'baseline':
            baseline = scan(args.directory)
            write_json(args.baseline_file, baseline)
            print(f"Baseline saved: {len(baseline['files'])} files, {len(baseline['skipped'])} skipped")
            return 2 if baseline['skipped'] else 0
        if args.report:
            outside_tree(args.report, args.directory)
        with open(args.baseline_file) as stream:
            baseline = validate(json.load(stream))
        result = compare(baseline, scan(args.directory))
        if args.report:
            write_json(args.report, result)
        print(json.dumps(result, indent=2))
        return 1 if result['has_changes'] else (2 if result['incomplete'] else 0)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f'Integrity check failed: {error}', file=__import__('sys').stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
