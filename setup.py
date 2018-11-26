import codecs
import os.path
import re
import sys

from setuptools import setup, find_packages


README = os.path.join(os.path.dirname(__file__), "README.rst")
long_description = open(README).read().strip() + "\n\n"


def find_version(*file_paths):
    version_file_path = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = codecs.open(version_file_path, encoding="utf-8").read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


install_requires = ["lxml", "cssselect", "cssutils", "requests", "cachetools"]

if sys.version_info >= (2, 6) and sys.version_info <= (2, 7):
    # Python 2.6 is the oldest version we support and it
    # needs some extra stuff
    install_requires.extend(["argparse", "ordereddict"])

tests_require = ["nose", "mock"]

setup(
    name="premailer",
    version=find_version("premailer", "__init__.py"),
    description="Turns CSS blocks into style attributes",
    long_description=long_description,
    keywords="html lxml email mail style",
    author="Peter Bengtsson",
    author_email="mail@peterbe.com",
    url="http://github.com/peterbe/premailer",
    license="Python",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Other Environment",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Python Software Foundation License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Communications",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Other/Nonlisted Topic",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages=find_packages(),
    include_package_data=True,
    test_suite="nose.collector",
    tests_require=tests_require,
    extras_require={
        "dev": ["tox", "twine", "therapist", "black", "flake8"],
        "test": tests_require,
    },
    zip_safe=False,
    install_requires=install_requires,
)
