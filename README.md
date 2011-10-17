premailer
=========


Turns CSS blocks into style attributes
--------------------------------------

When you send HTML emails you can't used style tags but instead you
have to put inline `style` attributes on every element. So from this:

        <html>
        <style type="text/css">
        h1 { border:1px solid black }
        p { color:red;}
        p::first-letter { float:left; }
        </style>
        <h1 style="font-weight:bolder">Peter</h1>
        <p>Hej</p>
        </html>

You want this:

        <html>
        <h1 style="font-weight:bolder; border:1px solid black">Peter</h1>
        <p style="{color:red} ::first-letter{float:left}">Hej</p>
        </html>


premailer does this. It parses an HTML page, looks up `style` blocks
and parses the CSS. It then uses the `lxml.html` parser to modify the
DOM tree of the page accordingly.


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
