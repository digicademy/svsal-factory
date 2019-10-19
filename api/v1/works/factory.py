from api.v1.works.analysis import extract_text_structure
from api.v1.works.html import html_dispatch
from api.v1.xutils import xml_ns, flatten
from lxml import etree


def transform(wid, xml_data):
    root = etree.fromstring(xml_data)
    #validate(wid, root)
    text = root.xpath('child::tei:text', namespaces=xml_ns)[0]
    #print(len(text))

    # INDEXING
    index_nodes = flatten(extract_text_structure(wid, text))
    index = etree.Element('sal_index')
    for n in index_nodes:
        index.append(n)
    index_str = etree.tostring(index, pretty_print=True)
    print(index_str[:100])
    with open('tests/resources/' + wid + "_index.xml", "wb") as fo:
        fo.write(index_str)


"""
    # HTML
    test_p = text.xpath('//*[@xml:id = "W0034-00-0003-pa-03eb"]', namespaces=xml_ns)[0]
    transformed = html_dispatch(test_p)
    print(etree.tostring(transformed))
"""

# TODO:
#   - extract_text_structure yields more sal_nodes for W0013 than current render.xql