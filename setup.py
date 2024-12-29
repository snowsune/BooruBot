#!/usr/bin/env python

from setuptools import setup, find_packages

readme = open("README.md").read()

setup(
    name="boorubot",
    description="todo",
    author="BixiBoo",
    author_email="tbd@gmail.com",
    url="https://github.com/snowsune/BooruBot",
    packages=find_packages(include=["boorubot"]),
    package_dir={"boorubot": "boorubot"},
    entry_points={
        "console_scripts": [
            "boorubot=boorubot.__main__:main",
        ],
    },
    python_requires=">=3.10.0",
    version="0.0.0",
    long_description=readme,
    include_package_data=True,
    install_requires=[
        "discord.py",
    ],
    license="MIT",
)
