
from abc import ABC, abstractmethod


class DocHTMLTransformer(ABC):
    """
    Transforms a basic node's TEI into HTML.
    """

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def transform_basic_node(self):
        pass


class GuidelinesHTMLTransformer(DocHTMLTransformer):

    def __init__(self, config):
        self.config = config

    def transform_basic_node(self):
        return 'test' # TODO


class ProjectmembersHTMLTransformer(DocHTMLTransformer):

    def __init__(self, config):
        self.config = config

    def transform_basic_node(self):
        return 'test' # TODO


class ProjectdescHTMLTransformer(DocHTMLTransformer):
    pass
