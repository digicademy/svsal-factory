from api.v1.works.analysis import WorkAnalysis
from api.v1.works.html import html_dispatch
from api.v1.works.txt import txt_dispatch
from api.v1.xutils import xml_ns, flatten, safe_xinclude, get_node_by_xmlid, make_dts_fragment_string, is_element, \
    get_xml_id, normalize_space, exists, copy_attributes
from api.v1.works.config import WorkConfig, tei_works_path
from api.v1.works.metadata import make_passage_metadata, make_resource_metadata
from api.v1.works.tei import wrap_tei_node_in_ancestors
from api.v1.errors import NodeIndexingError
from lxml import etree
import json
from copy import deepcopy
import re
import io


class WorkFactory:

    def __init__(self, config: WorkConfig):
        self.config = config
        self.analysis = WorkAnalysis()

    def make_structural_index(self, tei_text: etree._Element) -> etree._Element:
        """Creates an XML representation of the structure of a text, where relevant nodes are nested according
        to their original hierarchy and enriched with meta information.
        :param tei_root: the TEI root node of the document for which to create the index
        :return: the root node of the newly created index
        """
        struct_index_nodes = flatten(self.extract_structure(tei_text))
        struct_index = etree.Element('sal_index')
        for n in struct_index_nodes:
            struct_index.append(n)
        return struct_index

    def extract_structure(self, wid, node):
        if is_element(node):
            node_type = self.analysis.get_node_type(node)
            if get_xml_id(node) and node_type:
                sal_node = etree.Element('sal_node')
                name = etree.QName(node).localname

                # BASIC INFO
                sal_node.set('id', get_xml_id(node))
                sal_node.set('name', name)
                sal_node.set('type', node_type)
                is_basic = self.analysis.is_basic_node(node)
                if is_basic:
                    sal_node.set('basic', 'true')

                # CLASS & TYPE
                # @class is deprecated atm
                # node_class = get_node_class(node)
                # sal_node.set('class', etree.QName(node).localname)
                sal_node.set('citeType', self.analysis.get_cite_type(node, node_type))

                # NODE/SECTION TITLE
                title = 'placeholder'  # TODO
                sal_title = etree.Element('title')
                sal_title.text = title
                sal_node.append(sal_title)

                # CITETRAIL (preliminary and yet not concatenated with node parent's citetrail)
                preliminary_cite = normalize_space(self.analysis.get_citetrail_prefix(node, node_type)
                                                   + self.analysis.get_citetrail_infix(node, node_type))
                if preliminary_cite:
                    sal_node.set('cite', preliminary_cite)
                citetrail_ancestors = self.analysis.get_citable_ancestors(node, node_type, 'citetrail')
                citetrail_parent_id = None
                if citetrail_ancestors:
                    citetrail_parent_id = get_xml_id(citetrail_ancestors[0])
                if citetrail_parent_id:
                    sal_node.set('citetrailParent', citetrail_parent_id)

                # LEVEL
                level = len(citetrail_ancestors) + 1
                sal_node.set('level', str(level))  # TODO does this work with marginals and pages?
                from api.v1.works.factory import config
                if config.get_cite_depth() < level:
                    config.set_cite_depth(level)

                # PASSAGETRAIL (preliminary and not yet concatenated with parent's passagetrail)
                if self.analysis.is_passagetrail_node(node):
                    preliminary_passage = self.analysis.get_passagetrail(node, node_type)
                    sal_passage = etree.Element('passage')
                    sal_passage.text = preliminary_passage
                    sal_node.append(sal_passage)
                passagetrail_ancestors = self.analysis.get_citable_ancestors(node, node_type, 'passagetrail')
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

                # CHILD NODES
                children = list(flatten([self.extract_structure(wid, child) for child in node]))
                # TODO sal_title: note titles (as well as citetrails) need to be suffixed by their position / number
                if len(children) > 0:
                    sal_children = etree.Element('children')
                    for child in children:
                        if etree.iselement(child):
                            sal_children.append(child)
                        elif isinstance(child, list):
                            raise NodeIndexingError('Found list: ' + '; '.join(child) + ' instead of child::sal_node')
                    sal_node.append(sal_children)
                return sal_node
            else:
                return [self.extract_structure(wid, child) for child in node]
        else:
            pass

    # we need to query all *descendants*, not only children, for nodes referring to this node as parent; this
    # is due to specific nodes such as page and anchor nodes that do not refer to their immediate sal_node parent
    get_citable_children = etree.XPath('children/descendant::sal_node[@citetrailParent = $id]')  # TODO does this work?

    def enrich_index(self, sal_index):
        enriched_index = etree.Element('sal_index')
        node_count = 0
        for node in sal_index.iter('sal_node'):
            sal_node_id = node.get('id')
            # print('enrich_index: Processing node ' + sal_node_id)
            enriched_node = etree.Element('sal_node')
            copy_attributes(node, enriched_node)

            # POSITION of node
            enriched_node.set('n', str(node_count))
            node_count = node_count + 1

            # MEMBER (list of xml:id, separated by ';')
            citable_children = self.get_citable_children(node, id=sal_node_id) # TODO does this belong to analysis?
            if len(citable_children):
                member = []
                for m in citable_children:
                    member.append(m.get('id'))
                enriched_node.set('member', ';'.join(member))
                # TODO this makes paragraphs and pb/milestones "within" those paragraphs appear on the same level

            # PREV/NEXT NODES
            # we set prev/next only for structural and main nodes
            if node.get('type') in ('main', 'structural'):
                prev = node.xpath('preceding-sibling::sal_node[@type = "main" or @type = "structural"][1]')
                next = node.xpath('following-sibling::sal_node[@type = "main" or @type = "structural"][1]')
                # TODO this assumes that dts:next/prev should refer only to resources on the same level
                #  - or can 3.1's next refer to 4 if there is no 3.2?
                if len(prev):
                    enriched_node.set('prev', prev[0].get('id'))
                if len(next):
                    enriched_node.set('next', next[0].get('id'))

            # CITETRAIL
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
                # since iter() is depth-first, we can assume that the parent's full citetrail has already been registered
                parent_citetrail = self.config.get_citetrail_mapping(node.get('citetrailParent'))
                full_citetrail = parent_citetrail + '.' + revised_cite
                enriched_node.set('citetrailParent', parent_citetrail)  # overwrite old xml:id-based value
                enriched_node.set('citetrail', full_citetrail)
                self.config.put_citetrail_mapping(node.get('id'), full_citetrail)
            else:
                enriched_node.set('citetrail', revised_cite)
                self.config.put_citetrail_mapping(node.get('id'), revised_cite)

            # CRUMBTRAIL
            # TODO?

            # PASSAGETRAIL
            this_passage = node.xpath('passage/text()')
            revised_passage = ''
            if len(this_passage):
                revised_passage = str(this_passage[0])
                # print('revised_passage is: ' + revised_passage)
                # for div, milestones, and notes: determine passagetrail position based on preceding::sal_node with similar
                # passagetrails within *the same passagetrail section* (structure is more complicated than with citetrails,
                # since parent::sal_node is not necessarily a passagetrail "parent")
                position = ''
                if node.get('name') in ('div', 'milestone') or node.get('type') == 'note':
                    passagetrail_parent = None
                    if node.get('passagetrailParent'):
                        passagetrail_parent = \
                        node.xpath('ancestor::*[@id = "' + node.get('passagetrailParent') + '"][1]')[0]
                    else:
                        # if there is no passagetrail parent, take the sal_index root:
                        passagetrail_parent = node.xpath('ancestor::sal_index[1]')[0]
                    passagetrail_ancestors_n = node.get('passagetrailAncestorsN')
                    # using double quotes here as string markers for dealing with single/double quotes in passages
                    similar_xpath = "descendant::sal_node[@name = '" + node.get('name') + "'" \
                                    + " and ./passage/text() = '" + revised_passage + "'" \
                                    + " and @passagetrailAncestorsN = " \
                                    + "'" + passagetrail_ancestors_n + "']"
                    similar = passagetrail_parent.xpath(similar_xpath)
                    if len(similar) > 0:
                        similar_preceding = []
                        for s in similar:
                            if exists(s, 'following::sal_node[@id = "' + node.get('id') + '"]'):
                                similar_preceding.append(s)
                        position = str(len(similar_preceding) + 1)
                        revised_passage += ' [' + position + ']'
                        # TODO: using square brackets to indicate automatic numbering/"normalization" ?
            if node.get('passagetrailParent'):
                parent_passagetrail = self.config.get_passagetrail_mapping(node.get('passagetrailParent'))
                if revised_passage:
                    full_passagetrail = parent_passagetrail + ' ' + revised_passage
                    enriched_node.set('passagetrail', full_passagetrail)
                    self.config.put_passagetrail_mapping(node.get('id'), full_passagetrail)
                else:
                    enriched_node.set('passagetrail', parent_passagetrail)
                    self.config.put_passagetrail_mapping(node.get('id'), parent_passagetrail)
            else:
                enriched_node.set('passagetrail', revised_passage)
                self.config.put_passagetrail_mapping(node.get('id'), revised_passage)
                # if passage does not exist, we set an empty passagetrail

            # FINALIZATION
            enriched_index.append(enriched_node)
        return enriched_index

    def extract_toc(enriched_index: etree._Element):
        pass  # TODO

    def extract_pagination(enriched_index: etree._Element):
        pages = []
        for page_node in enriched_index.xpath('child::sal_node[@type = "page"]'):
            print('Citetrail=' + page_node.get('citetrail'))
            page_obj = {
                'dts:ref': page_node.get('citetrail'),
                'title': page_node.xpath('title/text()')[0]
            }
            pages.append(page_obj)
        return pages



