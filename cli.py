import argparse
import sys
import shlex
from db import FileStore
from utils import normalize_tags
import os


def _unquote(token: str) -> str:
    if not token:
        return token
    if (token[0] == token[-1]) and token[0] in ('"', "'") and len(token) >= 2:
        return token[1:-1]
    return token


def main(argv=None):
    parser = argparse.ArgumentParser(prog='tags-fs')
    parser.add_argument('--data-dir', '-d', default='./tags_data')
    args, rest = parser.parse_known_args(argv)

    store = FileStore(args.data_dir)

    if not rest:
        # start interactive mode
        repl(store)
        return

    def _unquote(token: str) -> str:
        if not token:
            return token
        if (token[0] == token[-1]) and token[0] in ('"', "'") and len(token) >= 2:
            return token[1:-1]
        return token

    # support single-command non-interactive mode
    if rest:
        cmd = rest[0]
        if cmd == 'add' and len(rest) >= 3:
            files_raw = _unquote(rest[1])
            tags_raw = _unquote(rest[2])
            files = [p.strip() for p in files_raw.split(',') if p.strip()]
            # normalize paths and unquote each path
            files = [os.path.normpath(_unquote(f)) for f in files]
            tags = normalize_tags(tags_raw)
        added = []
        for f in files:
            if not os.path.isfile(f):
                print(f"File not found: {f}")
                continue
            with open(f, 'rb') as fh:
                store.add_file(os.path.basename(f), fh.read())
            store.add_tags(os.path.basename(f), tags)
            added.append(os.path.basename(f))
        print('Added:', added)
        return
    print('Invalid or unsupported non-interactive command')


def repl(store: FileStore):
    print('Tags-based FS (centralized)')
    print('Commands:')
    print('  add <file1,file2> <tag1,tag2>')
    print('  delete <tag1,tag2>')
    print('  list <tag1,tag2>')
    print('  add-tags <tag-query> <tag1,tag2>')
    print('  delete-tags <tag-query> <tag1,tag2>')
    print('  show')
    print('  exit')
    while True:
        try:
            line = input('> ').strip()
        except EOFError:
            break
        if not line:
            continue
        try:
            # On Windows paths backslashes can be interpreted as escapes; use posix=False
            parts = shlex.split(line, posix=False)
        except ValueError:
            print('Invalid quoting in input')
            continue
        if not parts:
            continue
        cmd = parts[0]
        if cmd == 'exit':
            break
        if cmd == 'show':
            for name, tags in store.list_files():
                print(f"{name} : {tags}")
            continue
        if cmd == 'add' and len(parts) >= 3:
            files_raw = _unquote(parts[1])
            # tags may contain commas and/or spaces, it should be a single token after shlex
            tags_raw = _unquote(parts[2])
            files = [p.strip() for p in files_raw.split(',') if p.strip()]
            # normalize paths and unquote each path
            files = [os.path.normpath(_unquote(f)) for f in files]
            tags = normalize_tags(tags_raw)
            for f in files:
                if not os.path.isfile(f):
                    print(f"File not found: {f}")
                    continue
                store.add_file(os.path.basename(f), open(f,'rb').read())
                store.add_tags(os.path.basename(f), tags)
            print('OK')
            continue
        if cmd == 'delete' and len(parts) >= 2:
            tags = normalize_tags(parts[1])
            # delete files matching all tags
            matched = store.files_matching(tags)
            for m in matched:
                store.delete_file(m)
            print('Deleted:', matched)
            continue
        if cmd == 'list' and len(parts) >= 2:
            tags = normalize_tags(parts[1])
            matched = store.files_matching(tags)
            for m in matched:
                print(m, ':', store.meta.get(m, []))
            continue
        if cmd == 'add-tags' and len(parts) >= 3:
            q = normalize_tags(parts[1])
            add = normalize_tags(parts[2])
            matched = store.files_matching(q)
            for m in matched:
                store.add_tags(m, add)
            print('Updated:', matched)
            continue
        if cmd == 'delete-tags' and len(parts) >= 3:
            q = normalize_tags(parts[1])
            rem = normalize_tags(parts[2])
            matched = store.files_matching(q)
            for m in matched:
                store.remove_tags(m, rem)
            print('Updated:', matched)
            continue
        print('Unknown command')


if __name__ == '__main__':
    main()
