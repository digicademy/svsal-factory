from lxml import etree
from api.v1.works.xutils import flatten, xml_ns, is_element



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
            sal_node.set('n', node.xpath('./@xml:id')[0])
            sal_node.set('type', elem_type)
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


def get_elem_type(elem):
    """
    Determines the type of an indexable element. If the element is not indexable, an empty string is returned.
    """
    if is_structural_elem(elem):
        #print('Found structural element: ' + elem.tag)
        return 'structural'
    elif is_main_elem(elem):
        #print('Found main element: ' + elem.tag)
        return 'main'
    elif is_marginal_elem(elem):
        #print('Found marginal element: ' + elem.tag)
        return 'marginal'
    elif is_page_elem(elem):
        #print('Found page element: ' + elem.tag)
        return 'page'
    elif is_anchor_elem(elem):
        #print('Found anchor element: ' + elem.tag)
        return 'anchor'
    elif is_list_elem(elem):
        #print('Found list element: ' + elem.tag)
        return 'list'
    else:
        return ''

