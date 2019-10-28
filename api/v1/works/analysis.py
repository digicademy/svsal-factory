from lxml import etree
from api.v1.xutils import flatten, xml_ns, is_element, exists, get_xml_id, copy_attributes
from api.v1.works.txt import txt_dispatch, normalize_space
from api.v1.works.config import teaser_length as config_teaser_length
from api.v1.works.fragmentation import *
from api.v1.works.errors import NodeIndexingError
import re


# STRUCTURAL ANALYSIS AND NODE INDEXING


def extract_text_structure(wid, node):
    if is_element(node):
        node_type = get_elem_type(node)
        if get_xml_id(node) and node_type:
            sal_node = etree.Element('sal_node')

            # Basic information
            sal_node.set('id', get_xml_id(node))
            sal_node.set('name', etree.QName(node).localname)
            sal_node.set('type', node_type)
            is_basic = is_basic_elem(node)
            if is_basic:
                sal_node.set('basic', 'true')

            # Citable parent (still as xml:id, not citetrail)
            # TODO are citableParents still relevant? if so, should we rather get parents in the next run?
            parent_id = get_citable_parents_xml_id(node, node_type)
            if parent_id:
                sal_node.set('citableParent', parent_id)
            #else:
            #    print('Could not find citable parent: ' + get_xml_id(node))

            # Citetrails (still in preliminary form and not concatenated with node's parents' citetrail parts)
            preliminary_citetrail = normalize_space(get_citetrail_prefix(node, node_type) + get_citetrail_infix(node, node_type))
            if preliminary_citetrail:
                sal_node.set('citetrail', preliminary_citetrail)

            # Preliminary passagetrails
            # TODO

            # List nodes (require some more information about their contexts)
            # TODO check if this works
            if is_basic and node_type == 'list':
                level = len(node.xpath('ancestor::tei:list', namespaces=xml_ns))
                sal_node.set('listLevel', str(level))
                if level > 0:
                    sal_node.set('listParent', node.xpath('ancestor::tei:list[1]/@xml:id', namespaces=xml_ns)[0])
                # TODO: use citetrail rather than xml:id of listParent
                # TODO: some information about the kind of list (get_list_type)? in items or list?

            # Child nodes
            children = list(flatten([extract_text_structure(wid, child) for child in node]))
            # TODO sal_title: note titles (as well as citetrails) need to be suffixed by their position / number
            if len(children) > 0:
                sal_children = etree.Element('children')
                for sal_child in children:
                    if etree.iselement(sal_child):
                        sal_children.append(sal_child)
                    elif isinstance(sal_child, list):
                        raise NodeIndexingError('Found list: ' + '; '.join(sal_child) + ' instead of child::sal_node')
                sal_node.append(sal_children)
            return sal_node
        else:
            return [extract_text_structure(wid, child) for child in node]
    else:
        pass





# TODO verify that this really works
def enrich_index(sal_index):
    from api.v1.works.factory import config
    enriched_index = etree.Element('sal_index')
    for node in sal_index.iter('sal_node'):
        enriched_node = etree.Element('sal_node')
        copy_attributes(node, enriched_node)

        # CITETRAILS
        # determine citetrail position based on preceding-sibling::sal_node with similar citetrails
        this_citetrail = node.get('citetrail')
        revised_citetrail = this_citetrail
        if this_citetrail:
            similar_preceding = len(node.xpath('preceding-sibling::sal_node[@citetrail = "' + this_citetrail + '"]'))
            similar_following = len(node.xpath('following-sibling::sal_node[@citetrail = "' + this_citetrail + '"]'))
            if similar_preceding > 0 or similar_following > 0:
                if re.match(r'\d$', this_citetrail):
                    # if citetrail stem ends with number, use '-' as separator (e.g., for preserving page numbers)
                    revised_citetrail += '-' + str(similar_preceding + 1)
                else:
                    revised_citetrail += str(similar_preceding + 1)
        else:
            # if node has no citetrail stem, simply count similarly unnamed preceding siblings
            revised_citetrail = str(len(node.xpath('preceding-sibling::sal_node[not(@citetrail)]')) + 1)
        # construct full citetrail and put them into node and config.node_mappings
        if node.get('citableParent'):
            parent_citetrail = config.get_node_mappings()[node.get('citableParent')]
            # this assumes that full citetrail has already been written to parent
            full_citetrail = parent_citetrail + '.' + revised_citetrail
            enriched_node.set('citetrail', full_citetrail)
            config.put_node_mapping(node.get('id'), full_citetrail)
        else:
            enriched_node.set('citetrail', revised_citetrail)
            config.put_node_mapping(node.get('id'), revised_citetrail)


        enriched_index.append(enriched_node)
        # make full-blown citetrails
    return enriched_index


def get_ancestor_citetrails(node):
    citable_parent_id = node.get('citableParent')
    citable_parent_node = node.xpath('ancestor::sal_node[@id = "' + citable_parent_id + '"]')
    citetrails = []
    #if citable_parent_id and len(citable_parent_node) > 0:
    #    citetrails = construct_citetrail(citable_parent_node[0])
    #return path


# CITETRAIL UTIL FUNCTIONS


