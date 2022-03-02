# Copyright (C) 2022 Nokia
# Licensed under the MIT License
# SPDX-License-Identifier: MIT

from setuptools import setup

install_requires = []
with open("requirements.txt") as f:
    for line in f:
        line, _, _ = line.partition("#")
        line = line.strip()
        if line:
            install_requires.append(line)

with open("README.md") as f:
    long_description = f.read()

with open("koredump.spec") as f:
    for line in f:
        if line.startswith("Version:"):
            version = line.partition(":")[2].strip()
            break

setup(
    name="koredump",
    version=version,
    author="Nokia",
    author_email="",
    description="Coredump REST API for Kubernetes",
    license="MIT",
    url="http://github.com/nokia/koredump",
    long_description=long_description,
    install_requires=install_requires,
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
