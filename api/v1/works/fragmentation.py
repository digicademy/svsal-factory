from lxml import etree
from api.v1.xutils import xml_ns


structural_elem_xpath = \
    """
    boolean(
        self::tei:div[@type != "work_part"] or
        self::tei:back or 
        self::tei:front or 
        self::tei:text[@type = "work_volume"] 
    )
    """
main_elem_xpath = \
    """
    boolean( 
        self::tei:p or  
        self::tei:signed or  
        self::tei:head[not(ancestor::tei:list)] or  
        self::tei:titlePage or  
        self::tei:lg or  
        self::tei:label[@place != "margin"] or  
        self::tei:argument[not(ancestor::tei:list)] or  
        self::tei:table
    )
    """
marginal_elem_xpath = \
    """
    boolean(
        self::tei:note[@place = "margin"] or 
        self::tei:label[@place = "margin"] 
    )
    """
page_elem_xpath = \
    """
    boolean(
        self::tei:pb[not(@sameAs or @corresp)]
    )
    """
anchor_elem_xpath = \
    """
    boolean(
        self::tei:milestone[@unit != "other"]
    )
    """
    # TODO: inline labels?
list_elem_xpath = \
    """
    boolean(
        self::tei:list or 
        self::tei:item or 
        self::tei:head[ancestor::tei:list] or 
        self::tei:argument[ancestor::tei:list]
    )
    """
    # TODO: exclude 'simple' lists / items?
# XPath classes / functions
is_structural_elem = etree.XPath(structural_elem_xpath, namespaces=xml_ns)
main_ancestors_xpath = 'not(ancestor::*[' + main_elem_xpath + ' or ' + marginal_elem_xpath + ' or ' + list_elem_xpath + '])'
is_main_elem = etree.XPath(main_elem_xpath + ' and ' + main_ancestors_xpath, namespaces=xml_ns)
is_marginal_elem = etree.XPath(marginal_elem_xpath, namespaces=xml_ns)
is_anchor_elem = etree.XPath(anchor_elem_xpath, namespaces=xml_ns)
is_page_elem = etree.XPath(page_elem_xpath, namespaces=xml_ns)
list_ancestors_xpath = 'not(ancestor::*[' + main_elem_xpath + ' or ' + marginal_elem_xpath + '])'
is_list_elem = etree.XPath(list_elem_xpath + ' and ' + list_ancestors_xpath, namespaces=xml_ns)


def get_elem_type(elem):
    """
    Determines the type of an indexable element. If the element is not indexable, an empty string is returned.
    """
    if is_structural_elem(elem):
        return 'structural'
    elif is_main_elem(elem):
        return 'main'
    elif is_marginal_elem(elem):
        return 'marginal'
    elif is_page_elem(elem):
        return 'page'
    elif is_anchor_elem(elem):
        return 'anchor'
    elif is_list_elem(elem):
        return 'list'
    else:
        return ''


basic_list_elem_xpath = \
    """
    boolean(
        (self::tei:item or self::tei:head or self::tei:argument) and not(descendant::tei:list)
    )
    """
    # items, arguments, and heads that do not contain lists (= lowest level list elements)
    # TODO extend element types (are there other elems than item, argument and head?)
is_basic_list_elem = etree.XPath(list_elem_xpath + ' and ' + list_ancestors_xpath
                                 + ' and ' + basic_list_elem_xpath
                                 + ' and not(ancestor::*[' + basic_list_elem_xpath + '])',
                                 namespaces=xml_ns)
# TODO verify that this reaches all text nodes in lists, without duplicates

# old, much more complicated version:
#basic_list_elem_xpath = \
    #boolean(
    #    (self::tei:item and not(descendant::tei:list))
    #    or
    #    ((self::tei:argument or self::tei:head or self::tei:p)
    #        and not(ancestor::*[self::tei:item and not(descendant::tei:list)])
    #        and not(ancestor::*[self::tei:argument or self::tei:head or self::tei:p]))
    #)
# read as: 'items that do not contain lists, or other elements such as argument, head (add more elements there if
# necessary!) that do not occur within such items'
#is_basic_list_elem = etree.XPath(basic_list_elem_xpath, namespaces=xml_ns)


def is_basic_elem(node):
    return is_main_elem(node) or is_marginal_elem(node) or is_basic_list_elem(node)


def has_basic_ancestor(node):
    basic_ancestor = False
    for anc in node.xpath('ancestor::*'):
        if is_basic_elem(anc):
            basic_ancestor = True
    return basic_ancestor
    # TODO formulate this as a single xpath for increasing performance