"""
Baptiste's Basic Blog engine

Available commands:

    - mkdindex /path/to/article.html
        Output the HTML for the article's card that will be listed on the index.
"""
from dataclasses import dataclass
from datetime import date
from functools import partial
from html import escape as htmlescape
from pathlib import Path
import sys
import textwrap

from lxml import html


BLOG_DIR = Path(__file__).parent / "blog"


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

    def as_card(self, indent=0):
        s = """
<article>
  <h2><a href="/{url}">{title}</a></h2>
  <p>
    <small>Published on <time datetime="{pubdate}">{pubdate_str}</time></small>
  </p>
</article>
        """.strip().format(
            title=htmlescape(self.title),
            url=self.path.relative_to(BLOG_DIR),
            pubdate=self.pubdate.isoformat(),
            pubdate_str=self.pubdate_str,
        )
        if indent:
            s = textwrap.indent(s, indent * " ")
        return s


if __name__ == '__main__':
    subcommand, filepath = sys.argv[1:]
    assert subcommand == 'mkindex'  # TODO: proper argparser
    filepath = Path(filepath).resolve()
    article = Article.frompath(filepath)
    print(article.as_card(indent=6))


