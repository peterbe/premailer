from .premailer import Premailer, PremailerError


def main():
    """Command-line tool to transform html style to inline css

    Usage::

        $ echo '<style>h1 { color:red; }</style><h1>Title</h1>' | python -m premailer
        <h1 style="color:red"></h1>
        $ cat newsletter.html | python -m premailer
    """
    import sys
    from optparse import OptionParser

    parser = OptionParser(usage='python -m premailer [options]')

    parser.add_option("-f", "--file", dest="infile",
                      help="Specifies the input file.  The default is stdin.",
                      metavar="FILE")

    parser.add_option("-o", "--output", dest="outfile",
                      help="Specifies the output file.  The default is stdout.",
                      metavar="FILE")

    parser.add_option("--base-url", default=None, type=str, dest="base_url")

    parser.add_option("--remove-internal-links", default=True,
                      action="store_false", dest="preserve_internal_links")

    parser.add_option("--exclude-pseudoclasses", default=False,
                      action="store_true", dest="exclude_pseudoclasses")

    parser.add_option("--remove-style-tags", default=True,
                      action="store_false", dest="keep_style_tags")

    parser.add_option("--remove-star-selectors", default=True,
                      action="store_false", dest="include_star_selectors")

    parser.add_option("--remove-classes", default=False,
                      action="store_true", dest="remove_classes")

    parser.add_option("--strip-important", default=False,
                      action="store_true", dest="strip_important")

    (options, args) = parser.parse_args()

    if len(args) != 0:
        raise SystemExit(sys.argv[0] + " -f infile [-o outfile]]")

    if options.infile:
        infile = open(options.filename, "rb").read()
    else:
        infile = sys.stdin.read()

    if options.outfile:
        outfile = open(options.output, "wb")
    else:
        outfile = sys.stdout

    try:
        p = Premailer(
            html=infile,
            base_url=options.base_url,
            preserve_internal_links=options.preserve_internal_links,
            exclude_pseudoclasses=options.exclude_pseudoclasses,
            keep_style_tags=options.keep_style_tags,
            include_star_selectors=options.include_star_selectors,
            remove_classes=options.remove_classes,
            strip_important=options.strip_important
        )
    except PremailerError, e:
        raise SystemExit(e)
    else:
        outfile.write(p.transform())


if __name__ == '__main__':
    main()
