from lxml import etree
from api.v1.xutils import xml_ns

structural_elem_xpath = \
    """
    boolean(
        self::tei:div[not(ancestor::tei:teiHeader)] or
        self::tei:listPerson[not(ancestor::tei:teiHeader)] or
        self::tei:charDecl[ancestor::tei:teiHeader]
    )
    """

is_structural_elem = etree.XPath(structural_elem_xpath, namespaces=xml_ns)
is_basic_elem = etree.XPath(structural_elem_xpath + ' and not(descendant::*[' + structural_elem_xpath + '])',
                            namespaces=xml_ns)
# simple data/citation model: there are only structural nodes, and the most low-level nodes are citable

