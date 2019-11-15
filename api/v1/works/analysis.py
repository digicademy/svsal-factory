from api.v1.xutils import flatten, is_element, exists, get_xml_id, copy_attributes, xml_ns, normalize_space
from api.v1.works.txt import txt_dispatch
from api.v1.works.config import teaser_length as config_teaser_length, citation_labels
from api.v1.works.fragmentation import *
from api.v1.errors import NodeIndexingError
from api.v1.works.config import WorkConfig
from lxml import etree
import re


class WorkAnalysis:

    def __init__(self, config: WorkConfig):
        self.config = config

    # NODE DEFINITIONS:

    __structural_node_def = \
        """
        (
            self::tei:div[@type != "work_part"] or
            self::tei:back or 
            self::tei:front or 
            self::tei:text[@type = "work_volume"] 
        ) and ancestor::tei:text
        """
    __main_node_def = \
        """
        boolean( 
            self::tei:p or  
            self::tei:signed or  
            self::tei:head[not(ancestor::tei:list)] or  
            self::tei:titlePage or  
            self::tei:lg or  
            self::tei:label[@place != "margin"] or  
            self::tei:argument[not(ancestor::tei:list)] or  
            self::tei:table
        )
        """
    __marginal_node_def = \
        """
        boolean(
            self::tei:note[@place = "margin"] or 
            self::tei:label[@place = "margin"] 
        )
        """
    __page_node_def = \
        """
        boolean(
            self::tei:pb[not(@sameAs or @corresp)]
        )
        """
    __anchor_node_def = \
        """
        boolean(
            self::tei:milestone[@unit != "other"]
        )
        """  # TODO: inline labels as anchors?
    __list_node_def = \
        """
        boolean(
            self::tei:list or 
            self::tei:item or 
            self::tei:head[ancestor::tei:list] or 
            self::tei:argument[ancestor::tei:list]
        )
        """
    # TODO: exclude 'simple' lists / items?
    __is_structural_node_xpath = etree.XPath(__structural_node_def, namespaces=xml_ns)
    __main_ancestors_def = 'not(ancestor::*[' + __main_node_def + ' or ' + __marginal_node_def + ' or ' \
                           + __list_node_def + '])'
    __is_main_node_xpath = etree.XPath(__main_node_def + ' and ' + __main_ancestors_def, namespaces=xml_ns)
    __is_marginal_node_xpath = etree.XPath(__marginal_node_def, namespaces=xml_ns)
    __is_anchor_node_xpath = etree.XPath(__anchor_node_def, namespaces=xml_ns)
    __is_page_node_xpath = etree.XPath(__page_node_def, namespaces=xml_ns)
    __list_ancestors_def = 'not(ancestor::*[' + __main_node_def + ' or ' + __marginal_node_def + '])'
    __is_list_node_xpath = etree.XPath(__list_node_def + ' and ' + __list_ancestors_def, namespaces=xml_ns)

    def is_structural_node(self, node: etree._Element) -> bool:
        return self.__is_structural_node_xpath(node)

    def is_main_node(self, node: etree._Element) -> bool:
        return self.__is_main_node_xpath(node)

    def is_marginal_node(self, node: etree._Element) -> bool:
        return self.__is_marginal_node_xpath(node)

    def is_anchor_node(self, node: etree._Element):
        return self.__is_anchor_node_xpath(node)

    def is_page_node(self, node: etree._Element):
        return self.__is_page_node_xpath(node)

    def is_list_node(self, node):
        return self.__is_list_node_xpath(node)

    def get_node_type(self, node: etree._Element) -> str:
        """
        Determines the type of an indexable element. Works as a general check for indexability of a node: If the
        node is not indexable, the empty string is returned.
        """
        if self.is_structural_node(node):
            return 'structural'
        elif self.is_main_node(node):
            return 'main'
        elif self.is_marginal_node(node):
            return 'marginal'
        elif self.is_page_node(node):
            return 'page'
        elif self.is_anchor_node(node):
            return 'anchor'
        elif self.is_list_node(node):
            return 'list'
        else:
            return ''

    __basic_list_node_def = \
        """
        boolean(
            (self::tei:item or self::tei:head or self::tei:argument) and not(descendant::tei:list)
        )
        """  # read as: items, arguments, and heads that do not contain lists (= lowest level list elements)
    # TODO perhaps we can simplify this as "lowest-level" mixed content elements in lists?

    # TODO extend element types (are there other elems than item, argument and head?)
    __is_basic_list_node_xpath = etree.XPath(__list_node_def + ' and ' + __list_ancestors_def
                                             + ' and ' + __basic_list_node_def
                                             + ' and not(ancestor::*[' + __basic_list_node_def + '])',
                                             namespaces=xml_ns)
    # TODO verify that this reaches all text nodes in lists, without duplicates

    # old, much more complicated version:
    # basic_list_elem_xpath = \
    # boolean(
    #    (self::tei:item and not(descendant::tei:list))
    #    or
    #    ((self::tei:argument or self::tei:head or self::tei:p)
    #        and not(ancestor::*[self::tei:item and not(descendant::tei:list)])
    #        and not(ancestor::*[self::tei:argument or self::tei:head or self::tei:p]))
    # )
    # read as: 'items that do not contain lists, or other elements such as argument, head (add more elements there if
    # necessary!) that do not occur within such items'
    # is_basic_list_elem = etree.XPath(basic_list_elem_xpath, namespaces=xml_ns)

    def is_basic_list_node(self, node: etree._Element) -> bool:
        return self.__is_basic_list_node_xpath(node)

    def is_basic_node(self, node: etree._Element) -> bool:
        return self.is_main_node(node) or self.is_marginal_node(node) or self.is_basic_list_node(node)

    def has_basic_ancestor(self, node):
        basic_ancestor = False
        for anc in node.xpath('ancestor::*'):
            if self.is_basic_node(anc):
                basic_ancestor = True
        return basic_ancestor
        # TODO formulate this as a single xpath for increasing performance

    # CITETRAILS:

    def get_citetrail_prefix(self, node: etree._Element, node_type: str):
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

    def get_citetrail_infix(self, node:etree._Element, node_type:str):
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

    def get_citable_ancestors(self, node: etree._Element, node_type: str, mode: str):
        """
        Gets all citetrail or passagetrail ancestors of a node (switch modes: 'citetrail' vs 'passagetrail').
        """
        tei_ancestors = node.xpath('ancestor::*')
        ancestors = []
        if node_type == 'marginal' or node_type == 'anchor':
            # marginals and anchors must not have p (or some other "main" node) as their parent
            for anc in tei_ancestors:
                if (mode == 'citetrail' or (mode == 'passagetrail' and self.is_passagetrail_node(anc))) \
                        and self.is_structural_node(anc):
                    ancestors.append(anc)
        elif node_type == 'page':
            # within front, back, and single volumes, citable parent resolves to one of those elements for avoiding
            # collisions with identically named pb in other parts
            for anc in tei_ancestors:
                if (mode == 'citetrail' or (mode == 'passagetrail' and self.is_passagetrail_node(anc))) \
                        and exists(anc, 'self::tei:front or self::tei:back'
                                        + ' or self::tei:text[1][not(@xml:id = "completeWork" or @type = "work_part")]'):
                    ancestors.append(anc)
            # note: this makes all other pb appear outside of any structural hierarchy, but this should be fine
        else:
            for anc in tei_ancestors:
                if (mode == 'citetrail' or (mode == 'passagetrail' and self.is_passagetrail_node(anc))) \
                        and self.get_node_type(anc):
                    ancestors.append(anc)
        return ancestors[::-1] # ancestors.reverse() is not working here

    # PASSAGETRAILS:

    # gets a preliminary citetrail *part* (if any) for a specific node, not the whole citetrail
    def get_passagetrail(self, node: etree._Element, node_type: str):
        passagetrail = ''
        if self.is_passagetrail_node(node):
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
                    teaser = '"' + normalize_space(re.sub(r'"', '', self.get_node_title(node))[:15]) + '…"'
                    passagetrail += ' ' + teaser
                else:
                    if node.get('n') and re.match(r'^\[?\d+\]?$', node.get('n')):
                        passagetrail += ' ' + node.get('n')
            elif name == 'p':
                teaser = '"' + normalize_space(re.sub(r'"', '', self.make_node_teaser(node))[:15]) + '…"'
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

    def is_passagetrail_node(self, node):
        """
        Determines if a node constitutes a 'passagetrail' part.
        Note: assumes that get_elem_type(node) == True.
        """
        name = etree.QName(node).localname
        return bool(exists(node, 'self::tei:text[@type = "work_volume"]') \
                    or (exists(node, 'self::tei:div') and citation_labels[node.get('type')].get('isCiteRef')) \
                    or (exists(node, 'self::tei:milestone') and citation_labels[node.get('unit')].get('isCiteRef')) \
                    or exists(node, 'self::tei:pb[not(@sameAs or @corresp)]') \
                    or (citation_labels.get(name) and citation_labels.get(name).get('isCiteRef')))

    # TITLE, CLASS, TYPE:

    def get_cite_type(self, node: etree._Element, node_type: str) -> str:
        """
        Makes a dts:citeType string from a given element node.
        (Note: the string values are really made up, perhaps a better alternative would be standardized classes
        from RDF / ontologies.)
        :param node: the element node for which to derive a citation type
        :param node_type: the type of the node, as derived through get_elem_type()
        :return: the string value for dts:citeType
        """
        name = etree.QName(node).localname
        cite_type = 'section'
        if name == 'div':
            cite_type = citation_labels.get(node.get('type')).get('full')
        elif name == 'milestone':
            cite_type = citation_labels.get(node.get('unit')).get('full')
        elif node_type == 'main':
            if name == 'head':
                cite_type = 'heading'
            else:
                cite_type = 'paragraph'
        elif node_type == 'page':
            cite_type = 'page'
        elif node_type == 'marginal':
            cite_type = 'note'
        elif node_type == 'list':
            if name == 'list':
                cite_type = 'list'
            else:
                cite_type = 'item'  # TODO also includes head etc.
        elif citation_labels.get(name):
            cite_type = citation_labels.get(name).get('full')
        return cite_type

    def get_node_class(self, node):
        name = etree.QName(node).localname
        node_class = name
        if name == 'div':
            node_class += '-' + node.get('type')
        elif name == 'milestone':
            node_class += '-' + node.get('unit')
        elif name == 'text':
            if node.get('type') == 'work_volume':
                name += '-' + node.get('type')
            elif get_xml_id(node) == 'completeWork':
                name += '-complete_work'
        return node_class

    def get_node_title(self, node):
        name = etree.QName(node).localname
        xml_id = node.xpath('@xml:id', namespaces=xml_ns)[0]
        title = ''
        if name == 'div':
            if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
                title = '"' + node.get('n') + '"'
            elif exists(node, 'tei:head'):
                title = self.make_node_teaser(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
            elif exists(node, 'tei:label'):
                title = self.make_node_teaser(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
            elif node.get('n') and node.get('type'):
                title = node.get('n')
            elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"]'):
                title = self.make_node_teaser(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id
                                                            + '"][1]')[0])
            elif exists(node, 'tei:list/tei:head'):
                title = self.make_node_teaser(node.xpath('tei:list/tei:head[1]', namespaces=xml_ns)[0])
            elif exists(node, 'tei_list/tei:label'):
                title = self.make_node_teaser(node.xpath('tei:list/tei:label[1]', namespaces=xml_ns)[0])
        elif name == 'item':
            #if exists(node, 'parent::tei:list[@type="dict"] and descendant::tei:term[1]/@key'):
            #    return '"' + node.xpath('descendant::tei:term[1]/@key')[0] + '"'
            #    # TODO this needs revision when we have really have such dict. lists
            if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
                title = '"' + node.get('n') + '"'
            elif exists(node, 'tei:head'):
                title = self.make_node_teaser(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
            elif exists(node, 'tei:label'):
                title = self.make_node_teaser(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
            elif node.get('n'):
                title = node.get('n')
            elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"]'):
                title = self.make_node_teaser(
                    node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#' + xml_id + '"][1]', namespaces=xml_ns)[0])
        elif name == 'lg':
            if exists(node, 'tei:head'):
                title = self.make_node_teaser(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
            else:
                title = self.make_node_teaser(node)
        elif name == 'list':
            if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
                title = '"' + node.get('n') + '"'
            elif exists(node, 'tei:head'):
                title = self.make_node_teaser(node.xpath('tei:head[1]', namespaces=xml_ns)[0])
            elif exists(node, 'tei:label'):
                title = self.make_node_teaser(node.xpath('tei:label[1]', namespaces=xml_ns)[0])
            elif node.get('n'):
                title = node.get('n')
            elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
                title = self.make_node_teaser(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
        elif name == 'milestone':
            if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
                title = '"' + node.get('n') + '"'
            elif node.get('n'):
                title = node.get('n')
            elif exists(node, 'ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"]'):
                title = self.make_node_teaser(node.xpath('ancestor::tei:TEI//tei:text//tei:ref[@target = "#'+ xml_id +'"][1]')[0])
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
            title = self.make_node_teaser(node)
        return title

    def make_node_teaser(self, elem):
        normalized_text = normalize_space(re.sub(r'\{.*?\}', '', re.sub(r'\[.*?\]', '', txt_dispatch(elem, 'edit'))))
        if len(normalized_text) > config_teaser_length:
            shortened = normalize_space(normalized_text[:config_teaser_length])
            return '"' + shortened + '…"'
        else:
            return '"' + normalized_text + '"'

    """
    TODOs:
        - HTML title
    """
