from lxml import etree
from api.v1.xutils import flatten, xml_ns, is_element, exists
from api.v1.works.txt import txt_dispatch, normalize_space
from api.v1.works.factory import config
from api.v1.works.fragmentation import *
import re


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
            is_basic = is_basic_elem(node)
            if is_basic:
                sal_node.set('basic', 'true')
            if citetrail_prefix:
                sal_node.set('citetrailPrefix', citetrail_prefix)
                # TODO: build citetrail: citetrail_prefix + citetrail_name + position
            # list nodes require some more information about their fragmentation depth
            if is_basic and elem_type == 'list':
                sal_node.set('listLevel', str(len(node.xpath('ancestor::tei:list', namespaces=xml_ns))))
                sal_node.set('listParent', node.xpath('ancestor::tei:list[1]/@xml:id', namespaces=xml_ns)[0])
                # TODO: use citetrail rather than xml:id of listParent
                # TODO: some information about the kind of list (get_list_type)? in items or list?
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

# TODO: notes within lists?


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



# NODE TITLES


def get_node_title(node):
    name = etree.QName(node).localname
    xml_id = node.xpath('@xml:id', namespaces=xml_ns)[0]
    if name == 'div':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n') and node.get('type'):
            return node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            return make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        elif exists(node, 'tei:list/tei:head'):
            return make_teaser_from_element(node.xpath('tei:list/tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei_list/tei:label'):
            return make_teaser_from_element(node.xpath('tei:list/tei:label[1]', namespaces=xml_ns)[0])
        else:
            return ''
    elif name == 'item':
        #if exists(node, 'parent::tei:list[@type="dict"] and descendant::tei:term[1]/@key'):
        #    return '"' + node.xpath('descendant::tei:term[1]/@key')[0] + '"'
        #    # TODO this needs revision when we have really have such dict. lists
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            return node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"]'):
            return make_teaser_from_element(
                node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"][1]', namespaces=xml_ns)[0])
        else:
            return ''
    elif name == 'lg':
        if exists(node, 'tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        else:
            return make_teaser_from_element(node)
    elif name == 'list':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            return make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            return make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            return node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            return make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        else:
            return ''
    elif name == 'milestone':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '"' + node.get('n') + '"'
        elif node.get('n'):
            return node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
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