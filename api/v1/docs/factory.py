from api.v1.docs.config import DocConfig, doc_id_filenames
from api.v1.xutils import safe_xinclude, flatten
from api.v1.errors import QueryValidationError
from api.v1.xutils import is_element, get_xml_id
from api.v1.errors import NodeIndexingError
from api.v1.docs.analysis import DocAnalysis, GuidelinesAnalysis
from api.v1.docs.html import DocHTMLTransformer, GuidelinesHTMLTransformer
from api.v1.docs.config import tei_docs_path
from lxml import etree
from abc import ABC, abstractmethod


class DocFactory(ABC):

    def __init__(self):
        self.config = DocConfig()
        self.analysis = DocAnalysis
        self.html_transformer = DocHTMLTransformer

    def make_structural_index(self, tei_root: etree._Element) -> etree.Element:
        """Creates an XML representation of the structure of a text, where relevant nodes are nested according
        to their original hierarchy and enriched with meta information.
        :param tei_root: the TEI root node of the document for which to create the index
        :return: the root node of the newly created index
        """
        struct_index_nodes = flatten(self.extract_structure(tei_root, self.analysis))
        struct_index = etree.Element('sal_index')
        for n in struct_index_nodes:
            struct_index.append(n)
        return struct_index

    def extract_structure(self, node: etree._Element, analysis: DocAnalysis):
        """
        Analyzes a TEI node, copies information relevant for indexing to a new sal_node element, and recursively
        analyzes all the descendants of the current node (appending relevant descendant sal_nodes to the current
        sal_node element.
        :param node: the TEI node to be analyzed (might be any type of node)
        :param config: the configuration object for the current factory event
        :param analysis: the node analysis object for the current factory event
        :return: either a sal_node element or None
        """
        if is_element(node):
            print('Node exists: ' + str(len(node)))
            print(node)
            node_type = analysis.get_node_type(node)
            if get_xml_id(node) and node_type:
                sal_node = etree.Element('sal_node')
                node_id = get_xml_id(node)

                # BASIC INFO
                sal_node.set('id', node_id)
                sal_node.set('type', node_type)
                is_basic = analysis.is_basic_node(node)
                if is_basic:
                    sal_node.set('basic', 'true')

                # TITLE
                title = analysis.make_title(node)
                sal_node.set('title', title)  # TODO as child rather than attr?

                # CITETRAIL
                citetrail = analysis.make_citetrail(node)
                self.config.put_citetrail_mapping(node_id, citetrail)
                sal_node.set('citetrail', citetrail)

                # LEVEL
                citetrail_ancestors = analysis.get_citetrail_ancestors(node)
                level = len(citetrail_ancestors) + 1
                sal_node.set('level', str(level))
                if self.config.get_cite_depth() < level:
                    self.config.set_cite_depth(level)

                # CHILD NODES
                children = list(flatten([self.extract_structure(child) for child in node]))
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
                return [self.extract_structure(child) for child in node]
        else:
            pass


class GuidelinesFactory(DocFactory):
    def __init__(self):
        self.config = DocConfig()
        self.analysis = GuidelinesAnalysis
        self.html_transformer = GuidelinesHTMLTransformer


def get_doc_factory(doc_id: str) -> DocFactory:
    if doc_id == 'guidelines':
        return GuidelinesFactory()
    else:
        return None


def transform(doc_id: str, request_data):

    # 1.) Fetch file
    filename = doc_id_filenames.get(doc_id)
    if not filename:
        raise QueryValidationError('Could not find matching file for doc_id ' + doc_id)

    # 2.) Setup (factory, parser, config, element tree, etc.)
    factory = get_doc_factory(doc_id)
    parser = etree.XMLParser(attribute_defaults=False, no_network=False, ns_clean=True, remove_blank_text=False,
                             remove_comments=False, remove_pis=False, compact=False, collect_ids=True,
                             resolve_entities=False, huge_tree=False,
                             encoding='UTF-8')  # huge_tree=True, ns_clean=False ?
    tree = etree.parse(tei_docs_path + '/' + filename + '.xml', parser)  # TODO url; requires that did = filename
    tei_root = safe_xinclude(tree)

    # 3.) Information Extraction
    # a) extract the structural "skeleton" of the text, including basic node information
    structural_index = factory.make_structural_index(tei_root)
    # output for debugging:
    index_str = etree.tostring(structural_index, pretty_print=True)
    with open('tests/resources/out/' + doc_id + "_index.xml", "wb") as fo:
        fo.write(index_str)




