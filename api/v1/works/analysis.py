from lxml import etree
from api.v1.xutils import flatten, xml_ns, is_element, exists

# Element type definitions
structural_elem_xpath = \
    'boolean(' + \
    'self::tei:div[@type != "work_part"] or ' + \
    'self::tei:back or ' + \
    'self::tei:front or ' + \
    'self::tei:text[@type = "work_volume"]' + \
    ')'
main_elem_xpath = \
    'boolean(' + \
    'self::tei:p or ' + \
    'self::tei:signed or ' + \
    'self::tei:head[not(ancestor::tei:list)] or ' + \
    'self::tei:titlePage or ' + \
    'self::tei:lg or ' + \
    'self::tei:label[@place != "margin"] or ' + \
    'self::tei:argument[not(ancestor::tei:list)] or ' + \
    'self::tei:table' \
    ')'
marginal_elem_xpath = \
    'boolean(' \
    'self::tei:note[@place = "margin"] or ' \
    'self::tei:label[@place = "margin"]' \
    ')'
page_elem_xpath = \
    'boolean(' \
    'self::tei:pb[not(@sameAs or @corresp)]' \
    ')'
anchor_elem_xpath = \
    'boolean(' \
    'self::tei:milestone[@unit != "other"]' \
    ')' # TODO: inline labels
list_elem_xpath = \
    'boolean(' \
    'self::tei:list or ' \
    'self::tei:item or ' \
    'self::tei:head[ancestor::tei:list] or ' \
    'self::tei:argument[ancestor::tei:list]' \
    ')'


# XPath classes / functions
is_structural_elem = etree.XPath(structural_elem_xpath, namespaces=xml_ns)
main_ancestors_xpath = 'not(ancestor::*[' + main_elem_xpath + ' or ' + marginal_elem_xpath + ' or ' + list_elem_xpath + '])'
is_main_elem = etree.XPath(main_elem_xpath + ' and ' + main_ancestors_xpath, namespaces=xml_ns)
is_marginal_elem = etree.XPath(marginal_elem_xpath, namespaces=xml_ns)
is_anchor_elem = etree.XPath(anchor_elem_xpath, namespaces=xml_ns)
is_page_elem = etree.XPath(page_elem_xpath, namespaces=xml_ns)
list_ancestors_xpath = 'not(ancestor::*[' + main_elem_xpath + ' or ' + marginal_elem_xpath + '])'
is_list_elem = etree.XPath(list_elem_xpath + ' and ' + list_ancestors_xpath, namespaces=xml_ns)

basic_list_elem_xpath = \
    """
    boolean(
        (self::tei:list and not(descendant::tei:list)) or
        (
            (self::tei:item or self::tei:head or self::tei:argument) and 
             not(descendant::tei:list) and
             following-sibling::tei:item[child::tei:list[""" + list_elem_xpath + """]]
        )
    )
    """


# read as: 'lists that do not contain lists (=lists at the lowest level), or siblings thereof' # TODO is this working?
is_basic_list_elem = etree.XPath(basic_list_elem_xpath, namespaces=xml_ns)

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
    if is_element(node):
        elem_type = get_elem_type(node)
        if len(node.xpath('./@xml:id')) and elem_type:
            print('Processing ' + elem_type + ' element: ' + node.tag + ' (' + node.xpath('./@xml:id')[0] + ')')
            sal_node = etree.Element('sal_node')
            sal_node.set('id', node.xpath('./@xml:id')[0])
            sal_node.set('name', etree.QName(node).localname)
            sal_node.set('type', elem_type)
            citetrail_prefix = get_citetrail_prefix(node)
            if is_basic_elem(node):
                sal_node.set('basic', 'true')
            if citetrail_prefix:
                sal_node.set('citetrailPrefix', citetrail_prefix)
            sal_children = flatten([extract_text_structure(wid, child) for child in node])
            for sal_child in sal_children:
                if etree.iselement(sal_child):
                    print('Found sal_child!')
                    sal_node.append(sal_child)
                elif isinstance(sal_child, list):
                    print('Found list: ' + '; '.join(sal_child))
            return sal_node
        else:
            return [extract_text_structure(wid, child) for child in node]
    else:
        pass


def get_citetrail_prefix(elem):
    if is_page_elem(elem):
        return 'p'
    elif is_marginal_elem(elem):
        return 'n'
    elif is_anchor_elem(elem) and exists(elem, 'self::tei:milestone[@unit]'):
        return elem.get('unit')
    elif is_structural_elem(elem):
        if exists(elem, 'self::tei:text[@type = "work_volume"]'):
            return 'vol'
        elif exists(elem, 'self::tei:front'):
            return 'frontmatter'
        elif exists(elem, 'self::tei:back'):
            return 'backmatter'
        else:
            return ''
    elif is_main_elem(elem):
        if exists(elem, 'self::tei:head'):
            return 'heading'
        elif exists(elem, 'self::tei:titlePage'):
            return 'titlepage'
        else:
            return ''
    elif is_list_elem(elem):
        if exists(elem, 'self::tei:list[@type = "dict" or @type = "index"]'):
            return elem.get('type')
        elif exists(elem, 'self::tei:item[ancestor::tei:list[@type = "dict"]]'):
            return 'entry'
        else:
            return ''
    else:
        return ''



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


def is_basic_elem(node):
    return is_main_elem(node) or is_marginal_elem(node) or (is_list_elem(node) and is_basic_list_elem(node))
