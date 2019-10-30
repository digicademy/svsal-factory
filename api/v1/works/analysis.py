from lxml import etree
from api.v1.xutils import flatten, xml_ns, is_element, exists, get_xml_id, copy_attributes
from api.v1.works.txt import txt_dispatch, normalize_space
from api.v1.works.config import teaser_length as config_teaser_length
from api.v1.works.config import citation_labels
from api.v1.works.fragmentation import *
from api.v1.works.errors import NodeIndexingError, TEIMarkupError
import re


# STRUCTURAL ANALYSIS AND NODE INDEXING


def extract_text_structure(wid, node):
    if is_element(node):
        node_type = get_elem_type(node)
        if get_xml_id(node) and node_type:
            sal_node = etree.Element('sal_node')

            # BASIC INFO
            sal_node.set('id', get_xml_id(node))
            sal_node.set('name', etree.QName(node).localname)
            sal_node.set('type', node_type)
            is_basic = is_basic_elem(node)
            if is_basic:
                sal_node.set('basic', 'true')

            # CITETRAIL (preliminary and yet not concatenated with node parent's citetrail)
            preliminary_cite = normalize_space(get_citetrail_prefix(node, node_type) + get_citetrail_infix(node, node_type))
            if preliminary_cite:
                sal_node.set('cite', preliminary_cite)
            citetrail_ancestors = get_citable_ancestors(node, node_type, 'citetrail')
            citetrail_parent_id = None
            if citetrail_ancestors:
                citetrail_parent_id = get_xml_id(citetrail_ancestors[0])
            if citetrail_parent_id:
                sal_node.set('citetrailParent', citetrail_parent_id)

            # PASSAGETRAIL (preliminary and not yet concatenated with parent's passagetrail)
            preliminary_passage = get_passagetrail(node, node_type)
            if is_passagetrail_node(node):
                sal_node.set('passage', preliminary_passage)
            passagetrail_ancestors = get_citable_ancestors(node, node_type, 'passagetrail')
            passagetrail_parent_id = None
            if passagetrail_ancestors:
                passagetrail_parent_id = get_xml_id(passagetrail_ancestors[0])
            if passagetrail_parent_id:
                sal_node.set('passagetrailParent', passagetrail_parent_id)
            sal_node.set('passagetrailAncestorsN', str(len(passagetrail_ancestors)))

            # LIST (list nodes require some more information about their contexts)
            # TODO check if this works
            if is_basic and node_type == 'list':
                level = len(node.xpath('ancestor::tei:list', namespaces=xml_ns))
                sal_node.set('listLevel', str(level))
                if level > 0:
                    sal_node.set('listParent', node.xpath('ancestor::tei:list[1]/@xml:id', namespaces=xml_ns)[0])
                # TODO: use citetrail rather than xml:id of listParent
                # TODO: some information about the kind of list (get_list_type)? in items or list?

            # REMOVE:
            # DIV (add @type as @divType)
            #name = etree.QName(node).localname
            #if name == 'div':
            #    sal_node.set('divType', node.get('type'))

            # CHILD NODES
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


