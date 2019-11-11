from lxml import etree
from api.v1.xutils import is_element, get_xml_id, xml_ns, flatten
from api.v1.docs.fragmentation import is_basic_elem, is_structural_elem
from api.v1.errors import NodeIndexingError


def extract_structure(node, config):
    if is_element(node):
        if get_xml_id(node) and is_structural_elem(node):
            sal_node = etree.Element('sal_node')
            node_id = get_xml_id(node)

            # BASIC INFO
            sal_node.set('id', node_id)
            #sal_node.set('name', etree.QName(node).localname)
            is_basic = is_basic_elem(node)
            if is_basic:
                sal_node.set('basic', 'true')

            # TITLE
            # TODO?

            # CITETRAIL (full)
            # for the docs we make purely numeric citetrails (e.g. 1.2.3), regardless of the respective node's content
            citetrail_preceding = [prec for prec in node.xpath('preceding-sibling::*') if is_structural_elem(prec)]
            citetrail_ancestors = [anc for anc in node.xpath('ancestor::*') if is_structural_elem(anc)]
            cite = str(len(citetrail_preceding) + 1)
            citetrail = cite
            if len(citetrail_ancestors):
                citetrail_parent = citetrail_ancestors[::-1][0] # TODO does this work?
                cp_citetrail = config.get_citetrail_mapping(get_xml_id(citetrail_parent))
                citetrail = cp_citetrail + '.' + cite
            config.put_citetrail_mapping(node_id, citetrail)

            # LEVEL
            level = len(citetrail_ancestors) + 1
            sal_node.set('level', str(level))
            if config.get_cite_depth() < level:
                config.set_cite_depth(level)

            # CHILD NODES
            children = list(flatten([extract_structure(child, config) for child in node]))
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
            return [extract_structure(child, config) for child in node]
    else:
        pass