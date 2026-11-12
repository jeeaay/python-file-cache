# -*- coding=utf-8 -*-
'''
/* 文件缓存
 * @Author: jeay
 * @Date: 2021-08-16 09:23:39
 * @Last Modified by: jeay
 * @Last Modified time: 2021-08-16 11:27:07
 */
'''
import os, pickle, time
import hashlib
class FileCache:
    def __init__(self, path='cache') -> None:
        '''
        初始化
        @param path: 缓存储存路径，默认cache
        '''
        # 对称加密的密钥
        self.path = path
        if not os.path.isdir(self.path):
            os.mkdir(self.path)
    def cache(self, key, value=None, exp = 0):
        '''
        缓存
        @param key: 缓存的键，字符串类型，重复设置会覆盖已有缓存
        @param value: 缓存的值，类型不限，为空时读取缓存
        '''
        if value == None:
            return self.get(key)
        else:
            self.set(key, value, exp)
    def set(self, key, value, exp = 0):
        '''
        设置缓存
        @param key: 缓存的键，字符串类型，重复设置会覆盖已有缓存
        @param value: 缓存的值，类型不限
        @param exp: 有效期秒数，0 表示永不过期
        注意：exp 只保证过期后读不到值（get 时顺手删除），文件真正从磁盘消失
        取决于有没有运行清理脚本，见 purge() / purge_command()。
        '''
        cache_path = self._GetCachePath(key)
        data = {
            'stime': int(time.time()),
            'exp': exp,
            'data': value
        }
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
            # f.write(pickle.dumps(value))
    def get(self, key):
        '''
        设置缓存
        @param key: 缓存的键，字符串类型
        '''
        cache_path = self._GetCachePath(key, create=False)
        if not os.path.isfile(cache_path):
            return None
        try:
            with open(cache_path, 'rb') as f:
                value = pickle.load(f)
        except:
            return None
        # print(value)
        if value['exp'] == 0:
            return value['data']
        if value['exp'] is not None and (value['stime'] + value['exp'] < int(time.time())):
            self.rm(key)
            # print('过期')
            return None
        else:
            return value['data']

    def rm(self, key):
        '''
        删除缓存
        @param key: 缓存的键，字符串类型
        '''
        dir_path, filename = self._GetCachePath(key, False, create=False)
        try:
            os.remove(os.path.join(dir_path, filename))
        except OSError:
            pass
        # 非空目录会自己报错，省掉 listdir 判空这一趟以及它和并发写入之间的竞态
        try:
            os.rmdir(dir_path)
        except OSError:
            pass
    def purge(self, **kwargs):
        '''
        就地清理本目录下已过期的缓存文件，转交 filecaching.purger 执行。
        需要长期积累大量带过期时间缓存的场景，更推荐单独跑
        `python -m filecaching.purger --path ...`，见 purge_command()。
        @param kwargs: 透传给 filecaching.purger.purge()
        '''
        from . import purger
        return purger.purge(self.path, **kwargs)
    def purge_command(self, *args):
        '''
        返回调用清理脚本的命令行，可直接交给 subprocess 或写进 crontab。
        用 sys.executable 而不是裸 python，避免 cron 环境里用的不是同一个解释器。
        @param args: 附加给命令行的参数，如 '--rebuild'
        '''
        from . import purger
        return purger.purge_command(self.path, *args)
    def _GetCachePath(self, key, join = True, create = True):
        '''
        私有函数，用于统一处理缓存路径
        @param key: 缓存的键，字符串类型
        @param join: 为 True 时返回拼接好的文件路径，否则返回 (目录, 文件名)
        @param create: 分片目录不存在时是否创建，只读路径传 False
        '''
        key_sha1 = hashlib.sha1(key.encode()).hexdigest()[:18]
        dir_path = os.path.join(self.path, key_sha1[:2])
        if create and not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        if join:
            return os.path.join(dir_path, key_sha1[2:])
        else:
            return (dir_path, key_sha1[2:])
if __name__ == "__main__":
    fc = FileCache()
    # fc.set('a',{'a': '123'}, 3)
    print(fc.get('a'))
    # fc.rm('a')
