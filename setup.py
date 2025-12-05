#!/usr/bin/env python
#-*- coding:utf-8 -*-

#############################################
# File Name: setup.py
# Author: Jeay
# Mail: admin@jeay.net
# Created Time:  2021-08-16 11:27:07
#############################################


from setuptools import setup, find_packages
filepath = 'README.md'
setup(
    name = "filecaching",
    version = "0.0.4",
    keywords = ("filecaching", "filecache", "cache", "file caching tool", "caching"),
    description = "A simple and easy-to-use file caching tool",
    long_description = open(filepath, encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    license = "Apache-2.0 License",

    url = "https://github.com/jeeaay/python-file-cache.git",
    author = "Jeay",
    author_email = "wrjie@msn.cn",

    packages = find_packages(),
    include_package_data = True,
    platforms = "any",
    install_requires = []
)
