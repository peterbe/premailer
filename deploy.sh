#!/usr/bin/env bash
set -eo pipefail

# From https://pypi.org/project/twine/

rm -fr dist/
python setup.py sdist bdist_wheel
twine upload dist/*
