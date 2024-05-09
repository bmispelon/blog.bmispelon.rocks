"""
Baptiste's Basic Blog engine

Use ./bbblog.py --help to see all available commands
"""
from dataclasses import dataclass
from datetime import date, datetime
from functools import partial, wraps
from io import StringIO
from pathlib import Path
import random
import sys
import subprocess
import textwrap

from jinja2 import Environment, PackageLoader
from lxml import html
from lxml.etree import _ElementTree
import typer


BLOG_DIR = Path(__file__).parent / "blog"

JINJAENV = Environment(loader=PackageLoader("bbblog"), autoescape=True)


def render_template(name: str, **context) -> str:
    template = JINJAENV.get_template(name)
    return template.render(**context)


def _xpath(tree, xpath:str):
    found, = tree.xpath(xpath)
    return found


def _prettier_html(source: str) -> str:
    # using --stdin-filepath with a fake .html filename seems to better match
    # the behavior of prettier -w so we use that instead of manually specifying
    # --parser html.
    return subprocess.check_output(
        ["prettier", "--stdin-filepath", "test.html"],
        input=(source),
        text=True,
    )


def _prettyprint_html(tree):
    source = html.tostring(
        tree,
        pretty_print=True,
        encoding="unicode",
        doctype="<!doctype html>",
    )
    return _prettier_html(source)


def autohtml(fn):
    """
    A decorator for functions that take parsed HTML on the way in and modify it.
    The incoming HTML will be automatically parsed, the resulting tree will be
    passed to the original function then serialized back into a str on the way out.
    """
    @wraps(fn)
    def decorated(source:str, *args, **kwargs) -> str:
        parsed = html.fromstring(source)
        fn(parsed, *args, **kwargs)
        return _prettyprint_html(parsed)

    return decorated


def get_random_header_variant():
    """
    Return a random variant class for the <header> (see styles.css)
    """
    variants = [f"variant{i}" for i in range(1, 8)]
    return random.choice(variants)


@dataclass
class Article:
    title: str
    pubdate_str: str
    pubdate: date
    path: Path

    @classmethod
    def frompath(cls, article: Path):
        parsed = html.parse(article)
        x = partial(_xpath, parsed)
        return cls(
            title=x('//main/article/h1').text_content().strip(),
            pubdate_str=x('//main/article//*[@class="metadata-pubdate"]//time').text_content(),
            pubdate=date.fromisoformat(x('//main/article//*[@class="metadata-pubdate"]//time').attrib['datetime']),
            path=article,
        )

    @property
    def absolute_url(self) -> str:
        return Path("/") / self.path.relative_to(BLOG_DIR)

    def as_card(self, indent=0):
        card = render_template("_index_card.html", article=self)
        if indent:
            card = textwrap.indent(card, indent * " ")
        return card


@autohtml
def rewrite_dates(parsed: _ElementTree, old_date: date, new_date: date):
    """
    Find instances of `old_date` in the given HTML source and rewrite them to use `new_date`.
    Return the modified HTML source.
    """
    parsed = html.fromstring(source)
    for node in parsed.xpath(f"//time[@datetime='{old_date.isoformat()}']"):
        node.attrib["datetime"] = new_date.isoformat()
        node.text = new_date.strftime("%B %-dth")


@autohtml
def rewrite_header_class(parsed: _ElementTree, new_header_class):
    """
    Replace the class of the <header> in the given source and return the new
    source.
    """
    header = _xpath(parsed, "//body/header")
    header.attrib["class"] = new_header_class


app = typer.Typer()


@app.command()
def mkindex(filepath: Path):
    """
    Output the HTML for the article's card that will be listed on the index.
    """
    filepath = filepath.resolve()
    article = Article.frompath(filepath)
    print(article.as_card(indent=6))


@app.command()
def mkarticle(title: list[str]) -> Path:
    """
    Create an article stub file in the blog/articles directory
    """
    TODAY = date.today()
    slug = "-".join(map(str.lower, title)).replace(":", "")

    context = {
        "title": " ".join(title),
        "pubdate": TODAY,
        "header_variant": get_random_header_variant(),
    }

    articlepath = BLOG_DIR / "articles" / str(TODAY.year) / f"{TODAY.isoformat()}-{slug}.html"
    assert not articlepath.exists()
    articlepath.write_text(render_template("article.html", **context))
    print(f"Created a new article at {articlepath.relative_to(Path.cwd())}")
    return articlepath


@app.command()
def changedate(filepath: Path, newdate: datetime = datetime.now()) -> Path:
    """
    Change the date of the given article, return the new path. If no date is
    given, uses the current date.
    """
    newdate: date = newdate.date()  # XXX: typer currently only supports datetime, not date

    datestr, basetitle = filepath.name[:10], filepath.name[10:]
    articledate = date.fromisoformat(datestr)

    newpath = filepath.parent.parent / str(newdate.year) / f"{newdate.isoformat()}{basetitle}"
    newcontent = rewrite_dates(filepath.read_text(), articledate, newdate)

    # Create the year directory in case we're changing year
    newpath.parent.mkdir(parents=True, exist_ok=True)

    filepath.rename(newpath)
    newpath.write_text(newcontent)

    print(f"Renamed and updated {filepath} -> {newpath}")
    return newpath


@app.command()
def randomizeheader(filepaths: list[Path]):
    """
    Change the header variant class used in the given file(s)
    """
    for filepath in filepaths:
        variant = get_random_header_variant()
        old_source = filepath.read_text()
        new_source = rewrite_header_class(old_source, f"container {variant}")
        filepath.write_text(new_source)
        print(f"File {filepath} got new variant {variant}")


if __name__ == '__main__':
    app()
