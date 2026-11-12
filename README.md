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

## 清理过期缓存 Clean up expired cache

`exp` 只保证**过期之后读不到值**：`get` 命中一条过期缓存时会顺手把它删掉。
如果一条缓存写入后再也没被读到，它的文件会一直留在磁盘上。
要让文件真正消失，需要运行清理脚本 —— 定期手动跑、加进 crontab、或在常驻进程里循环调用，任选其一。

### 命令行 / 定时任务 Command line & cron

```bash
# 推荐用 python -m：cron 环境里的 python 往往不是应用 venv 里的那个
python -m filecaching.purger --path /var/app/cache
filecaching-purge --path /var/app/cache          # 等价的命令行入口

# crontab：每小时清一次，顺手删掉清空的分片目录
0 * * * * cd /var/app && /var/app/venv/bin/python -m filecaching.purger --path cache --vacuum -q
```

### 在代码里调用 In code

```python
from filecaching.purger import purge
purge('/var/app/cache')                       # 返回一份统计字典
FileCache('/var/app/cache').purge()           # 等价

# 交给 subprocess / supervisor 的命令行数组
FileCache('/var/app/cache').purge_command('--vacuum')
# [sys.executable, '-m', 'filecaching.purger', '--path', '/var/app/cache', '--vacuum']
```

### 参数 Options

| 参数 | 说明 |
| --- | --- |
| `--path` | 缓存目录，即 `FileCache(path)` 的 path（必填） |
| `--rebuild` | 忽略已有索引，完整扫一遍 payload |
| `--dry-run` | 只统计会删多少，不删除、不写索引 |
| `--shard XX` | 只处理某个分片（两位十六进制，可重复），便于拆成多份并行清理 |
| `--max-files N` | 最多删 N 个文件后退出，下次接着做 |
| `--deadline SEC` | 超过 SEC 秒后退出，下次接着做 |
| `--vacuum` | 分片被清空后连目录一起删除 |
| `--json` / `-q` | JSON 输出 / 静默 |

退出码：`0` 正常，`1` 出错，`2` 已有清理进程在跑。脚本自带目录锁，可以安全地重复调度。

### 性能 Performance

20000 条 512 字节缓存、其中一半已过期，Windows NTFS 本地盘实测：

| 场景 | 耗时 |
| --- | --- |
| 应用写入这 20000 条 | 7.5 s |
| 首轮清理（没有索引，逐条读 payload 建立索引） | 6.1 s |
| 之后每轮（无任何变动） | 0.66 s |
| 之后每轮（2000 条被改写） | 0.79 s |

也就是说首轮大致等于"把缓存重新写一遍"的代价，之后每轮只与**变动的文件数**成正比，且基本不受缓存值大小影响。
索引文件 `cache/xx/.index` 每万条约占 0.17 MB。Linux / ext4 上以上各项都要再快一个数量级。

### 关于 .index

- 每个分片目录下多出一个 `.index`，只记录「文件名、过期时间、文件修改时间」三件事。
- 它只是用来免去重复打开文件的加速结构，**过期与否最终以数据文件内容为准**；可以随时删掉，下一轮自动重建。
- 库的读写路径（`cache` / `set` / `get` / `rm`）完全不碰它，只有清理脚本读写它。
- 脚本只处理形如 `cache/两位十六进制/十六位十六进制` 的文件，目录里的其他内容不会被碰。

> 清理脚本会反序列化缓存目录下的数据文件来读取过期时间，这点和 `get()` 相同。
> 因此缓存目录不应放在其他用户可写的位置。

## LICENSE

Apache-2.0 License

## Source code

https://github.com/jeeaay/python-file-cache

