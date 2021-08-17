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
# 实例化 Instantiate（可以使用FileCache(cache_path)指定缓存目录路径）(You can use FileCache (cache_path) specify the cache directory path)
fc = FileCache()
# 设置缓存 Set cache
fc.cache(key, value)
# 设置具有有效期的缓存 Set cache with an expiration date（单位是秒）
fc.cache(key, value, expiration_seconds)
# 读取缓存
fc.cache(key)
```

## LICENSE

Apache-2.0 License

## Source code

https://github.com/jeeaay/python-file-cache

