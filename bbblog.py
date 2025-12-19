"""
Baptiste's Basic Blog engine

Use ./bbblog.py --help to see all available commands
"""

from collections import abc
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import partial, wraps
from operator import attrgetter
from pathlib import Path
import random
import subprocess
import textwrap
import typing

from jinja2 import Environment, PackageLoader
from lxml import etree, html
import typer


BLOG_ROOT_URL = "https://blog.bmispelon.rocks"
BLOG_DIR = Path(__file__).parent / "blog"

JINJAENV = Environment(loader=PackageLoader("bbblog"), autoescape=True)

HtmlTreeOrElement = html.HtmlElement | etree.ElementTree[html.HtmlElement]


def render_template(name: str, **context) -> str:
    template = JINJAENV.get_template(name)
    return template.render(**context)


def _xpath(tree: HtmlTreeOrElement, xpath: str) -> html.HtmlElement:
    (found,) = tree.xpath(xpath)
    return found


def _xml(
    tag: str, text: str | None = None, tail: str | None = None, **attrib
) -> etree.Element:
    node = etree.Element(tag, **attrib)
    if text is not None:
        node.text = text
    if tail is not None:
        node.tail = tail
    return node


def _atomdate(d: date) -> str:
    return datetime.combine(d, time(0)).isoformat() + "Z"


def _prettier_html(source: str) -> str:
    # using --stdin-filepath with a fake .html filename seems to better match
    # the behavior of prettier -w so we use that instead of manually specifying
    # --parser html.
    return subprocess.check_output(
        ["prettier", "--stdin-filepath", "test.html"],
        input=(source),
        text=True,
    )


def _prettyprint_html(tree: HtmlTreeOrElement, prettier: bool = True, **kwargs) -> str:
    kwargs.setdefault("pretty_print", True)
    kwargs.setdefault("doctype", "<!doctype html>")
    kwargs.setdefault("encoding", "unicode")

    source = html.tostring(tree, **kwargs)
    if prettier:
        return _prettier_html(source)
    else:
        return source


def _prettyprint_xml(tree: etree.ElementTree | etree.Element) -> str:
    etree.indent(tree)
    return etree.tostring(
        tree,
        xml_declaration=True,
        encoding="utf-8",
    ).decode("utf-8")


def _mkrss(index_dir: Path, max_entries: int) -> etree.Element:
    feed = _xml("feed", xmlns="http://www.w3.org/2005/Atom")
    feed.append(_xml("title", text="{# Blog title goes here #}"))
    feed.append(_xml("subtitle", text="A blog by Baptiste Mispelon"))
    feed.append(_xml("link", href=f"{BLOG_ROOT_URL}/atom.xml", rel="self"))
    feed.append(_xml("link", href=f"{BLOG_ROOT_URL}/"))
    feed.append(_xml("id", text=f"{BLOG_ROOT_URL}/"))

    articles = [Article.frompath(p) for p in index_dir.glob("**/*.html")]
    articles.sort(key=attrgetter("pubdate"), reverse=True)

    if not articles:
        return feed

    feed.append(_xml("updated", text=_atomdate(articles[0].pubdate), tail="\n\n"))

    for article in articles[:max_entries]:
        entry = article.as_atom_entry()
        entry.tail = "\n\n"
        feed.append(entry)

    return feed


def rewrite_html[**P](
    fn: abc.Callable[typing.Concatenate[html.HtmlElement, P], None],
) -> abc.Callable[typing.Concatenate[Path, P], None]:
    """
    A decorator to help write functions that modify a HTML file in place.

    The decorated function should take an ElementTree as a first argument
    and modify it in place.
    The decorator will transform that function into a new one that takes in
    a filepath, reads its content, parses it as HTML, feeds it to the original
    function, then writes the modified tree back to the file.
    """

    @wraps(fn)
    def decorated(filepath: Path, *args: P.args, **kwargs: P.kwargs) -> None:
        parsed = html.fromstring(filepath.read_text())
        fn(parsed, *args, **kwargs)
        filepath.write_text(_prettyprint_html(parsed))

    return decorated


