# -*- coding: utf-8 -*-
'''
/* 过期缓存清理器（离线运行）
 *
 * .index 只由本模块读写，FileCache 的写入路径不参与，因此它可以随时被删掉重建。
 * 记录里的 expire_at 来自数据文件的 payload，本模块只是把它缓存下来避免重复打开文件。
 *
 * 用法：
 *   python -m filecaching.purger --path /var/app/cache
 *   from filecaching.purger import purge; purge('/var/app/cache')
 * @Author: jeay
 */
'''
import argparse
import errno
import json
import os
import pickle
import re
import struct
import sys
import time

MAGIC = b'FCIX'
VERSION = 1
INDEX_NAME = '.index'
LOCK_NAME = '.purger.lock'

_HDR = struct.Struct('<4sB2sI')       # magic, version, shard, 记录条数
_REC = struct.Struct('<QII')          # hash_low, expire_at(0=永不过期), st_mtime
_HDR_SIZE = _HDR.size
_REC_SIZE = _REC.size
_U32_MAX = 0xFFFFFFFF

_SHARD_RE = re.compile(r'^[0-9a-f]{2}$')
_ENTRY_RE = re.compile(r'^[0-9a-f]{16}$')


def index_path(root, shard):
    '''某个分片的索引文件路径。'''
    return os.path.join(root, shard, INDEX_NAME)


def purge_command(root, *args):
    '''返回可直接交给 subprocess / cron 的命令行，用 sys.executable 避开 PATH 上的 python 不是同一个。'''
    return [sys.executable, '-m', 'filecaching.purger', '--path', os.path.abspath(root)] + list(args)


def _u32(value):
    value = int(value)
    if value < 0:
        return 0
    return value if value < _U32_MAX else _U32_MAX


def _read_expire_at(path):
    '''
    从数据文件的 payload 里取出绝对过期时间。
    返回 0 表示永不过期，None 表示读不懂（调用方必须保守跳过，不删也不记录）。
    '''
    try:
        with open(path, 'rb') as f:
            payload = pickle.load(f)
        exp = payload['exp']
        stime = payload['stime']
    except Exception:
        return None
    if not exp:
        # 与 FileCache.get() 对齐：0 / None / 假值都视为永不过期
        return 0
    try:
        return _u32(stime) + _u32(exp)
    except Exception:
        return None


def _load_index(path, shard):
    '''返回 {hash_low: (expire_at, mtime)}，缺失或不可信时返回 None 表示需要重建。'''
    try:
        with open(path, 'rb') as f:
            blob = f.read()
    except OSError:
        return None
    if len(blob) < _HDR_SIZE + _REC_SIZE:
        return None
    try:
        magic, version, name, count = _HDR.unpack_from(blob)
    except struct.error:
        return None
    if magic != MAGIC or version != VERSION or name != shard.encode('ascii'):
        return None
    if count != (len(blob) - _HDR_SIZE) // _REC_SIZE:
        return None
    try:
        return {h: (expire_at, mtime)
                for h, expire_at, mtime in _REC.iter_unpack(blob[_HDR_SIZE:])}
    except struct.error:
        return None


def _store_index(path, shard, records):
    body = bytearray(_HDR.pack(MAGIC, VERSION, shard.encode('ascii'), len(records)))
    pack = _REC.pack
    for hash_low in records:
        expire_at, mtime = records[hash_low]
        body += pack(hash_low, _u32(expire_at), _u32(mtime))
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(bytes(body))
    os.replace(tmp, path)


def _confirm_expired(path, expire_at, now, probe=None):
    '''
    删除前的最后一道复核。返回 False 就留给下一轮。
    probe 为 None 表示 expire_at 来自索引，此时必须以内容为准再读一次——mtime 秒级粒度
    会认不出同一秒内的覆盖写。随后的 stat 把「判定过期」与「unlink」之间的窗口压到一次
    stat。这个窗口无法归零（跨进程无法与 set() 协调），后果是一次 cache miss 而不是脏读。
    '''
    if probe is None:
        probe = time.time()
        fresh = _read_expire_at(path)
        if fresh is None or fresh == 0 or fresh >= now or expire_at != fresh:
            return False
    try:
        if os.stat(path).st_mtime > probe:
            return False
    except OSError:
        return True
    return True


