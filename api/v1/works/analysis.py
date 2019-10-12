from lxml import etree


ns = {'xml': 'http://www.w3.org/XML/1998/namespace',
      'tei': 'http://www.tei-c.org/ns/1.0',
      'xi': 'http://www.w3.org/2001/XInclude'}

# Element type definitions
structural_elems = \
    ['self::tei:div[@type != "work_part"]',
     'self::tei:back',
     'self::tei:front',
     'self::tei:text[@type = "work_volume"]']
main_elems = \
    ['self::tei:p',
     'self::tei:signed',
     'self::tei:head[not(ancestor::tei:list)]',
     'self::tei:titlePage',
     'self::tei:lg',
     'self::tei:label[@place != "margin"]',
     'self::tei:argument[not(ancestor::tei:list)]',
     'self::tei:table']
marginal_elems = \
    ['self::tei:note[@place = "margin"]',
     'self::tei:label[@place = "margin"]']
page_elems = \
    ['self::tei:pb[not(@sameAs or @corresp)]']
anchor_elems = \
    ['self::tei:milestone[@unit != "other"]']
    # TODO: inline labels
list_elems = \
    ['self::tei:list',
     'self::tei:item',
     'self::tei:head[ancestor::tei:list]',
     'self::tei:argument[ancestor::tei:list]']


# TODO
def validate(wid, tei_root):
    # @xml:id
    # xincludes resolved
    # basic structure: teiHeader, text, body
    pass


# TODO
def extract_metadata(wid, tei_header):
    pass


def extract_text_structure(wid, node):
    if etree.iselement(node):
        if get_elem_type(node) and len(node.xpath('./@xml:id')):
            #print('Found index node: ' + node.tag)
            #sal_node = etree.Element('sal_node')
            #sal_children = ...
            #return sal_node
            for child in node:
                extract_text_structure(wid, child)
        else:
            for child in node:
                extract_text_structure(wid, child)
    else:
        pass


def get_elem_type(elem):
    """
    Determines the type of an indexable element. If the element is not indexable, an empty string is returned.
    """
    if is_structural_elem(elem):
        print('Found structural element: ' + elem.tag)
        return 'structural'
    elif is_main_elem(elem):
        print('Found main element: ' + elem.tag)
        return 'main'
    elif is_marginal_elem(elem):
        print('Found marginal element: ' + elem.tag)
        return 'marginal'
    elif is_page_elem(elem):
        print('Found page element: ' + elem.tag)
        return 'page'
    elif is_anchor_elem(elem):
        print('Found anchor element: ' + elem.tag)
        return 'anchor'
    elif is_list_elem(elem):
        print('Found list element: ' + elem.tag)
        return 'list'
    else:
        return ''



def is_structural_elem(elem):
    for expr in structural_elems:
        if len(elem.xpath(expr, namespaces=ns)):
            return True
    return False


def is_main_elem(elem):
    if check_main_ancestors(elem):
        for expr in main_elems:
            if len(elem.xpath(expr, namespaces=ns)):
                return True
    return False


def check_main_ancestors(elem):
    for ancestor in elem.xpath('ancestor::*'):
        if is_main_elem(ancestor) or is_marginal_elem(ancestor) or is_list_elem(ancestor):
            # use 'self::tei:list' instead of 'is_list_elem(ancestor)' in case of endless loop
            return False
    return True


def is_marginal_elem(elem):
    for expr in marginal_elems:
        if len(elem.xpath(expr, namespaces=ns)):
            return True
    return False


def is_anchor_elem(elem):
    for expr in anchor_elems:
        if len(elem.xpath(expr, namespaces=ns)):
            return True
    return False


def is_page_elem(elem):
    for expr in page_elems:
        if len(elem.xpath(expr, namespaces=ns)):
            return True
    return False


def is_list_elem(elem):
    if check_list_ancestors(elem):
        for expr in list_elems:
            if len(elem.xpath(expr, namespaces=ns)):
                return True
    return False


def check_list_ancestors(elem):
    for ancestor in elem.xpath('ancestor::*'):
        if is_main_elem(ancestor) or is_marginal_elem(ancestor):
            return False
    return True

