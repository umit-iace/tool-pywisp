#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("requirements.txt") as requirements_file:
    requirements = requirements_file.read()

test_requirements = [
]

setup(
    name="pywisp",
    version="1.0",
    description="Weird visualisation of test bench prototypes",
    long_description="Weird visualisation of test bench prototypes",
    classifiers=[
        "Natural Language :: English",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="pywisp visualisation arduino tcpip",
    url="https://github.com/umit-iace/tool-pywisp",
    author="IACE",
    author_email="jens.wurm@umit.at",
    license="GPLv3",
    packages=["pywisp"],
    package_dir={"pywisp": "pywisp"},
    install_requires=requirements,
    include_package_data=True,
    test_suite="pywisp.tests",
    tests_require=test_requirements,
    zip_safe=False
)
