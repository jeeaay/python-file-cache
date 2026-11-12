# -*- coding: utf-8 -*-
'''filecaching.purger 的行为测试。运行：python -m unittest discover -s tests'''
import io
import os
import pickle
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filecaching import FileCache
from filecaching import purger


class PurgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='fc-test-')
        self.root = os.path.join(self.tmp, 'cache')
        self.fc = FileCache(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- 辅助 ----
    def entry(self, key, exp=0, age=0, value='v'):
        '''经真实 FileCache 写入以复用其路径规则，再把创建时间挪到 age 秒前。'''
        self.fc.set(key, value, exp)
        path = self.fc._GetCachePath(key)
        stime = int(time.time()) - age
        with open(path, 'wb') as f:
            pickle.dump({'stime': stime, 'exp': exp, 'data': value}, f)
        os.utime(path, (stime, stime))
        return path

    def raw(self, shard, name, stime, exp, mtime=None, value='v'):
        '''在指定分片里直接造一条缓存，便于控制迭代顺序。'''
        d = os.path.join(self.root, shard)
        if not os.path.isdir(d):
            os.makedirs(d)
        path = os.path.join(d, name)
        with open(path, 'wb') as f:
            pickle.dump({'stime': stime, 'exp': exp, 'data': value}, f)
        touched = stime if mtime is None else mtime
        os.utime(path, (touched, touched))
        return path

    def shard_of(self, path):
        return os.path.basename(os.path.dirname(path))

    def keys_in_shard(self, shard):
        return sorted(n for n in os.listdir(os.path.join(self.root, shard))
                      if purger._ENTRY_RE.match(n))

    # ---- 基本正确性 ----
    def test_deletes_only_expired(self):
        gone = self.entry('expired', exp=60, age=120)
        live = self.entry('live', exp=3600)
        forever = self.entry('forever', exp=0, age=999999)

        stats = purger.purge(self.root)

        self.assertEqual(stats['deleted'], 1)
        self.assertEqual(stats['errors'], 0)
        self.assertFalse(os.path.exists(gone))
        self.assertTrue(os.path.isfile(live))
        self.assertTrue(os.path.isfile(forever))
        self.assertEqual(self.fc.get('live'), 'v')
        self.assertEqual(self.fc.get('forever'), 'v')

    def test_exp_none_and_garbage_never_deleted(self):
        now = int(time.time())
        none_exp = self.raw('0a', '0000000000000001', now - 99999, None)
        broken = self.raw('0a', '0000000000000002', now, 0)
        with open(broken, 'wb') as f:
            f.write(b'\x80\x04\x95 not a real pickle')

        stats = purger.purge(self.root, shards=['0a'])

        self.assertEqual(stats['deleted'], 0)
        self.assertEqual(stats['skipped'], 1)
        self.assertTrue(os.path.isfile(none_exp))
        self.assertTrue(os.path.isfile(broken))

    def test_freed_bytes_reported(self):
        self.entry('expired', exp=60, age=120, value='x' * 5000)
        stats = purger.purge(self.root)
        self.assertGreater(stats['freed_bytes'], 4000)

    # ---- 索引 ----
    def test_index_created_and_reused(self):
        live = self.entry('live', exp=3600)
        self.entry('expired', exp=60, age=120)
        first = purger.purge(self.root)
        self.assertEqual(first['payload_reads'], 2)
        self.assertTrue(os.path.isfile(purger.index_path(self.root, self.shard_of(live))))

        second = purger.purge(self.root)
        self.assertEqual(second['payload_reads'], 0, 'mtime 未变不应再打开数据文件')
        self.assertEqual(second['seen'], first['seen'] - 1)

    def test_overwrite_with_same_name_is_detected(self):
        '''覆盖写不改文件名，只能靠 mtime 发现，否则会一直沿用第一次的 TTL。'''
        key = 'rewrite-me'
        path = self.entry(key, exp=3600)
        self.assertTrue(purger.purge(self.root)['deleted'] == 0)

        stime = int(time.time()) - 120
        with open(path, 'wb') as f:
            pickle.dump({'stime': stime, 'exp': 60, 'data': 'v'}, f)
        os.utime(path, (stime, stime))

        stats = purger.purge(self.root)
        self.assertEqual(stats['deleted'], 1)
        self.assertFalse(os.path.exists(path))

    def test_externally_removed_key_drops_record(self):
        path = self.entry('gone', exp=3600)
        purger.purge(self.root)
        self.fc.rm('gone')
        self.assertFalse(os.path.exists(path))

        stats = purger.purge(self.root)
        self.assertEqual(stats['payload_reads'], 0)

    def test_missing_index_rebuilds_from_payload(self):
        live = self.entry('live', exp=3600)
        purger.purge(self.root)
        shard = self.shard_of(live)
        os.remove(purger.index_path(self.root, shard))

        gone = self.raw(shard, '00000000000000aa', int(time.time()) - 120, 60)
        stats = purger.purge(self.root, shards=[shard])

        self.assertEqual(stats['payload_reads'], 2, '索引丢失只能全部回读')
        self.assertFalse(os.path.exists(gone))
        self.assertTrue(os.path.isfile(live))

    def test_garbage_and_truncated_index_are_ignored(self):
        live = self.entry('live', exp=3600)
        purger.purge(self.root)
        shard = self.shard_of(live)
        path = purger.index_path(self.root, shard)
        with open(path, 'rb') as f:
            blob = f.read()
        now = int(time.time())

        expired = self.raw(shard, '00000000000000ab', now - 120, 60)
        with open(path, 'wb') as f:                     # 条数与文件长度对不上
            f.write(blob[:-3])
        self.assertEqual(purger.purge(self.root, shards=[shard])['payload_reads'], 2)
        self.assertFalse(os.path.exists(expired))

        expired = self.raw(shard, '00000000000000ac', now - 120, 60)
        with open(path, 'wb') as f:                     # 完全不是索引
            f.write(b'XXXXXXXXXXXX')
        stats = purger.purge(self.root, shards=[shard])

        self.assertEqual(stats['deleted'], 1)
        self.assertFalse(os.path.exists(expired))
        self.assertTrue(os.path.isfile(live))

    def test_index_of_wrong_shard_is_rejected(self):
        now = int(time.time())
        self.raw('0b', '000000000000000b', now, 3600)   # 留一条活的，索引才会存在
        gone = self.raw('0b', '000000000000000a', now - 120, 60)
        purger.purge(self.root, shards=['0b'])
        self.assertFalse(os.path.exists(gone))

        source = purger.index_path(self.root, '0b')
        self.assertIsNotNone(purger._load_index(source, '0b'))
        self.assertIsNone(purger._load_index(source, '0c'), '同一份索引不能当另一个分片用')

        os.makedirs(os.path.join(self.root, '0c'))
        shutil.copy(source, purger.index_path(self.root, '0c'))
        target = self.raw('0c', '000000000000000a', now - 120, 60)
        stats = purger.purge(self.root, shards=['0c'])

        self.assertEqual(stats['payload_reads'], 1, '被拒绝的索引必须退回全量回读')
        self.assertEqual(stats['deleted'], 1)
        self.assertFalse(os.path.exists(target))
        self.assertEqual(purger.purge(self.root, shards=['0c'])['payload_reads'], 0)

    # ---- 并发与复核 ----
    def test_recently_rewritten_file_is_skipped(self):
        '''mtime 晚于复核时刻说明有写入插在我们判定之后，必须留给下一轮。'''
        now = int(time.time())
        path = self.raw('0d', '000000000000000d', now - 120, 60, mtime=now + 30)

        stats = purger.purge(self.root, shards=['0d'])

        self.assertEqual(stats['deleted'], 0)
        self.assertEqual(stats['skipped'], 1)
        self.assertTrue(os.path.isfile(path))

    def test_stale_index_cannot_outvote_the_payload(self):
        '''mtime 对得上时索引会免掉回读，所以判定过期后还要再以内容为准复核一次。'''
        live = self.entry('live', exp=3600)
        purger.purge(self.root)
        shard = self.shard_of(live)
        path = purger.index_path(self.root, shard)
        with open(path, 'r+b') as f:
            f.seek(purger._HDR_SIZE)
            f.write(purger._REC.pack(int(os.path.basename(live), 16),
                                     int(time.time()) - 10,
                                     int(os.stat(live).st_mtime)))

        stats = purger.purge(self.root, shards=[shard])

        self.assertEqual(stats['payload_reads'], 0)
        self.assertEqual(stats['deleted'], 0, '删除前必须以 payload 内容为准')
        self.assertEqual(stats['skipped'], 1)
        self.assertTrue(os.path.isfile(live))

    # ---- 预算与副作用 ----
    def test_max_files_budget_and_convergence(self):
        now = int(time.time())
        for i in range(5):
            self.raw('0e', '%016x' % i, now - 120, 60)

        first = purger.purge(self.root, shards=['0e'], max_files=2)
        self.assertEqual(first['deleted'], 2)
        self.assertFalse(first['complete'])
        self.assertEqual(len(self.keys_in_shard('0e')), 3)

        second = purger.purge(self.root, shards=['0e'])
        self.assertEqual(second['deleted'], 3)
        self.assertTrue(second['complete'])
        self.assertEqual(self.keys_in_shard('0e'), [])

    def test_dry_run_changes_nothing(self):
        gone = self.entry('expired', exp=60, age=120)
        before = sorted(os.listdir(self.root))

        stats = purger.purge(self.root, dry_run=True)

        self.assertEqual(stats['deleted'], 1, 'dry-run 也要报出会删多少')
        self.assertTrue(stats['dry_run'])
        self.assertTrue(os.path.exists(gone))
        self.assertEqual(sorted(os.listdir(self.root)), before)
        self.assertEqual([s for s in os.listdir(self.root)
                          if os.path.isfile(purger.index_path(self.root, s))], [])

    def test_vacuum_removes_emptied_shard(self):
        now = int(time.time())
        self.raw('0f', '000000000000000f', now - 120, 60)
        purger.purge(self.root, shards=['0f'], vacuum=True)
        self.assertFalse(os.path.isdir(os.path.join(self.root, '0f')))

    def test_vacuum_keeps_shard_that_still_has_entries(self):
        now = int(time.time())
        live = self.raw('0f', '0000000000000001', now, 3600)
        gone = self.raw('0f', '0000000000000002', now - 120, 60)

        stats = purger.purge(self.root, shards=['0f'], vacuum=True)

        self.assertEqual(stats['deleted'], 1)
        self.assertEqual(stats['vacuumed'], 0)
        self.assertTrue(os.path.isfile(live))
        self.assertFalse(os.path.exists(gone))
        self.assertTrue(os.path.isfile(purger.index_path(self.root, '0f')))

    def test_shard_must_exist(self):
        with self.assertRaises(ValueError):
            purger.purge(self.root, shards=['aa'])

    # ---- 锁 ----
    def test_lock_blocks_concurrent_run(self):
        self.entry('expired', exp=60, age=120)
        lock = os.path.join(self.root, purger.LOCK_NAME)
        open(lock, 'wb').close()

        stats = purger.purge(self.root)
        self.assertTrue(stats['locked'])
        self.assertEqual(stats['deleted'], 0)

        rc = purger.main(['--path', self.root, '-q'])
        self.assertEqual(rc, 2)

        os.utime(lock, (0, 0))           # 陈旧锁应被回收
        stats = purger.purge(self.root)
        self.assertFalse(stats['locked'])
        self.assertEqual(stats['deleted'], 1)

    # ---- 库侧改动 ----
    def test_get_does_not_create_shard_dir(self):
        entries = FileCache(os.path.join(self.tmp, 'readonly'))
        entries.get('nothing-here')
        self.assertEqual(os.listdir(os.path.join(self.tmp, 'readonly')), [])

    def test_rm_of_missing_key_is_quiet(self):
        self.fc.rm('never-written')
        self.assertIsNone(self.fc.get('never-written'))

    def test_purge_command_uses_current_interpreter(self):
        cmd = self.fc.purge_command('--rebuild')
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1:3], ['-m', 'filecaching.purger'])
        self.assertEqual(cmd[3], '--path')
        self.assertEqual(os.path.normcase(cmd[4]), os.path.normcase(self.root))
        self.assertEqual(cmd[5], '--rebuild')

    def test_cli_json_output(self):
        self.entry('expired', exp=60, age=120)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = purger.main(['--path', self.root, '--json'])
        self.assertEqual(rc, 0)
        import json
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload['deleted'], 1)
        self.assertTrue(payload['complete'])

    def test_missing_root_raises(self):
        with self.assertRaises(ValueError):
            purger.purge(os.path.join(self.tmp, 'nope'))


if __name__ == '__main__':
    unittest.main()
