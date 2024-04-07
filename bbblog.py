"""
Baptiste's Basic Blog engine

Use ./bbblog.py --help to see all available commands
"""
from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
from pathlib import Path
import sys
import textwrap

from jinja2 import Environment, PackageLoader
from lxml import html
import typer


BLOG_DIR = Path(__file__).parent / "blog"

JINJAENV = Environment(loader=PackageLoader("bbblog"), autoescape=True)


def render_template(name: str, **context) -> str:
    template = JINJAENV.get_template(name)
    return template.render(**context)


def _xpath(tree, xpath:str):
    found, = tree.xpath(xpath)
    return found


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


def rewrite_dates(source: str, old_date: date, new_date: date) -> str:
    """
    Find instances of `old_date` in the given HTML source and rewrite them to use `new_date`.
    Return the modified HTML source.
    """
    parsed = html.fromstring(source)
    for node in parsed.xpath(f"//time[@datetime='{old_date.isoformat()}']"):
        node.attrib["datetime"] = new_date.isoformat()
        node.text = new_date.strftime("%B %-dth")

    return html.tostring(parsed, pretty_print=True, encoding="unicode")


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
    slug = "-".join(map(str.lower, title))

    context = {
        "title": " ".join(title),
        "pubdate": TODAY,
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


if __name__ == '__main__':
    app()
