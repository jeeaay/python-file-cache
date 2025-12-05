# -*- coding: utf-8 -*-
import os
import sys
import time

def ensure_project_root_in_sys_path():
    """
    确保项目根目录加入 sys.path 以支持从上级导入包。
    仅在直接运行 demo/test_cache.py 时需要。
    """
    try:
        project_root = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
    except Exception as err:
        print(f"[路径注入失败] {err}")

# 优先尝试常规包导入；失败时补充路径后重试
try:
    from filecaching import FileCache
except ImportError:
    ensure_project_root_in_sys_path()
    try:
        from filecaching import FileCache
    except Exception as err:
        print(f"[导入失败] 无法导入 filecaching 包: {err}")
        raise

def build_cache_client(cache_dir='cache'):
    """
    构造文件缓存客户端。
    """
    try:
        return FileCache(cache_dir)
    except Exception as err:
        print(f"[实例化失败] {err}")
        raise

def cache_set(cache_client, cache_key, cache_value, expiration=0):
    """
    设置缓存并输出结果。
    """
    try:
        cache_client.cache(cache_key, cache_value, expiration)
        print(f"Set cache: {cache_key} = {cache_value} (exp={expiration}s)")
    except Exception as err:
        print(f"[设置失败] key={cache_key} err={err}")

def cache_get(cache_client, cache_key):
    """
    获取缓存并输出结果。
    """
    try:
        value = cache_client.cache(cache_key)
        print(f"Get cache: {cache_key} = {value}")
        return value
    except Exception as err:
        print(f"[读取失败] key={cache_key} err={err}")
        return None

def cache_delete(cache_client, cache_key):
    """
    删除缓存并输出结果。
    """
    try:
        cache_client.rm(cache_key)
        print(f"Delete cache: {cache_key} done")
    except Exception as err:
        print(f"[删除失败] key={cache_key} err={err}")

def wait_seconds(seconds):
    """
    等待给定秒数。
    """
    try:
        time.sleep(seconds)
    except Exception as err:
        print(f"[等待失败] seconds={seconds} err={err}")

def main():
    """
    运行基本用例验证 FileCache 的导入与功能。
    """
    cache_client = build_cache_client()

    print("Test 1: Set cache")
    cache_set(cache_client, "test_key", "test_value")

    print("\nTest 2: Get cache")
    cache_get(cache_client, "test_key")

    print("\nTest 3: Set cache with expiration")
    cache_set(cache_client, "temp_key", "temp_value", 3)

    print("\nTest 4: Get temp cache immediately")
    cache_get(cache_client, "temp_key")

    print("\nTest 5: Wait and get expired cache")
    wait_seconds(4)
    cache_get(cache_client, "temp_key")

    print("\nTest 6: Delete cache")
    cache_delete(cache_client, "test_key")
    cache_get(cache_client, "test_key")

    print("\nAll tests completed!")

if __name__ == "__main__":
    main()
