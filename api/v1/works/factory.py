from api.v1.works.analysis import extract_text_structure
from api.v1.works.html import html_dispatch
from api.v1.works.txt import txt_dispatch
from api.v1.xutils import xml_ns, flatten
from api.v1.works.config import WorkConfig
from lxml import etree
import re


config = WorkConfig()


def transform(wid, xml_data):
    root = etree.fromstring(xml_data)
    #validate(wid, root)

    char_decl = root.xpath('descendant::tei:charDecl', namespaces=xml_ns)[0]
    config.set_chars(char_decl)

    text = root.xpath('child::tei:text', namespaces=xml_ns)[0]

    # INDEXING
    index_nodes = flatten(extract_text_structure(wid, text))
    index = etree.Element('sal_index')
    for n in index_nodes:
        index.append(n)
    index_str = etree.tostring(index, pretty_print=True)
    print(index_str[:100])
    with open('tests/resources/out/' + wid + "_index.xml", "wb") as fo:
        fo.write(index_str)

    # add txt, html etc., and flatten node index
    final_index = etree.Element('sal_index')
    n = 1
    for node in index.xpath('descendant::sal_node'): # TODO: does this maintain document order?
        node_id = node.get('id')
        #print('Processing node ' + node_id)
        tei_node = root.xpath('//*[@xml:id = "' + node_id + '"]', namespaces=xml_ns)[0]
        sal_node = etree.Element('sal_node')
        sal_node.set('id', node_id)
        sal_node.set('n', str(n)) # essential field for keeping track of order and positions of elements downstream
        # txt
        node_edit = txt_dispatch(tei_node, 'edit')
        node_orig = txt_dispatch(tei_node, 'orig')
        sal_txt_orig = etree.Element('sal_txt_orig')
        sal_txt_orig.text = node_orig
        sal_txt_edit = etree.Element('sal_txt_edit')
        sal_txt_edit.text = node_edit
        sal_node.append(sal_txt_orig)
        sal_node.append(sal_txt_edit)
        # html
        # TODO
        # out
        final_index.append(sal_node)
        n += 1

    final_index_str = etree.tostring(final_index, pretty_print=True, encoding="UTF-8")
    with open('tests/resources/out/' + wid + "_finalIndex.xml", "wb") as fo:
        fo.write(final_index_str)

    # HTML
    #test_p = text.xpath('//*[@xml:id = "W0034-00-0003-pa-03eb"]', namespaces=xml_ns)[0]
    #transformed = html_dispatch(test_p)
    #print(etree.tostring(transformed))

    #TXT
    #txt_orig = re.sub(r' {2,}', ' ', txt_dispatch(test_p, 'orig'))
    #txt_edit = re.sub(r' {2,}', ' ', ''.join(txt_dispatch(test_p, 'edit')))


# TODO:
#   - extract_text_structure yields more sal_nodes for W0013 than current render.xql