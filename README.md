premailer
=========

[![Travis](https://travis-ci.org/peterbe/premailer.png?branch=master)](https://travis-ci.org/peterbe/premailer)


Turns CSS blocks into style attributes
--------------------------------------

When you send HTML emails you can't used style tags but instead you
have to put inline `style` attributes on every element. So from this:

        <html>
        <style type="text/css">
        h1 { border:1px solid black }
        p { color:red;}
        </style>
        <h1 style="font-weight:bolder">Peter</h1>
        <p>Hej</p>
        </html>

You want this:

        <html>
        <h1 style="font-weight:bolder; border:1px solid black">Peter</h1>
        <p style="color:red">Hej</p>
        </html>


premailer does this. It parses an HTML page, looks up `style` blocks
and parses the CSS. It then uses the `lxml.html` parser to modify the
DOM tree of the page accordingly.

Getting started
---------------

If you havena't already done so, install `premailer` first:

        $ pip install premailer

Next, the most basic use is to use the shortcut function, like this:

        >>> from premailer import transform
        >>> print transform("""
        ...         <html>
        ...         <style type="text/css">
        ...         h1 { border:1px solid black }
        ...         p { color:red;}
        ...         p::first-letter { float:left; }
        ...         </style>
        ...         <h1 style="font-weight:bolder">Peter</h1>
        ...         <p>Hej</p>
        ...         </html>
        ... """)
        <html>
        <head></head>
        <body>
        <h1 style="font-weight:bolder; border:1px solid black">Peter</h1>
                <p style="color:red">Hej</p>
                </body>
        </html>

For more advanced options, check out the code of the `Premailer` class
and all its options in its constructor.

You can also use premailer from the command line by using his main module.

    $ python -m premailer -h
    usage: python -m premailer [options]

    optional arguments:
      -h, --help            show this help message and exit
      -f [INFILE], --file [INFILE]
                            Specifies the input file. The default is stdin.
      -o [OUTFILE], --output [OUTFILE]
                            Specifies the output file. The default is stdout.
      --base-url BASE_URL
      --remove-internal-links PRESERVE_INTERNAL_LINKS
                            Remove links that start with a '#' like anchors.
      --exclude-pseudoclasses
                            Pseudo classes like p:last-child', p:first-child, etc
      --preserve-style-tags
                            Do not delete <style></style> tags from the html
                            document.
      --remove-star-selectors
                            All wildcard selectors like '* {color: black}' will be
                            removed.
      --remove-classes      Remove all class attributes from all elements
      --strip-important     Remove '!important' for all css declarations.
      --disable-basic-attributes Disable provided basic attributes (comma separated)
      --disable-validation  Disable CSSParser validation of attributes and values

A basic example:

    $ python -m premailer --base-url=http://google.com/ -f newsletter.html
    <html>
    <head><style>.heading { color:red; }</style></head>
    <body><h1 class="heading" style="color:red"><a href="http://google.com/">Title</a></h1></body>
    </html>

The command line interface supports standard input.

    $ echo '<style>.heading { color:red; }</style><h1 class="heading"><a href="/">Title</a></h1>' | python -m premailer --base-url=http://google.com/
    <html>
    <head><style>.heading { color:red; }</style></head>
    <body><h1 class="heading" style="color:red"><a href="http://google.com/">Title</a></h1></body>
    </html>

Turning relative URLs into absolute URLs
----------------------------------------

Another thing premailer can do for you is to turn relative URLs (e.g.
"/some/page.html" into "http://www.peterbe.com/some/page.html"). It
does this to all `href` and `src` attributes that don't have a `://`
part in it. For example, turning this:

        <html>
        <body>
        <a href="/">Home</a>
        <a href="page.html">Page</a>
        <a href="http://crosstips.org">External</a>
        <img src="/folder/">Folder</a>
        </body>
        </html>

Into this:

        <html>
        <body>
        <a href="http://www.peterbe.com/">Home</a>
        <a href="http://www.peterbe.com/page.html">Page</a>
        <a href="http://crosstips.org">External</a>
        <img src="http://www.peterbe.com/folder/">Folder</a>
        </body>
        </html>

by using `transform('...', base_url='http://www.peterbe.com/')`.


HTML attributes created additionally
------------------------------------

Certain HTML attributes are also created on the HTML if the CSS
contains any ones that are easily translated into HTML attributes. For
example, if you have this CSS: `td { background-color:#eee; }` then
this is transformed into `style="background-color:#eee"` AND as an
HTML attribute `bgcolor="#eee"`.

Having these extra attributes basically as a "back up" for really shit
email clients that can't even take the style attributes. A lot of
professional HTML newsletters such as Amazon's use this.
You can disable some attributes in `disable_basic_attributes`
