from api.v1.works.analysis import extract_text_structure, enrich_index
from api.v1.works.html import html_dispatch
from api.v1.works.txt import txt_dispatch
from api.v1.xutils import xml_ns, flatten
from api.v1.works.config import WorkConfig
from api.v1.works.dts import make_resource_metadata
from lxml import etree
import json
import re


config = WorkConfig('', node_count=0) # TODO wid
#config = None # TODO: conflicts between multiple parallel calls to transform()?


def transform(wid, xml_data):
    root = etree.fromstring(xml_data)
    #validate(wid, root)

    # put some technical metadata from the teiHeader into config
    char_decl = root.xpath('descendant::tei:charDecl', namespaces=xml_ns)[0]
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

    resources = []
    for node in enriched_index.iter('sal_node'):
        fragment = {}
        dts_resource_metadata = make_resource_metadata(node, config)
        fragment.update(dts_resource_metadata)
        fragment['basic'] = False
        if node.get('basic') == 'true':
            fragment['basic'] = True
            node_id = node.get('id')
            tei_node = root.xpath('//*[@xml:id = "' + node_id + '"]', namespaces=xml_ns)[0]
            # TXT
            txt_edit = txt_dispatch(tei_node, 'edit')
            txt_orig = txt_dispatch(tei_node, 'orig')
            # HTML
            html_nodes = html_dispatch(tei_node) # this assumes that
            html = etree.tostring(html_nodes, encoding="UTF-8") # this assumes that there is exactly 1 html root
            content = {'txt_edit': txt_edit, 'txt_orig': txt_orig, 'html': str(html, encoding='UTF-8')}
            fragment.update(content)
            # TODO TEI
        resources.append(fragment)
    with open('tests/resources/out/' + wid + '_resources.json', 'w') as fo:
        fo.write(json.dumps(resources, indent=4))

