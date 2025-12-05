**发布到 PyPI 指南**
- 目标：从 `h:\git\py\python-file-cache` 构建并发布包到 TestPyPI/PyPI
- 包名：`filecaching`

**准备工作**
- 确认未发布的新版本：修改 `setup.py` 的 `version`
- 安装打包与上传工具（使用官方索引避免镜像缺包）：
  - `python -m pip install -i https://pypi.org/simple --upgrade setuptools wheel twine build`
- 可选优化：
  - 将 `setup.py` 的 `keywords` 从 tuple 改为 list，示例：`keywords=["filecaching", "filecache", "cache", "file caching tool", "caching"]`
  - 增加 `classifiers` 与 `python_requires` 提升检索与兼容性标识

**构建发布包**
- 首选（使用当前环境依赖，规避隔离环境镜像问题）：
  - `python -m build --no-isolation`
- 产物位置：`dist/`
  - `filecaching-<version>.tar.gz`
  - `filecaching-<version>-py3-none-any.whl`

**元数据检查**
- 检查分发包：`python -m twine check dist/*`
- 通过后再进行上传

**上传到 TestPyPI（沙箱验证）**
- 准备 TestPyPI 账户或 API Token
- 上传命令：`python -m twine upload --repository testpypi dist/*`
- 安装验证：`python -m pip install -i https://test.pypi.org/simple filecaching`

**上传到正式 PyPI**
- 上传命令：`python -m twine upload dist/*`
- 安装验证：`python -m pip install filecaching`

**凭证配置（推荐 API Token）**
- Windows 路径：`C:\Users\<用户名>\.pypirc`
- `.pypirc` 示例（请替换为你自己的 token）：
```
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
repository: https://upload.pypi.org/legacy/
username: __token__
password: pypi-<YOUR-PYPI-TOKEN>

[testpypi]
repository: https://test.pypi.org/legacy/
username: __token__
password: pypi-<YOUR-TESTPYPI-TOKEN>
```
- 若不使用 `.pypirc`，也可在命令行传入：
  - `python -m twine upload -u __token__ -p pypi-<YOUR-TOKEN> dist/*`

**常见问题与处理**
- 版本冲突：同一版本不可重复上传，需递增 `setup.py` 的 `version`
- 包名冲突：若 PyPI 已存在同名包且非你所有，必须更换 `name`
- 镜像问题：国内镜像可能缺部分依赖；安装工具时使用 `-i https://pypi.org/simple`
- 构建失败（隔离环境无法安装依赖）：使用 `python -m build --no-isolation`
- PATH 警告：优先使用 `python -m <模块>` 形式运行，避免脚本路径问题

**完整示例（一次性执行）**
- 更新版本号：编辑 `setup.py` 的 `version`
- 安装工具：
  - `python -m pip install -i https://pypi.org/simple --upgrade setuptools wheel twine build`
- 构建产物：
  - `python -m build --no-isolation`
- 检查产物：
  - `python -m twine check dist/*`
- 上传 TestPyPI：
  - `python -m twine upload --repository testpypi dist/*`
- 上传 PyPI：
  - `python -m twine upload dist/*`

**验证安装**
- TestPyPI：`python -m pip install -i https://test.pypi.org/simple filecaching`
- PyPI：`python -m pip install filecaching`
