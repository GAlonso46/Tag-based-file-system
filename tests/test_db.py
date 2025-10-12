import tempfile
import os
from db import FileStore


def write_temp_file(dirpath, name, content=b'hello'):
    p = os.path.join(dirpath, name)
    with open(p, 'wb') as f:
        f.write(content)
    return p


def test_add_and_list_files(tmp_path):
    base = tmp_path / 'data'
    base.mkdir()

    # prepare a source temp file to add
    src = tmp_path / 'src'
    src.mkdir()
    f1 = write_temp_file(str(src), 'a.txt', b'AAA')

    store = FileStore(str(base))
    # add file content
    store.add_file('a.txt', b'AAA')
    # set tags
    store.set_tags('a.txt', ['tag1', 'tag2'])

    files = store.list_files()
    assert any(name == 'a.txt' for name, _ in files)
    assert store.meta['a.txt'] == ['tag1', 'tag2']


def test_files_matching_and_delete(tmp_path):
    base = tmp_path / 'data2'
    base.mkdir()
    store = FileStore(str(base))

    store.add_file('f1.txt', b'1')
    store.set_tags('f1.txt', ['a', 'b'])

    store.add_file('f2.txt', b'2')
    store.set_tags('f2.txt', ['a'])

    # query ['a'] should return both
    res = store.files_matching(['a'])
    assert set(res) == {'f1.txt', 'f2.txt'}

    # query ['a','b'] should return only f1
    res2 = store.files_matching(['a', 'b'])
    assert res2 == ['f1.txt']

    # delete f1
    store.delete_file('f1.txt')
    assert 'f1.txt' not in store.meta
    # file removed from storage
    assert not os.path.exists(os.path.join(store.files_dir, 'f1.txt'))


def test_add_and_remove_tags_edge_cases(tmp_path):
    base = tmp_path / 'data3'
    base.mkdir()
    store = FileStore(str(base))

    store.add_file('x.txt', b'x')
    store.set_tags('x.txt', ['t1'])

    # add tags including existing
    store.add_tags('x.txt', ['t1', 't2'])
    assert set(store.meta['x.txt']) == {'t1', 't2'}

    # remove only t1
    store.remove_tags('x.txt', ['t1'])
    assert store.meta.get('x.txt') == ['t2']

    # remove last tag -> file should be deleted
    store.remove_tags('x.txt', ['t2'])
    assert 'x.txt' not in store.meta
    assert not os.path.exists(os.path.join(store.files_dir, 'x.txt'))
