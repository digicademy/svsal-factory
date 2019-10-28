
class TEIMarkupError(Exception):
    """Base class for exceptions originating from markup constructs that the factory doesn't know how to deal with."""
    pass

class TEIUnkownElementError(Exception):
    pass

class NodeIndexingError(Exception):
    """Base class for exceptions that occur during node indexing"""
    pass