def enrich_index(sal_index):
    from api.v1.works.factory import config
    enriched_index = etree.Element('sal_index')
    for node in sal_index.iter('sal_node'):
        enriched_node = etree.Element('sal_node')
        copy_attributes(node, enriched_node)

        # CITETRAILS
        # determine citetrail position based on preceding-sibling::sal_node with similar @cite
        this_cite = node.get('cite')
        revised_cite = this_cite
        if this_cite:
            similar_preceding = len(node.xpath('preceding-sibling::sal_node[@cite = "' + this_cite + '"]'))
            similar_following = len(node.xpath('following-sibling::sal_node[@cite = "' + this_cite + '"]'))
            if similar_preceding > 0 or similar_following > 0:
                if re.match(r'\d$', this_cite):
                    # if cite ends with number, use '-' as separator (e.g., for preserving page numbers)
                    revised_cite += '-' + str(similar_preceding + 1)
                else:
                    revised_cite += str(similar_preceding + 1)
        else:
            # if node has no @cite[./string()], simply count similarly unnamed preceding siblings
            revised_cite = str(len(node.xpath('preceding-sibling::sal_node[not(@cite)]')) + 1)
        # construct full citetrail and put them into node and config.node_mappings
        if node.get('citetrailParent'):
            print('node id is ' + node.get('id'))
            print('parent_citetrail is ' + node.get('citetrailParent'))
            #print(config.get_node_mappings())
            # since iter() is depth-first, we can assume that the parent's full citetrail has already been registered
            parent_citetrail = config.get_citetrail_mapping(node.get('citetrailParent'))
            full_citetrail = parent_citetrail + '.' + revised_cite
            enriched_node.set('citetrail', full_citetrail)
            config.put_citetrail_mapping(node.get('id'), full_citetrail)
        else:
            enriched_node.set('citetrail', revised_cite)
            config.put_citetrail_mapping(node.get('id'), revised_cite)

        # PASSAGETRAILS
        this_passage = node.get('passagetrail')
        revised_passage = this_passage
        if this_passage:
            # for div, milestones, and notes: determine passagetrail position based on preceding::sal_node with similar
            # passagetrails within *the same passagetrail section* (structure is more complicated than with citetrails,
            # since parent::sal_node is not necessarily a passagetrail "parent")
            position = ''
            if node.get('name') in ('div', 'milestone') or node.get('type') == 'note':
                passagetrail_parent = None
                if node.get('passagetrailParent'):
                    passagetrail_parent = node.xpath('ancestor::*[@id = "' + node.get('passagetrailParent') + '"]')[0]
                else:
                    # if there is no passagetrail parent, take the sal_index root:
                    passagetrail_parent = node.xpath('ancestor::sal_index')
                passagetrail_ancestors_n = node.get('passagetrailAncestorsN')
                similar = passagetrail_parent.xpath('descendant::sal_node[@name = "' + node.get('name') + '"'
                                                              + ' and @passage = "' + this_passage + '"'
                                                              + ' and @passagetrailAncestorsN = '
                                                              + passagetrail_ancestors_n
                                                              + ']')
                if len(similar) > 0:
                    similar_preceding = []
                    for s in similar:
                        if exists('following::sal_node[@id = "' + node.get('id') + '"]'):
                            similar_preceding.append(s)
                    position = str(len(similar_preceding) + 1)
                    revised_passage += ' [' + position + ']'
                    # using square brackets to indicate automatic numbering/"normalization"
        if node.get('passagetrailParent'):
            parent_passagetrail = config.get_passagetrail_mapping(node.get('passagetrailParent'))
            print(config.get_node_mappings())
            if revised_passage:
                full_passagetrail = parent_passagetrail + ' ' + revised_passage
                enriched_node.set('passagetrail', full_passagetrail)
                config.put_passagetrail_mapping(node.get('id'), full_passagetrail)
            else:
                enriched_node.set('passagetrail', parent_passagetrail)
                config.put_passagetrail_mapping(node.get('id'), parent_passagetrail)
        # if neither passage nor passagetrailParent exists, we refrain from setting any attributes/mappings

        # FINALIZATION
        enriched_index.append(enriched_node)
        # make full-blown citetrails
    return enriched_index


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


def get_citable_ancestors(node: etree._Element, node_type: str, mode: str):
    """
    Gets all citetrail or passagetrail ancestors of a node (switch modes: 'citetrail' vs 'passagetrail').
    """
    tei_ancestors = node.xpath('ancestor::*')
    ancestors = []
    if node_type == 'marginal' or node_type == 'anchor':
        # marginals and anchors must not have p (or some other "main" node) as their parent
        for anc in tei_ancestors:
            if (mode == 'citetrail' or (mode == 'passagetrail' and is_passagetrail_node(anc))) \
                    and is_structural_elem(anc):
                ancestors.append(anc)
    elif node_type == 'page':
        # within front, back, and single volumes, citable parent resolves to one of those elements for avoiding
        # collisions with identically named pb in other parts
        for anc in tei_ancestors:
            if (mode == 'citetrail' or (mode == 'passagetrail' and is_passagetrail_node(anc))) \
                    and exists(anc, 'self::tei:front or self::tei:back'
                                    + ' or self::tei:text[1][not(@xml:id = "completeWork" or @type = "work_part")]'):
                ancestors.append(anc)
        # note: this makes all other pb appear outside of any structural hierarchy, but this should be fine
    else:
        for anc in tei_ancestors:
            if (mode == 'citetrail' or (mode == 'passagetrail' and is_passagetrail_node(anc))) and get_elem_type(anc):
                ancestors.append(anc)
    return ancestors


# PASSAGETRAIL UTIL FUNCTIONS


