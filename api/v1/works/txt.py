from lxml import etree
import re
from api.v1.xutils import flatten, is_element, exists, get_xml_id, is_text_node
from api.v1.errors import TEIUnkownElementError
from api.v1.works.config import WorkConfig, tei_text_elements
from api.v1.works.analysis import WorkAnalysis

import api.v1.works.factory as factory


class WorkTXTTransformer:

    def __init__(self, config: WorkConfig, analysis: WorkAnalysis):
        self.config = config
        self.analysis = analysis

    def dispatch(self, node, mode):
        if is_element(node):
            # check whether there is a specific transformation function defined for the element type - if not,
            # we pass the node through
            elem_function = getattr(self, 'transform_' + etree.QName(node).localname.lower(), None)
            if callable(elem_function):
                return elem_function(node)  # globals()[etree.QName(node).localname.lower()](node)
            elif etree.QName(node).localname in tei_text_elements:
                return self.passthru(node, mode)
            else:
                raise TEIUnkownElementError('Unknown element: ' + etree.QName(node).localname)
        elif is_text_node(node):
            return self.transform_text_node(node)
        else:
            return ''
        # omit comments and processing instructions

    def passthru(self, node, mode):
        if len(node.xpath('node()')) > 0:
            children = []
            for child in node.xpath('node()'):
                if is_element(child):
                    if self.analysis.is_basic_node(child) and self.analysis.is_marginal_node(child):
                        id = get_xml_id(child)
                        children.append('{%note:' + id + '%}')
                        # placeholder for marginal note in main text: those must be reinserted later if necessary
                        # TODO: use citetrail rather than xml:id? make sure that placeholders are excluded from searching/indexing
                    elif not self.analysis.is_structural_node(child):
                        # makes sure that structural elements yield only headings, not their nested content
                        children.append(self.dispatch(child, mode))
                else:
                    children.append(self.dispatch(child, mode))
            return ''.join(list(flatten(children)))
        else:
            return ''

    def transform_text_node(self, node, mode):
        return re.sub(r'\s+', ' ', str(node))

    # ELEMENT FUNCTIONS

    def transform_abbr(self, node, mode):
        return self.transform_orig_elem(node, mode)

    def transform_bibl(self, node, mode):
        if mode == 'edit' and exists(node, '@sortKey'):
            text = self.passthru(node, mode)
            return text + ' [' + re.sub(r'_', ', ', node.get('sortKey')) + ']' # TODO revision of bibl/@sortKey
        else:
            return self.passthru(node, mode)

    def transform_byline(self, node, mode):
        return self.passthru(node, mode) + '\n'

    def transform_cb(self, node, mode):
        if not node.get('break') == 'no':
            return ' '

    def transform_corr(self, node, mode):
        return self.transform_edit_elem(node, mode)

    def transform_div(self, node, mode): # nr
        # in txt, div can maximally yield a label; the processing of its children happens on the self.analysis.is_basic_nodeent level
        if mode == 'edit'and node.get('n') and not re.match(r'^[\[\]\d]+$]', node.get('n')): # if @n is more than a mere number
            return '\n[ *' + node.get('n') + '* ]\n'
        else:
            return '\n'

    def transform_doctitle(self, node, mode):
        return self.passthru(node, mode) + '\n'

    def transform_expan(self, node, mode):
        return self.transform_edit_elem(node, mode)

    def transform_figure(self, node, mode):
        return ''

    def transform_g(self, node, mode):
        char = factory.config.get_chars()[node.get('ref')[1:]]
        if mode == 'orig':
            if char.get('precomposed'):
                return char['precomposed']
            elif char.get('composed'):
                return char['composed']
            else:
                return char['standardized']
        else: # mode == 'edit'
            if node.get('ref')[1:] in ('char017f', 'char0292'):
                if node.text in (char.get('precomposed'), char.get('composed')):
                    return char['standardized']
                else:
                    return self.passthru(node, mode)
            else:
                return self.passthru(node, mode)

    def transform_gap(self, node, mode):
        return ''

    def transform_imprint(self, node, mode):
        return self.passthru(node, mode) + '\n'

    def transform_item(self, node, mode): # TODO test this, esp. with more complicated/nested lists
        text = ''
        if self.analysis.is_basic_node(node) or self.analysis.has_basic_ancestor(node):
            text = self.passthru(node, mode)
        leading = '- '
        if exists(node, 'parent::tei:list/@type = "numbered"'):
            leading = '# '
        elif exists(node, 'parent::tei:list/@type = "simple"'):
            leading = ' '
        return leading + text + '\n'

    def transform_label(self, node, mode):
        text = self.passthru(node, mode)
        if node.get('place') == 'margin':
            return '{\n\t' + text + '\n}' # TODO separate notes from surrounding text rather during final txt serialization?
        else:
            return text

    def transform_l(self, node, mode):
        return self.passthru(node, mode) + '\n'

    def transform_lb(self, node, mode):
        if not node.get('break') == 'no':
            return ' '

    def transform_list(self, node, mode): #nr
        # in txt, div can maximally yield a label; the processing of its descendants happens on the self.analysis.is_basic_nodeent level
        if mode == 'edit' and node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
            return '\n[*' + node.get('n') + '*]\n'
        else:
            return '\n'

    def transform_lg(self, node, mode):
        return '\n' + self.passthru(node, mode)

    def transform_milestone(self, node, mode):
        if mode == 'orig':
            if node.get('rendition') == '#dagger':
                return '†'
            elif node.get('rendition') == '#asterisk':
                return '*'
            else:
                return '[*]'
        else: # mode == 'edit'
            if node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')): # @n is not a number
                return '[' + node.get('n') + ']'
            elif node.get('n') and factory.config.get_citation_labels()[node.get('unit')]['abbr']: # @n is a number
                return '[' + factory.config.get_citation_labels()[node.get('unit')]['abbr'] + ' ' + node.get('n') + ']'
            else:
                return '[*]'

    def transform_name(self, node, mode):
        text = self.passthru(node, mode)
        if mode == 'edit' and node.get('key') and node.get('ref'):
            return text + ' [' + node.get('key') + '/' + node.get('ref') + ']'
        elif mode == 'edit' and (node.get('key') or node.get('ref')):
            return text + ' [' + '/'.join([a for a in (node.get('key'), node.get('ref')) if a is not None]) + ']'
        else:
            return text

    def transform_note(self, node, mode):
        text = self.passthru(node, mode)
        return '{\n\t' + text + '\n}' # TODO separate notes from surrounding text rather during final txt serialization?

    def transform_orig(self, node, mode):
        return self.transform_orig_elem(node, mode)

    def transform_p(self, node, mode):
        text = self.passthru(node, mode)
        if exists(node, 'ancestor::tei:note'):
            if exists(node, 'following-sibling::tei:p'):
                return text + '\n'
            else:
                return text
        else:
            return '\n' + text + '\n'

    def transform_pb(self, node, mode):
        if not node.get('break') == 'no':
            return ' '

    def transform_persname(self, node, mode):
        key = node.get('key')
        ref = node.get('ref')
        if mode == 'edit' and (key or ref):
            if key and ref:
                return key + ' [' + ref + ']'
            elif key:
                return key
            else:
                return '[' + ref + ']'
        else:
            return self.passthru(node, mode)

    def transform_placename(self, node, mode):
        if mode == 'edit' and node.get('key'):
            return self.passthru(node, mode) + '[' + node.get('key') + ']'
        else:
            return self.passthru(node, mode)

    def transform_publisher(self, node, mode):
        return self.transform_persname(node, mode)

    def transform_pubplace(self, node, mode):
        return self.transform_placename(node, mode)

    def transform_quote(self, node, mode):
        return '"' + self.passthru(node, mode) + '"'

    def transform_reg(self, node, mode):
        return self.transform_edit_elem(node, mode)

    def transform_sic(self, node, mode):
        return self.transform_orig_elem(node, mode)

    def transform_socalled(self, node, mode):
        return '"' + self.passthru(node, mode) + '"'

    def transform_space(self, node, mode):
        if node.get('dim') == 'horizontal' or node.get('rendition') == '#h-gap':
            return ' '

    def transform_term(self, node, mode):
        if mode == 'edit' and node.get('key'):
            return self.passthru(node, mode) + '[' + node.get('key') + ']'
        else:
            return self.passthru(node, mode)

    def transform_title(self, node, mode):
        if mode == 'edit' and node.get('key'):
            return self.passthru(node, mode) + '[' + node.get('key') + ']'
        else:
            return self.passthru(node, mode)

    def transform_titlepage(self, node, mode):
        return self.passthru(node, mode) + '\n'

    # UTIL FUNCTIONS

    def transform_edit_elem(self, node, mode):
        if mode == 'edit':
            return self.passthru(node, mode)
        else:
            return ''

    def transform_orig_elem(self, node, mode):
        if mode == 'orig' or not exists(node, 'parent::tei:choice/*[self::tei:expan or self::tei:corr or self::tei:reg]'):
            return self.passthru(node, mode)
        else:
            return ''
