import re
import argparse
import json
import random
import os

from premailer import transform

_root = os.path.join(os.path.dirname(__file__), 'samples')
samples = [
    os.path.join(_root, x) for x in os.listdir(_root)
    if os.path.isdir(os.path.join(_root, x))
]

def run(iterations):

    def raw(s):
        return re.sub(r'>\s+<', '><', s.replace('\n', ''))

    print(samples)
    for i in range(iterations):
        random.shuffle(samples)
        for sample in samples:
            with open(os.path.join(sample, 'input.html')) as f:
                input_html = f.read()
            with open(os.path.join(sample, 'output.html')) as f:
                output_html = f.read()
            try:
                with open(os.path.join(sample, 'options.json')) as f:
                    options = json.load(f)
            except FileNotFoundError:
                options = {}

            options['pretty_print'] = False
            got_html = transform(input_html, **options)
            got_html_raw = raw(got_html)
            output_html_raw = raw(output_html)
            if got_html_raw != output_html_raw:
                print("FAIL!", sample)
                print("GOT ".ljust(80, '-'))
                print(got_html)
                # print(repr(got_html_raw))
                print("EXPECTED ".ljust(80, '-'))
                print(output_html)
                # print(repr(output_html_raw))
                print()
                assert 0, sample


def main(args):
    parser = argparse.ArgumentParser(usage='python run.py [options]')

    parser.add_argument(
        "--iterations", default=10, type=int
    )

    options = parser.parse_args(args)

    run(options.iterations)
    return 0

if __name__ == '__main__':  # pragma: no cover
    import sys

    sys.exit(main(sys.argv[1:]))
