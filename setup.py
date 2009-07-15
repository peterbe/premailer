from setuptools import setup, find_packages
import sys, os

import premailer
version = premailer.__version__ # hate repeating myself

README = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = open(README).read().strip() + "\n\n"


setup(name='premailer',
      version=version,
      description="Turns CSS blocks into style attributes",
      long_description=long_description,
      keywords='html lxml email mail style',
      author='Peter Bengtsson',
      author_email='peter@fry-it.com',
      url='http://www.peterbe.com/plog/premailer.py',
      download_url='http://pypi.python.org/pypi/premailer/',
      license='Python',
      classifiers = [
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
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      test_suite='nose.collector',
      test_requires=['Nose'],
      zip_safe=True,
      install_requires=[
        'lxml',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
