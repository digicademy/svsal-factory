
class TEIMarkupError(Exception):
    """Base class for exceptions originating from markup constructs that the factory doesn't know how to deal with."""
    pass


class TEIUnkownElementError(Exception):
    pass


class NodeIndexingError(Exception):
    """Base class for exceptions that occur during node indexing"""
    pass


class QueryValidationError(Exception):
    """Base class for exceptions that originate from query parameters that could not be mapped to valid resources."""
    # TODO this should ideally reside somewhere upstream, so that we can return a valid error code etc. to the client
    #  see https://flask.palletsprojects.com/en/1.1.x/patterns/apierrors/
    pass
