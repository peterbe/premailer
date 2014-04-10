import codecs
import os.path
import re

# Prevent spurious errors during `python setup.py test`, a la
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html:
try:
    import multiprocessing
except ImportError:
    pass

from setuptools import setup, find_packages


README = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = open(README).read().strip() + "\n\n"


def md2stx(s):
    import re
    s = re.sub(':\n(\s{8,10})', r'::\n\1', s)
    return s

long_description = md2stx(long_description)


def find_version(*file_paths):
    version_file = codecs.open(os.path.join(os.path.dirname(__file__),
                               *file_paths)).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='premailer',
    version=find_version('premailer', '__init__.py'),
    description="Turns CSS blocks into style attributes",
    long_description=long_description,
    keywords='html lxml email mail style',
    author='Peter Bengtsson',
    author_email='mail@peterbe.com',
    url='http://github.com/peterbe/premailer',
    license='Python',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Other Environment",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Python Software Foundation License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Communications",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Other/Nonlisted Topic",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages=find_packages(),
    include_package_data=True,
    test_suite='nose.collector',
    tests_require=['nose', 'mock'],
    zip_safe=False,
    install_requires=[
        'lxml',
        'cssselect',
        'cssutils',
    ],
)
