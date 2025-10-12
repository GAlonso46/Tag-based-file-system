import argparse
import os
import shlex
import sys
from tags.core.tag_service import TagService
from tags.utils.helpers import normalize_tags, unquote, split_input_preserve_quotes

_PROMPT = """Tags-based FS (centralized)
Commands:
  add <file1,file2> <tag1,tag2>
  delete <tag1,tag2>
  list <tag1,tag2>
  add-tags <tag-query> <tag1,tag2>
  delete-tags <tag-query> <tag1,tag2>
  show
  exit
"""

def _do_non_interactive(rest, service: TagService):
    # support single-command non-interactive mode similar to original
    if not rest:
        return False
    cmd = rest[0]
    if cmd == 'add' and len(rest) >= 3:
        files_raw = unquote(rest[1])
        tags_raw = unquote(rest[2])
        files = [os.path.normpath(unquote(p.strip())) for p in files_raw.split(',') if p.strip()]
        added = service.add_files(files, tags_raw)
        print('Added:', added)
        return True
    print('Invalid or unsupported non-interactive command')
    return True

def repl(service: TagService):
    print(_PROMPT)
    while True:
        try:
            line = input('> ').strip()
        except EOFError:
            break
        if not line:
            continue
        try:
            parts = split_input_preserve_quotes(line)
        except ValueError:
            print('Invalid quoting in input')
            continue
        if not parts:
            continue
        cmd = parts[0]
        if cmd == 'exit':
            break
        if cmd == 'show':
            for name, tags in service.show_all():
                print(f"{name} : {tags}")
            continue
        if cmd == 'add' and len(parts) >= 3:
            files_raw = unquote(parts[1])
            tags_raw = unquote(parts[2])
            files = [os.path.normpath(unquote(p.strip())) for p in files_raw.split(',') if p.strip()]
            # prueba
            for f in files:
                print(f)
            added = service.add_files(files, tags_raw)
            print('Added:', added)
            continue
        if cmd == 'delete' and len(parts) >= 2:
            tags = normalize_tags(parts[1])
            deleted = service.delete_by_tags(tags)
            print('Deleted:', deleted)
            continue
        if cmd == 'list' and len(parts) >= 2:
            tags = normalize_tags(parts[1])
            matched = service.list_by_tags(tags)
            for m, meta_tags in matched:
                print(m, ':', meta_tags)
            continue
        if cmd == 'add-tags' and len(parts) >= 3:
            q = parts[1]
            add = parts[2]
            updated = service.add_tags_to_query(q, add)
            print('Updated:', updated)
            continue
        if cmd == 'delete-tags' and len(parts) >= 3:
            q = parts[1]
            rem = parts[2]
            updated = service.remove_tags_from_query(q, rem)
            print('Updated:', updated)
            continue
        print('Unknown command')

def main(argv=None):
    parser = argparse.ArgumentParser(prog='tags-fs')
    parser.add_argument('--data-dir', '-d', default='./tags_data')
    args, rest = parser.parse_known_args(argv)
    service = TagService(args.data_dir)

    if not rest:
        # interactive
        repl(service)
        return

    # single command mode
    # combine rest into tokens like shell would do so quoted paths stay together
    # rest may already be tokenized by parse_known_args, so just pass it
    if rest:
        # attempt to handle a single non-interactive command
        if _do_non_interactive(rest, service):
            return
    print('Invalid or unsupported non-interactive command')