def transform(wid: str, request_data):

    # 0.) get, parse, and expand the xml dataset
    parser = etree.XMLParser(attribute_defaults=False, no_network=False, ns_clean=True, remove_blank_text=False,
                             remove_comments=False, remove_pis=False, compact=False, collect_ids=True,
                             resolve_entities=False, huge_tree=False, encoding='UTF-8')  # huge_tree=True, ns_clean=False ?
    tree = etree.parse(tei_works_path + '/' + wid + '.xml', parser)  # TODO url
    tei_root = safe_xinclude(tree)
    tei_header = tei_root.xpath('tei:teiHeader', namespaces=xml_ns)[0]
    tei_text = tei_root.xpath('child::tei:text', namespaces=xml_ns)[0]

    # 1.) Setup
    config = WorkConfig(node_count=0)
    factory = WorkFactory(config)

    # TODO TEI validation

    # put some technical metadata from the teiHeader into config

    char_decl = tei_header.xpath('descendant::tei:charDecl', namespaces=xml_ns)[0]
    config.set_chars(char_decl)
    prefix_defs = tei_root.xpath('descendant::tei:prefixDef', namespaces=xml_ns)
    for pd in prefix_defs:
        config.set_prefix_def(pd)

    # 1.) INDEXING
    # a) extract the basic structure of the text (i.e., the hierarchy of all relevant nodes), also building
    # preliminary citetrails
    structural_index = factory.make_structural_index(tei_text)
    # for debugging:
    with open('tests/resources/out/' + wid + "_index0.xml", "wb") as fo:
        fo.write(etree.tostring(structural_index, pretty_print=True))
    # b) enrich index (e.g., make full citetrails), and flatten nodes
    enriched_index = factory.enrich_index(structural_index)
    # for debugging:
    with open('tests/resources/out/' + wid + "_index.xml", "wb") as fo:
        fo.write(etree.tostring(enriched_index, pretty_print=True))

    # 2.) TOC and PAGINATION