def get_citetrail_prefix(node: etree._Element, node_type: str):
    """
    Citetrails for certain node types are always prefixed with a 'categorical' keyword/string.
    """
    prefix = ''
    name = etree.QName(node).localname
    if node_type == 'page':
        prefix = 'p'
    elif node_type == 'marginal':
        prefix = 'n'
    elif node_type == 'anchor' and exists(node, 'self::tei:milestone[@unit]'):
        prefix = node.get('unit')
    elif node_type == 'structural':
        if name == 'front':
            prefix = 'frontmatter'
        elif name == 'back':
            prefix = 'backmatter'
        elif exists(node, 'self::tei:text[@type = "work_volume"]'):
            prefix = 'vol'
    elif node_type == 'main':
        if exists(node, 'self::tei:head'):
            prefix = 'heading'
        elif exists(node, 'self::tei:titlePage'):
            prefix = 'titlepage'
    elif node_type == 'list':
        if exists(node, 'self::tei:list[@type = "dict" or @type = "index"]'):
            prefix = node.get('type')
        elif exists(node, 'self::tei:item[ancestor::tei:list[@type = "dict"]]'):
            prefix = 'entry'
    return prefix


def get_citetrail_infix(node:etree._Element, node_type:str):
    """
    Certain nodes contain an infix in their citetrail: a "name" that is derived from node-specific
    properties such as attributes. Such an infix is usually (but not necessarily) individual for the respective node.
    """
    infix = ''
    name = etree.QName(node).localname
    if node_type == 'marginal':
        if node.get('n'):
            infix = re.sub(r'([^a-zA-Z0-9]|[\[\]])', '', node.get('n')).upper()
    elif node_type == 'page':
        if node.get('n'):
            infix = re.sub(r'([^a-zA-Z0-9]|[\[\]])', '', node.get('n')).upper()
        else:
            infix = node.get('facs')[5:]
    elif name == 'item':
        # if the item contains a term, we use that for giving the item a "speaking" name
        terms = node.xpath('descendant::tei:term[@key]', namespaces=xml_ns)
        if terms:
            term = terms[0]
            if len(term.xpath('ancestor::tei:list', namespaces=xml_ns)) \
                    == len(node.xpath('ancestor::tei:list', namespaces=xml_ns)):
                infix = re.sub(r'[^a-zA-Z0-9]', '', term.get('key')).upper()
    return infix


def get_citable_parents_xml_id(node: etree._Element, node_type: str):
    """
    Gets the citetrail (not passagetrail!) parent of the node.
    """
    ancestors = node.xpath('ancestor::*')
    if node_type == 'marginal' or node_type == 'anchor':
        # marginals and anchors must not have p (or some other "main" node) as their citableParent
        for anc in ancestors:
            if is_structural_elem(anc):
                return get_xml_id(anc)
    elif node_type == 'page':
        # within front, back, and single volumes, citable parent resolves to one of those elements for avoiding
        # collisions with identically named pb in other parts
        for anc in ancestors:
            if exists(anc, 'self::tei:front or self::tei:back or self::tei:text[1][not(@xml:id = "completeWork" or @type = "work_part")]'):
                return get_xml_id(anc)
        # note: this makes pb for which "else" is true appear outside of any structural hierarchy
    else:
        for anc in ancestors:
            if get_elem_type(anc):
                return get_xml_id(anc)


# NODE TITLES


def get_node_title(node):
    name = etree.QName(node).localname
    xml_id = node.xpath('@xml:id', namespaces=xml_ns)[0]
    title = ''
    if name == 'div':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            title = '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            title = make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            title = make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n') and node.get('type'):
            title = node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            title = make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        elif exists(node, 'tei:list/tei:head'):
            title = make_teaser_from_element(node.xpath('tei:list/tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei_list/tei:label'):
            title = make_teaser_from_element(node.xpath('tei:list/tei:label[1]', namespaces=xml_ns)[0])
    elif name == 'item':
        #if exists(node, 'parent::tei:list[@type="dict"] and descendant::tei:term[1]/@key'):
        #    return '"' + node.xpath('descendant::tei:term[1]/@key')[0] + '"'
        #    # TODO this needs revision when we have really have such dict. lists
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            title = '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            title = make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            title = make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            title = node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"]'):
            title = make_teaser_from_element(
                node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"][1]', namespaces=xml_ns)[0])
    elif name == 'lg':
        if exists(node, 'tei:head'):
            title = make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        else:
            title = make_teaser_from_element(node)
    elif name == 'list':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            title = '"' + node.get('n') + '"'
        elif exists(node, 'tei:head'):
            title = make_teaser_from_element(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
        elif exists(node, 'tei:label'):
            title = make_teaser_from_element(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
        elif node.get('n'):
            title = node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            title = make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
    elif name == 'milestone':
        if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            title = '"' + node.get('n') + '"'
        elif node.get('n'):
            title = node.get('n')
        elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
            title = make_teaser_from_element(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
    elif name == 'note':
        if node.get('n'):
            title = '"' + node.get('n') + '"'
    elif name == 'pb':
        if node.get('n') and re.match(r'fol\.', node.get('n')):
            title = node.get('n')
        else:
            title = 'p. ' + node.get('n')
        # one could also prepend a 'Vol. ' prefix here in case of a multivolume work
    elif name == 'text':
        if node.get('type') == 'work_volume':
            title = node.get('n')
    elif name == 'head' or name == 'label' or name == 'p' or name == 'signed' or name == 'titlePart':
        title = make_teaser_from_element(node)
    return title


# TODO HTML title


def make_teaser_from_element(elem):
    normalized_text = normalize_space(re.sub(r'\{.*?\}', '', re.sub(r'\[.*?\]', '', txt_dispatch(elem, 'edit'))))
    if len(normalized_text) > config_teaser_length:
        shortened = normalize_space(normalized_text[:config_teaser_length])
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

    # General:
    # TODO: notes within lists?