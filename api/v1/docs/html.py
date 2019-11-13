
from abc import ABC, abstractmethod


class DocHTMLTransformer(ABC):
    """
    Transforms a basic node's TEI into HTML.
    """

    @abstractmethod
    def transform_basic_node(self):
        pass


class GuidelinesHTMLTransformer(DocHTMLTransformer):
    pass


class ProjectmembersHTMLTransformer(DocHTMLTransformer):
    pass


class ProjectdesHTMLTransformer(DocHTMLTransformer):
    pass
