from lxml import etree
from api.v1.xutils import flatten, xml_ns, is_element, exists
from api.v1.works.txt import txt_dispatch, normalize_space
from api.v1.works.factory import config
import re



# ELEMENT TYPES


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


def is_basic_list_elem(elem):
    return bool(is_list_elem(elem) and len(elem.xpath('ancestor::tei:list', namespaces=xml_ns)) == 0)
    # Only top-level lists count as basic elements. This might produce rather large basic txt/html units for long
    # lists (such as indices), but defining regular, basic units on deeper list levels becomes quite difficult when
    # lists are unevenly or deeply nested.


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



# STRUCTURAL ANALYSIS AND NODE INDEXING


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
                # TODO: build citetrail: citetrail_prefix + citetrail_name + position
            sal_children = flatten([extract_text_structure(wid, child) for child in node])
            # TODO sal_title: note titles (as well as citetrails) need to be suffixed by their position / number
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



# CITETRAILS


def get_citetrail_prefix(elem):
    """
    Note: this function assumes that get_element_type(elem) == True
    """
    if is_page_elem(elem):
        return 'p'
    elif is_marginal_elem(elem):
        return 'n'
    elif is_anchor_elem(elem) and exists(elem, 'self::tei:milestone[@unit]'):
        return elem.get('unit')
    elif is_structural_elem(elem) and exists(elem, 'self::tei:text[@type = "work_volume"]'):
        return 'vol'
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


def get_citetrail_name(elem):
    """
    Note: this function assumes that get_element_type(elem) == True
    """
    name = etree.QName(elem).localname
    if name == 'front':
        return 'frontmatter'
    elif name == 'back':
        return 'backmatter'
    elif name == 'item':
        pass # TODO



# SECTION TITLES


def get_node_title(node):
    name = etree.QName(node).localname
    xml_id = node.xpath('@xml:id', namespaces=xml_ns)[0]
    if name == 'div':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists('tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists('tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n') and node.get('type'):
            return node.get('n')
        elif exists('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            return make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        elif exists('tei:list/tei:head'):
            return make_teaser_from_element(node.xpath('tei:list/tei:head[1]', namespaces=xml_ns)[0])
        elif exists('tei_list/tei:label'):
            return make_teaser_from_element(node.xpath('tei:list/tei:label[1]', namespaces=xml_ns)[0])
        else:
            return ''
    elif name == 'item':
        #if exists('parent::tei:list[@type="dict"] and descendant::tei:term[1]/@key'):
        #    return '"' + node.xpath('descendant::tei:term[1]/@key')[0] + '"'
        #    # TODO this needs revision when we have really have such dict. lists
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists('tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists('tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            return node.get('n')
        elif exists('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"]'):
            return make_teaser_from_element(
                node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"][1]', namespaces=xml_ns)[0])
        else:
            return ''
    elif name == 'lg':
        if exists('tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        else:
            return make_teaser_from_element(node)
    elif name == 'list':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists('tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists('tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            return node.get('n')
        elif exists('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            return make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        else:
            return ''
    elif name == 'milestone':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif node.get('n'):
            return node.get('n')
        elif exists('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            return make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        else:
            return ''
    elif name == 'note':
        if node.get('n'):
            return '"' + node.get('n') + '"'
        else:
            return '' # TODO: in this case, the note title must be derived from the position of the note
    elif name == 'pb':
        if node.get('n') and re.match(r'fol\.', node.get('n')):
            return node.get('n')
        else:
            return 'p. ' + node.get('n')
        # one could also prepend a 'Vol. ' prefix here in case of a multivolume work
    elif name == 'text':
        if node.get('type') == 'work_volume':
            return node.get('n')
        else:
            return ''
    elif name == 'head' or name == 'label' or name == 'p' or name == 'signed' or name == 'titlePart':
        return make_teaser_from_element(node)
    else:
        return ''


# TODO HTML title


def make_teaser_from_element(elem):
    normalized_text = normalize_space(re.sub(r'\{.*?\}', '', re.sub(r'\[.*?\]', '', txt_dispatch(elem, 'edit'))))
    if len(normalized_text) > config.teaser_length:
        shortened = normalize_space(normalized_text[:config.teaser_length])
        return '"' + shortened + '…"'
    else:
        return '"' + normalized_text + '"'


# TODOS


    # TODO
    def validate(wid, tei_root):
        # @xml:id
        # xincludes resolved
        # basic structure: teiHeader, text, body
        # every text node is within is_basic_element
        pass

    # TODO
    def extract_metadata(wid, tei_header):
        pass