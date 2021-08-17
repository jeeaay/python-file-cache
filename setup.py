#!/usr/bin/env python
#-*- coding:utf-8 -*-

#############################################
# File Name: setup.py
# Author: Jeay
# Mail: admin@jeay.net
# Created Time:  2021-08-16 11:27:07
#############################################


from setuptools import setup, find_packages

setup(
    name = "filecaching",
    version = "0.1.0",
    keywords = ("filecaching", "filecache", "cache", "file caching tool", "caching"),
    description = "A simple and easy-to-use file caching tool",
    long_description = "A simple and easy-to-use file caching tool",
    license = "Apache-2.0 License",

    url = "https://github.com/jeeaay/python-file-cache.git",
    author = "Jeay",
    author_email = "admin@jeay.net",

    packages = find_packages(),
    include_package_data = True,
    platforms = "any",
    install_requires = []
)
