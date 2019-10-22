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
    # for debugging:
    with open('tests/resources/' + wid + "_index.xml", "wb") as fo:
        fo.write(index_str)


    # HTML
    test_p = text.xpath('//*[@xml:id = "W0034-00-0003-pa-03eb"]', namespaces=xml_ns)[0]
    transformed = html_dispatch(test_p)
    print(etree.tostring(transformed))

    #TXT
    txt_orig = re.sub(r' {2,}', ' ', txt_dispatch(test_p, 'orig'))
    txt_edit = re.sub(r' {2,}', ' ', ''.join(txt_dispatch(test_p, 'edit')))


# TODO:
#   - extract_text_structure yields more sal_nodes for W0013 than current render.xql