def _list_shards(root, wanted):
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return []
    shards = [n for n in names if _SHARD_RE.match(n) and os.path.isdir(os.path.join(root, n))]
    if not wanted:
        return shards
    return [s for s in shards if s in wanted]


def _purge_shard(root, shard, opts, stats):
    '''处理一个分片，返回 False 表示因预算中断。'''
    dir_path = os.path.join(root, shard)
    now = int(time.time())
    try:
        listing = list(os.scandir(dir_path))
    except OSError:
        stats['errors'] += 1
        return True

    index = None if opts['rebuild'] else _load_index(index_path(root, shard), shard)
    records = dict(index) if index is not None else {}
    present = set()

    for entry in listing:
        name = entry.name
        if not _ENTRY_RE.match(name):
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        hash_low = int(name, 16)
        present.add(hash_low)
        stats['seen'] += 1
        mtime = int(st.st_mtime)

        cached = index.get(hash_low) if index is not None else None
        probe = None
        if cached is not None and cached[1] == mtime:
            expire_at = cached[0]           # 自上次以来没动过，免去一次打开
        else:
            stats['payload_reads'] += 1
            # 取在回读之前：这之后任何写入都会在 mtime 上留下痕迹
            probe = time.time()
            expire_at = _read_expire_at(entry.path)
            if expire_at is None:
                records.pop(hash_low, None)
                stats['skipped'] += 1
                continue
            records[hash_low] = (expire_at, mtime)

        if not expire_at or expire_at >= now:
            continue
        if stats['deleted'] >= opts['max_files'] or (
                opts['deadline'] and time.time() >= opts['deadline']):
            # present 只覆盖已走到的部分，此时不能拿它去剔除还没看过的旧记录
            _finish_index(root, shard, records, None, stats, opts)
            return False
        if not _confirm_expired(entry.path, expire_at, now, probe):
            stats['skipped'] += 1
            continue
        if opts['dry_run']:
            stats['deleted'] += 1
            stats['freed_bytes'] += st.st_size
            continue
        try:
            os.remove(entry.path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                stats['errors'] += 1
                continue
        records.pop(hash_low, None)
        present.discard(hash_low)
        stats['deleted'] += 1
        stats['freed_bytes'] += st.st_size

    _finish_index(root, shard, records, present, stats, opts)
    if opts['vacuum'] and not present:
        _vacuum(dir_path, root, shard, stats, opts)
    return True


def _finish_index(root, shard, records, present, stats, opts):
    '''
    写回索引。present 为整片 scandir 得到的集合，用它剔除已被外部 rm 掉的条目；
    为 None 表示本轮中途结束，还没走到的条目不能据此判定消失。
    '''
    if present is not None:
        records = {h: r for h, r in records.items() if h in present}
    if opts['dry_run']:
        return
    path = index_path(root, shard)
    try:
        if not records:
            if os.path.isfile(path):
                os.remove(path)
        else:
            _store_index(path, shard, records)
    except OSError:
        stats['errors'] += 1


def _vacuum(dir_path, root, shard, stats, opts):
    '''只有目录里除了索引不剩别的东西才收摊，否则连索引一起留着。'''
    if opts['dry_run']:
        return
    try:
        if [n for n in os.listdir(dir_path)
                if n not in (INDEX_NAME, INDEX_NAME + '.tmp')]:
            return
    except OSError:
        return
    for name in (INDEX_NAME, INDEX_NAME + '.tmp'):
        try:
            os.remove(os.path.join(dir_path, name))
        except OSError:
            pass
    try:
        os.rmdir(dir_path)
        stats['vacuumed'] += 1
    except OSError:
        pass


def _acquire_lock(root, stale_after):
    path = os.path.join(root, LOCK_NAME)
    for attempt in (0, 1):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except OSError as err:
            if err.errno not in (errno.EEXIST, errno.EACCES):
                raise
            try:
                if attempt or time.time() - os.stat(path).st_mtime < stale_after:
                    return None, None
                os.remove(path)
            except OSError:
                return None, None
            continue
        return fd, path
    return None, None


def _release_lock(fd, path):
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.remove(path)
    except OSError:
        pass


def purge(root, rebuild=False, dry_run=False, shards=None, max_files=None,
          deadline=None, vacuum=False, quiet=True, lock_stale=3600):
    '''
    清理 root 下已过期的缓存文件。给常驻进程直接调用，调度权在使用方。
    返回一份可序列化的统计字典；dry_run 时 deleted / freed_bytes 表示「将会删除」的量。
    '''
    root = os.path.abspath(os.path.expanduser(root))
    if not os.path.isdir(root):
        raise ValueError('缓存目录不存在: %s' % root)
    started = time.time()
    opts = {
        'rebuild': bool(rebuild),
        'dry_run': bool(dry_run),
        'vacuum': bool(vacuum),
        'max_files': int(max_files) if max_files is not None else 1 << 62,
        'deadline': (started + float(deadline)) if deadline else None,
    }
    stats = {'seen': 0, 'payload_reads': 0, 'deleted': 0, 'freed_bytes': 0,
             'skipped': 0, 'errors': 0, 'vacuumed': 0, 'shards': 0}

    fd, lock = _acquire_lock(root, lock_stale)
    if fd is None:
        stats.update(complete=False, locked=True, elapsed=round(time.time() - started, 3),
                     root=root)
        return stats

    try:
        targets = _list_shards(root, set(shards or ()))
        if shards:
            missing = set(shards) - set(targets)
            if missing:
                raise ValueError('分片不存在: %s' % ', '.join(sorted(missing)))
        complete = True
        for shard in targets:
            stats['shards'] += 1
            if not _purge_shard(root, shard, opts, stats):
                complete = False
                break
    finally:
        _release_lock(fd, lock)

    stats.update(root=root, complete=complete, dry_run=dry_run, locked=False,
                 elapsed=round(time.time() - started, 3))
    if not quiet:
        # 保持 ASCII：cron 常常跑在 LANG=C 下，中文摘要会退化成转义串
        sys.stderr.write(
            'filecaching-purge: shards=%d seen=%d reads=%d deleted=%d skipped=%d '
            'errors=%d freed=%.1fMB elapsed=%.2fs%s\n'
            % (stats['shards'], stats['seen'], stats['payload_reads'], stats['deleted'],
               stats['skipped'], stats['errors'], stats['freed_bytes'] / 1048576.0,
               stats['elapsed'], ' [dry-run]' if dry_run else ''))
    return stats


def build_parser():
    p = argparse.ArgumentParser(
        prog='filecaching-purge',
        description='清理 filecaching 的过期缓存文件（可安全重复运行）。')
    p.add_argument('--path', required=True, help='缓存根目录，即 FileCache(path) 的 path')
    p.add_argument('--rebuild', action='store_true',
                   help='忽略已有 .index，完整扫描一遍 payload')
    p.add_argument('--dry-run', action='store_true', help='只统计，不删除、不改索引')
    p.add_argument('--shard', action='append', metavar='XX',
                   help='只处理指定分片（16 进制两位，可重复），便于把清理拆成多份 cron')
    p.add_argument('--max-files', type=int, metavar='N', help='最多删除 N 个文件后停止')
    p.add_argument('--deadline', type=float, metavar='SEC', help='超过 SEC 秒后停止')
    p.add_argument('--vacuum', action='store_true', help='删空之后移除分片目录')
    p.add_argument('--json', action='store_true', help='把统计结果以 JSON 输出到 stdout')
    p.add_argument('-q', '--quiet', action='store_true', help='不输出统计')
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        stats = purge(args.path, rebuild=args.rebuild, dry_run=args.dry_run,
                      shards=args.shard, max_files=args.max_files,
                      deadline=args.deadline, vacuum=args.vacuum,
                      quiet=args.quiet or args.json)
    except (ValueError, OSError) as err:
        sys.stderr.write('filecaching-purge: %s\n' % err)
        return 1
    if args.json:
        sys.stdout.write(json.dumps(stats, sort_keys=True) + '\n')
    if stats.get('locked'):
        return 2
    return 1 if stats.get('errors') else 0


if __name__ == '__main__':
    sys.exit(main())
