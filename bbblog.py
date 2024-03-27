"""
Baptiste's Basic Blog engine

Use ./bbblog.py --help to see all available commands
"""
from dataclasses import dataclass
from datetime import date
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


if __name__ == '__main__':
    app()