def get_random_header_variant() -> str:
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
    content: str

    @classmethod
    def frompath(cls, article: Path):
        parsed = html.parse(article)
        x = partial(_xpath, parsed)
        return cls(
            title=x("//main/article/h1").text_content().strip(),
            pubdate_str=x(
                '//main/article//*[@class="metadata-pubdate"]//time'
            ).text_content(),
            pubdate=date.fromisoformat(
                x('//main/article//*[@class="metadata-pubdate"]//time').attrib[
                    "datetime"
                ]
            ),
            path=article,
            content=_prettyprint_html(
                _xpath(parsed, "//main/article"), pretty_print=True, doctype=None
            ),
        )

    @property
    def absolute_url(self) -> Path:
        return Path("/") / self.path.relative_to(BLOG_DIR)

    def as_card(self, indent=0):
        card = render_template("_index_card.html", article=self)
        if indent:
            card = textwrap.indent(card, indent * " ")
        return card

    def as_atom_entry(self) -> etree.Element:
        entry = etree.Element("entry")
        author = etree.Element("author")
        author.append(_xml("name", "Baptiste Mispelon"))

        entry.append(_xml("title", text=self.title))
        entry.append(_xml("link", href=f"{BLOG_ROOT_URL}{self.absolute_url}"))
        entry.append(_xml("id", text=f"{BLOG_ROOT_URL}{self.absolute_url}"))
        entry.append(_xml("published", text=_atomdate(self.pubdate)))
        entry.append(_xml("updated", text=_atomdate(self.pubdate)))
        # TODO: remove <script>, <style>, and x-* attributes
        entry.append(_xml("content", type="html", text=self.content))
        entry.append(author)
        return entry


@rewrite_html
def rewrite_dates(parsed: html.HtmlElement, old_date: date, new_date: date):
    """
    Find instances of `old_date` in the given HTML source and rewrite them to use `new_date`.
    Return the modified HTML source.
    """
    for node in parsed.xpath(f"//time[@datetime='{old_date.isoformat()}']"):
        node.attrib["datetime"] = new_date.isoformat()
        node.text = new_date.strftime("%B %-dth")


@rewrite_html
def rewrite_header_class(parsed: html.HtmlElement, new_header_class: str):
    """
    Replace the class of the <header> in the given source and return the new
    source.
    """
    header = _xpath(parsed, "//body/header")
    header.attrib["class"] = new_header_class


@rewrite_html
def insert_card(parsed: html.HtmlElement, card_source: str):
    card = html.fragment_fromstring(card_source)
    card.tail = "\n\n"  # make sure there's a blank line after the card
    h1 = _xpath(parsed, '//h1[text()="Articles"]')
    main = h1.getparent()
    assert main is not None
    main.insert(main.index(h1) + 1, card)


app = typer.Typer()


@app.command()
def mkindex(filepath: Path) -> None:
    """
    Add a card for the given article to the index (just after <h1>).
    """
    filepath = filepath.resolve()
    article = Article.frompath(filepath)
    index = BLOG_DIR / "index.html"
    insert_card(index, article.as_card())
    print(f"Added card for {filepath} to {index}")


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

    articledir = BLOG_DIR / "articles" / str(TODAY.year)
    articledir.mkdir(parents=True, exist_ok=True)
    articlepath = articledir / f"{TODAY.isoformat()}-{slug}.html"
    assert not articlepath.exists()
    articlepath.write_text(render_template("article.html", **context))
    print(f"Created a new article at {articlepath.relative_to(Path.cwd())}")
    return articlepath


@app.command()
def changedate(filepath: Path, newdate_: datetime = datetime.now()) -> Path:
    """
    Change the date of the given article, return the new path. If no date is
    given, uses the current date.
    """
    newdate: date = (
        newdate_.date()
    )  # XXX: typer currently only supports datetime, not date

    datestr, basetitle = filepath.name[:10], filepath.name[10:]
    articledate = date.fromisoformat(datestr)

    newpath = (
        filepath.parent.parent / str(newdate.year) / f"{newdate.isoformat()}{basetitle}"
    )

    # Create the year directory in case we're changing year
    newpath.parent.mkdir(parents=True, exist_ok=True)

    filepath.rename(newpath)
    rewrite_dates(newpath, articledate, newdate)

    print(f"Renamed and updated {filepath} -> {newpath}")
    return newpath


@app.command()
def randomizeheader(filepaths: list[Path]) -> None:
    """
    Change the header variant class used in the given file(s)
    """
    for filepath in filepaths:
        variant = get_random_header_variant()
        rewrite_header_class(filepath, f"container {variant}")
        print(f"File {filepath} got new variant {variant}")


@app.command()
def mkrss(max_entries: int = 50) -> None:
    """
    Generate an RSS (atom) feed of the index page
    """
    feed = _mkrss(BLOG_DIR / "articles", max_entries=max_entries)
    atom_file = BLOG_DIR / "atom.xml"
    atom_file.write_text(_prettyprint_xml(feed))
    print(f"Wrote RSS feed to {atom_file}")


if __name__ == "__main__":
    app()
