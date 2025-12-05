# python-file-cache

一个简单易用的Python的文件缓存工具

A simple and easy-to-use file caching tool

## 安装 Install

```
pip install filecaching
```
## 如何使用 How to use

```python
# 引入 Import
from filecaching import FileCache
# 实例化 Instantiate
fc = FileCache()
#（可以使用FileCache(cache_path)指定缓存目录路径）
# (You can use FileCache(cache_path) specify the cache directory path)
fc = FileCache(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache'))
# 设置缓存 Set cache
fc.cache(key, value)
# 设置具有有效期的缓存 Set cache with an expiration date（单位是秒）
fc.cache(key, value, expiration_seconds)
# 读取缓存 Get cache
fc.cache(key)
# 删除 Remove cache
fc.rm(key)
```

## 一些实例 Some examples

```python
from filecaching import FileCache
fc = FileCache()
# 设置缓存 Set cache
fc.cache('a', {'v': 'abc'})
# 设置具有有效期的缓存 Set cache with an expiration date (30s)
fc.cache('b', [1,2,3], 30)
# 读取缓存 Get cache
print(fc.cache('a'))
print(fc.cache('b'))
# 删除 Remove cache
fc.rm('a')
```

## LICENSE

Apache-2.0 License

## Source code

https://github.com/jeeaay/python-file-cache