# gets a preliminary citetrail *part* (if any) for a specific node, not the whole citetrail
def get_passagetrail(node: etree._Element, node_type: str):
    passagetrail = ''
    if is_passagetrail_node(node):
        name = etree.QName(node).localname
        if name in ('back', 'front', 'titlePage'):
            passagetrail = citation_labels[name]['abbr']
        elif name == 'milestone':
            passagetrail = citation_labels[node.get('unit')]['abbr']
            if node.get('n') and re.match(r'^\[?\d+\]?$', node.get('n')):
                passagetrail += ' ' + node.get('n')
        elif name == 'div':
            div_type = node.get('type')
            passagetrail = citation_labels[div_type]['abbr']
            if div_type in ('lecture', 'gloss'):
                # abbr. + shortened version of the div node's title
                teaser = '"' + normalize_space(re.sub(r'"', '', get_node_title(node))[:15]) + '…"'
                passagetrail += ' ' + teaser
            else:
                if node.get('n') and re.match(r'^\[?\d+\]?$', node.get('n')):
                    passagetrail += ' ' + node.get('n')

                # trying to derive node position from div's siblings - deprecated, since we can do this better
                # from within sal_index
                """
                elif is_passagetrail_node(node.xpath('parent::*')[0]) or len(get_passagetrail_ancestors(node)) == 0:
                    # if the node's parent is a passagetrail node, or if there are no passagetrail ancestors
                    # at all, we can simply count similar preceding siblings (if required)
                    # first, count all similar preceding and following siblings to see if there are multiple such divs
                    # on the same level:
                    preceding_similar_siblings = []
                    for prec in node.xpath('preceding-sibling::tei:div[@type = "' + node.get('type') +'"]',
                                           namespaces=xml_ns):
                        if is_passagetrail_node(prec):
                            preceding_similar_siblings.append(prec)
                    following_similar_siblings = []
                    for foll in node.xpath('following-sibling::tei:div[@type = "' + node.get('type') + '"]',
                                           namespaces=xml_ns):
                        if is_passagetrail_node(foll):
                            following_similar_siblings.append(foll)
                    if (len(preceding_similar_siblings) + len(following_similar_siblings)) > 0:
                        position = '[' + str(len(preceding_similar_siblings) + 1) + ']'
                        # using "[]" to indicate automatic derivation of position
                else:
                    raise TEIMarkupError('tei:div neither has a numeric @n, nor could a position automatically be '
                                         'derived from the number of similar preceding siblings (there might be '
                                         'similar siblings above or below the preceding-sibling axis!)')
                if position:
                    return label + ' ' + position
                else:
                    return label
                """
        elif name == 'p':
            teaser = '"' + normalize_space(re.sub(r'"', '', make_teaser_from_element(node))[:15]) + '…"'
            passagetrail = citation_labels[name]['abbr'] + ' ' + teaser
        elif name == 'text':
            if node.get('type') == 'work_volume':
                passagetrail = 'vol. ' + node.get('n')
        elif node_type == 'marginal':
            passagetrail = citation_labels['note']['abbr']
            if node.get('n') and node.get('n'):
                passagetrail += ' "' + node.get('n') + '"'
        elif node_type == 'page':
            if node.get('n') and re.match(r'fol\.', node.get('n')):
                passagetrail = node.get('n')
            else:
                passagetrail = 'p. ' + node.get('n')
    return passagetrail


def is_passagetrail_node(node):
    """
    Determines if a node constitutes a 'passagetrail' part.
    Note: assumes that get_elem_type(node) == True.
    """
    name = etree.QName(node).localname
    return bool(exists(node, 'self::tei:text[@type = "work_volume"]') \
                or (exists(node, 'self::tei:div') and citation_labels[node.get('type')]['isCiteRef']) \
                or (exists(node, 'self::tei:milestone') and citation_labels[node.get('unit')]['isCiteRef']) \
                or exists(node, 'self::tei:pb[not(@sameAs or @corresp)]') \
                or (citation_labels.get(name) and citation_labels.get(name).get('isCiteRef')))


# TODO is this necessary?
#def get_passagetrail_ancestors(node):
#    ancestors = []
#    for anc in node.xpath('ancestor::*'):
#        if get_elem_type(anc) and is_passagetrail_node(anc):
#            ancestors.append(anc)
#    return ancestors


def get_preceding_passagetrail_siblings(node):
    precedings = []
    for prec in node.xpath('preceding-sibling::*'):
        if is_passagetrail_node(prec):
            precedings.append(prec)
    return precedings

# NODE TITLE UTIL FUNCTIONS


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