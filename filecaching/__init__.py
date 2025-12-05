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
        cache_path = self._GetCachePath(key)
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
        dir_path, filename = self._GetCachePath(key, False)
        # 先删除文件
        fpath = os.path.join(dir_path, filename)
        if os.path.isfile(fpath):
            os.remove(fpath)
        # 判断目录是否空了
        if len(os.listdir(dir_path)) == 0:
            os.rmdir(dir_path)
    def _GetCachePath(self, key, join = True):
        '''
        私有函数，用于统一处理缓存路径
        @param key: 缓存的键，字符串类型
        '''
        key_sha1 = hashlib.sha1(key.encode()).hexdigest()[:18]
        dir_path = os.path.join(self.path, key_sha1[:2])
        if not os.path.isdir(dir_path):
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
