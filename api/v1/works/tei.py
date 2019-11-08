from lxml import etree
from api.v1.xutils import exists, xml_ns, copy_attributes, tei_ns


def wrap_tei_node_in_ancestors(node: etree._Element, wrapped_node: etree._Element):
    """Recursively wraps a tei node in its (non-technical) ancestor nodes.
    @param node: the node in the original tree, required for navigating the tree towards the top
    @param wrapped_node: a copy of the original node or its wrapping, which will eventually be returned
    """
    ancestors = node.xpath('ancestor::*[not(self::tei:TEI or self::tei:text[@type = "work_part"])]', namespaces=xml_ns)
    if len(ancestors):
        ancestor = ancestors[-1]  # ancestors are in document order
        wrap = etree.Element(etree.QName(ancestor).localname)
        copy_attributes(ancestor, wrap)
        wrap.append(wrapped_node)
        return wrap_tei_node_in_ancestors(ancestor, wrap)
    else:
        # declare the tei namespace on the root element
        wrapped_node.set('xmlns', xml_ns['tei'])
        return wrapped_node


# TODO metadata of a specific node/fragment (here or somewhere downstream?)
