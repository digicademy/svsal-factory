from api.v1.docs.config import DocConfig, doc_id_filenames
from api.v1.docs.analysis import extract_structure
from api.v1.xutils import safe_xinclude, flatten
from api.v1.errors import QueryValidationError
from lxml import etree


def transform(doc_id: str):
    filename = doc_id_filenames.get(doc_id)
    if not filename:
        raise QueryValidationError('Could not find matching file for doc_id ' + doc_id)
    config = DocConfig(doc_id, node_count=0)

    parser = etree.XMLParser(attribute_defaults=False, no_network=False, ns_clean=True, remove_blank_text=False,
                             remove_comments=False, remove_pis=False, compact=False, collect_ids=True,
                             resolve_entities=False, huge_tree=False,
                             encoding='UTF-8')  # huge_tree=True, ns_clean=False ?
    tree = etree.parse(config.tei_docs_path + '/' + filename + '.xml', parser)  # TODO url; requires that did = filename
    root = safe_xinclude(tree)

    # 1. INDEXING
    # a) extract the basic structure of the text (i.e., the hierarchy of all relevant nodes), also building
    # preliminary citetrails
    index_nodes = flatten(extract_structure(root, config))
    index = etree.Element('sal_index')
    for n in index_nodes:
        index.append(n)
    index_str = etree.tostring(index, pretty_print=True)
    with open('tests/resources/out/' + doc_id + "_index.xml", "wb") as fo:
        fo.write(index_str)

