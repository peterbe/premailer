#!/usr/bin/env bash
set -eo pipefail

# From https://pypi.org/project/twine/

python setup.py sdist bdist_wheel
twine upload dist/*