#    pages = extract_pagination(enriched_index)
#    with open('tests/resources/out/' + wid + '_pages.json', 'w') as fo:
#        fo.write(json.dumps(pages, indent=4))

    # 3.) PASSAGES
    passages = []
    for node in enriched_index.iter('sal_node'):
        fragment = {}
        dts_resource_metadata = make_passage_metadata(node, config)
        fragment.update(dts_resource_metadata)
        fragment['basic'] = False
        # for now, add txt, html etc. only if node is "basic"
        if node.get('basic') == 'true':
            fragment['basic'] = True
            node_id = node.get('id')
            # root.xpath('//*[@xml:id = "' + node_id + '"]', namespaces=xml_ns)[0]
            tei_node = get_node_by_xmlid(tei_root, xmlid=node_id)[0]
            # TXT
            txt_edit = make_dts_fragment_string(txt_dispatch(tei_node, 'edit'))
            txt_orig = make_dts_fragment_string(txt_dispatch(tei_node, 'orig'))
            # HTML
            html_node = html_dispatch(tei_node) # this assumes that there is exactly 1 html result node
            html = make_dts_fragment_string(html_node)
            # TEI
            tei_node_with_ancestors = wrap_tei_node_in_ancestors(tei_node, deepcopy(tei_node))
            tei = make_dts_fragment_string(tei_node_with_ancestors)
            # aggregate:
            content = {'txt_edit': str(txt_edit, encoding='UTF-8'),
                       'txt_orig': str(txt_orig, encoding='UTF-8'),
                       'html': str(html, encoding='UTF-8'),
                       'tei': str(tei, encoding='UTF-8')}
            fragment.update(content)
        passages.append(fragment)
    with open('tests/resources/out/' + wid + '_resources.json', 'w') as fo:
        fo.write(json.dumps(passages, indent=4))

    # 4.) WORK/VOLUME METADATA
    resource_metadata = make_resource_metadata(tei_header, config, wid)
    with open('tests/resources/out/' + wid + '_metadata.json', 'w') as fo:
        fo.write(json.dumps(resource_metadata, indent=4))
