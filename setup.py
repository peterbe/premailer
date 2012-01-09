import os
from setuptools import setup, find_packages

version = '1.11'

README = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = open(README).read().strip() + "\n\n"


def md2stx(s):
    import re
    s = re.sub(':\n(\s{8,10})', r'::\n\1', s)
    return s

long_description = md2stx(long_description)


setup(name='premailer',
      version=version,
      description="Turns CSS blocks into style attributes",
      long_description=long_description,
      keywords='html lxml email mail style',
      author='Peter Bengtsson',
      author_email='peter@fry-it.com',
      url='http://github.com/peterbe/premailer',
      download_url='http://github.com/peterbe/premailer',
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
      tests_require=['Nose'],
      zip_safe=True,
      install_requires=[
        'lxml',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
