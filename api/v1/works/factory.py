from api.v1.works.analysis import extract_text_structure, enrich_index
from api.v1.works.html import html_dispatch
from api.v1.works.txt import txt_dispatch
from api.v1.xutils import xml_ns, flatten, safe_xinclude, get_node_by_xmlid, make_dts_fragment_string
from api.v1.works.config import WorkConfig, tei_works_path
from api.v1.works.metadata import make_passage_metadata, make_resource_metadata
from api.v1.works.tei import wrap_tei_node_in_ancestors
from lxml import etree
import json
from copy import deepcopy
import re
import io


config = WorkConfig('', node_count=0) # TODO wid


def transform(wid: str, request_data):

    # 0.) get, parse, and expand the xml dataset
    parser = etree.XMLParser(attribute_defaults=False, no_network=False, ns_clean=True, remove_blank_text=False,
                             remove_comments=False, remove_pis=False, compact=False, collect_ids=True,
                             resolve_entities=False, huge_tree=False, encoding='UTF-8')  # huge_tree=True, ns_clean=False ?
    tree = etree.parse(tei_works_path + '/' + wid + '.xml', parser)  # TODO url
    root = safe_xinclude(tree)

    # TODO TEI validation

    # put some technical metadata from the teiHeader into the config object
    tei_header = root.xpath('tei:teiHeader', namespaces=xml_ns)[0]
    char_decl = tei_header.xpath('descendant::tei:charDecl', namespaces=xml_ns)[0]
    config.set_chars(char_decl)
    prefix_defs = root.xpath('descendant::tei:prefixDef', namespaces=xml_ns)
    for pd in prefix_defs:
        config.set_prefix_def(pd)
    text = root.xpath('child::tei:text', namespaces=xml_ns)[0]

    # 1. INDEXING
    # a) extract the basic structure of the text (i.e., the hierarchy of all relevant nodes), also building
    # preliminary citetrails
    index_nodes0 = flatten(extract_text_structure(wid, text))
    index0 = etree.Element('sal_index')
    for n in index_nodes0:
        index0.append(n)
    index0_str = etree.tostring(index0, pretty_print=True)
    with open('tests/resources/out/' + wid + "_index0.xml", "wb") as fo:
        fo.write(index0_str)
    # b) make full citetrails
    enriched_index = enrich_index(index0)
    index_str = etree.tostring(enriched_index, pretty_print=True)
    with open('tests/resources/out/' + wid + "_index.xml", "wb") as fo:
        fo.write(index_str)

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
            tei_node = get_node_by_xmlid(root, xmlid=node_id)[0]
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

    resource_metadata = make_resource_metadata(tei_header, config, wid)
    with open('tests/resources/out/' + wid + '_metadata.json', 'w') as fo:
        fo.write(json.dumps(resource_metadata, indent=4))
