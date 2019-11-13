from lxml import etree
from api.v1.xutils import is_element, get_xml_id, xml_ns, flatten
from abc import ABC, abstractmethod

"""
Groups functionality for analyzing node types and making citetrails and other metadata into classes (for each doc type).
"""

class DocAnalysis(ABC):

    # NODE TYPES:
    # in docs, there are generally 2 types of nodes: structural and basic nodes

    @abstractmethod
    def is_structural_node(self, node: etree.Element) -> bool:
        """
        Determines whether a node defines a structural section that contains other structural and/or basic nodes.
        :param node: the node to be determined
        :return: bool indicating whether the node is structural
        """
        pass

    @abstractmethod
    def is_basic_node(self, node: etree.Element) -> bool:
        """
        Determines whether a node defines a basic text unit (such as a paragraph or a heading) that is not to be
        further nested.
        :param node: the node to be determined
        :return: bool indicating whether the node is basic
        """
        pass

    def get_node_type(self, node: etree.Element) -> str:
        """
        Gets the type of the node, expressed as a string. If the node is not relevant for doc indexing, the empty
        string is returned.
        :param node: the node to get the type for
        :return: one of 'basic', 'structural', or the empty string ''
        """
        if self.is_structural_node(node):
            return 'structural'
        elif self.is_basic_node(node):
            return 'basic'
        else:
            return ''

    # TITLE

    @abstractmethod
    def make_title(self, node: etree.Element) -> str:
        """
        Makes the title for a node, based on its metadata (attributes) and/or content nodes (headings, etc.).
        :return: the title
        """
        pass

    # CITETRAILS:

    @abstractmethod
    def make_citetrail(self, node: etree._Element):
        pass

    @abstractmethod
    def get_citetrail_ancestors(self, node: etree._Element):
        pass


class GuidelinesAnalysis(DocAnalysis):

    structural_node_def = \
        """
        self::tei:div
        """
    basic_node_def = \
        """
        (
        self::tei:p or
        self::tei:head or
        self::tei:list
        ) and not(ancestor::*[
            self::tei:p or
            self::tei:head or
            self::tei:list
            ]
        )
        """

    is_structural_node_xpath = etree.XPath(structural_node_def, namespaces=xml_ns)
    is_basic_node_xpath = etree.XPath(basic_node_def, namespaces=xml_ns)

    def is_structural_node(self, node: etree._Element) -> bool:
        """
        Wrapper function for is_structural_node_xpath, which determines whether a node is structural.
        :param node: the node to be analyzed
        :return: a bool indicating whether the node is structural
        """
        return self.is_structural_elem(node)

    def is_basic_node(self, node: etree._Element) -> bool:
        """
        Wrapper function for is_basic_node_xpath, which determines whether a node is basic.
        :param node: the node to be analyzed
        :return: a bool indicating whether the node is basic
        """
        return self.is_basic_node(node)

    def make_title(self, node: etree._Element) -> str:
        return 'placeholder'  # TODO

    def make_citetrail(self, node: etree._Element):
        node_id = node.get('id')
        citetrail_preceding = [prec for prec in node.xpath('preceding-sibling::*') if self.get_node_type(prec)]
        citetrail_ancestors = [anc for anc in node.xpath('ancestor::*') if self.get_node_type(anc)]
        cite = str(len(citetrail_preceding) + 1)
        citetrail = cite
        if len(citetrail_ancestors):
            citetrail_parent = citetrail_ancestors[::-1][0]  # TODO does this work?
            cp_citetrail = self.config.get_citetrail_mapping(get_xml_id(citetrail_parent))
            citetrail = cp_citetrail + '.' + cite
        return citetrail

    def get_citetrail_ancestors(self, node: etree._Element):
        return list([anc for anc in node.xpath('ancestor::*') if self.is_structural_node(anc)])[::-1]
        # revert list so that ancestors are positioned relative to current node
