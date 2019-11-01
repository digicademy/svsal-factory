from lxml import etree
import re
from api.v1.xutils import flatten, is_element, is_text_node, exists, xml_ns, get_xml_id
from api.v1.works.fragmentation import is_basic_elem, is_marginal_elem, is_structural_elem, has_basic_ancestor
from api.v1.works.errors import TEIUnkownElementError
from api.v1.works.config import tei_text_elements

import api.v1.works.factory as factory



# CONTROLLER FUNCTIONS


def txt_dispatch(node, mode):
    if is_element(node):
        if globals().get('txt_' + etree.QName(node).localname.lower()):
            return globals()['txt_' + etree.QName(node).localname.lower()](node, mode)
        elif etree.QName(node).localname in tei_text_elements:
            return txt_passthru(node, mode)
        else:
            raise TEIUnkownElementError('Unknown element: ' + etree.QName(node).localname)
    elif is_text_node(node):
        return txt_text_node(node)
    else:
        return ''
    # omit comments and processing instructions


def txt_passthru(node, mode):
    if len(node.xpath('node()')) > 0:
        children = []
        for child in node.xpath('node()'):
            if is_element(child):
                if is_basic_elem(child) and is_marginal_elem(child):
                    id = get_xml_id(child)
                    children.append('{%note:' + id + '%}')
                    # placeholder for marginal note in main text: those must be reinserted later if necessary
                    # TODO: use citetrail rather than xml:id? make sure that placeholders are excluded from searching/indexing
                elif not is_structural_elem(child):
                    # makes sure that structural elements yield only headings, not their nested content
                    children.append(txt_dispatch(child, mode))
            else:
                children.append(txt_dispatch(child, mode))
        return ''.join(list(flatten(children)))
    else:
        return ''


def txt_text_node(node):
    return re.sub(r'\s+', ' ', str(node))



# ELEMENT FUNCTIONS


def txt_abbr(node, mode):
    return txt_orig_elem(node, mode)


def txt_bibl(node, mode):
    if mode == 'edit' and exists(node, '@sortKey'):
        text = txt_passthru(node, mode)
        return text + ' [' + re.sub(r'_', ', ', node.get('sortKey')) + ']' # TODO revision of bibl/@sortKey
    else:
        return txt_passthru(node, mode)


def txt_byline(node, mode):
    return txt_passthru(node, mode) + '\n'


def txt_cb(node, mode):
    if not node.get('break') == 'no':
        return ' '


def txt_corr(node, mode):
    return txt_edit_elem(node, mode)


def txt_div(node, mode): # nr
    # in txt, div can maximally yield a label; the processing of its children happens on the is_basic_element level
    if mode == 'edit'and node.get('n') and not re.match(r'^[\[\]\d]+$]', node.get('n')): # if @n is more than a mere number
        return '\n[ *' + node.get('n') + '* ]\n'
    else:
        return '\n'


def txt_doctitle(node, mode):
    return txt_passthru(node, mode) + '\n'


def txt_expan(node, mode):
    return txt_edit_elem(node, mode)


def txt_figure(node, mode):
    return ''


def txt_g(node, mode):
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
                return txt_passthru(node, mode)
        else:
            return txt_passthru(node, mode)


def txt_gap(node, mode):
    return ''


def txt_imprint(node, mode):
    return txt_passthru(node, mode) + '\n'


def txt_item(node, mode): # TODO test this, esp. with more complicated/nested lists
    text = ''
    if is_basic_elem(node) or has_basic_ancestor(node):
        text = txt_passthru(node, mode)
    leading = '- '
    if exists(node, 'parent::tei:list/@type = "numbered"'):
        leading = '# '
    elif exists(node, 'parent::tei:list/@type = "simple"'):
        leading = ' '
    return leading + text + '\n'


def txt_label(node, mode):
    text = txt_passthru(node, mode)
    if node.get('place') == 'margin':
        return '{\n\t' + text + '\n}' # TODO separate notes from surrounding text rather during final txt serialization?
    else:
        return text


def txt_l(node, mode):
    return txt_passthru(node, mode) + '\n'


def txt_lb(node, mode):
    if not node.get('break') == 'no':
        return ' '


def txt_list(node, mode): #nr
    # in txt, div can maximally yield a label; the processing of its descendants happens on the is_basic_element level
    if mode == 'edit' and node.get('n') and not re.match(r'^[\d\[\]]+$', node.get('n')):
        return '\n[*' + node.get('n') + '*]\n'
    else:
        return '\n'


def txt_lg(node, mode):
    return '\n' + txt_passthru(node, mode)


def txt_milestone(node, mode):
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


def txt_name(node, mode):
    text = txt_passthru(node, mode)
    if mode == 'edit' and node.get('key') and node.get('ref'):
        return text + ' [' + node.get('key') + '/' + node.get('ref') + ']'
    elif mode == 'edit' and (node.get('key') or node.get('ref')):
        return text + ' [' + '/'.join([a for a in (node.get('key'), node.get('ref')) if a is not None]) + ']'
    else:
        return text


def txt_note(node, mode):
    text = txt_passthru(node, mode)
    return '{\n\t' + text + '\n}' # TODO separate notes from surrounding text rather during final txt serialization?


def txt_orig(node, mode):
    return txt_orig_elem(node, mode)


def txt_p(node, mode):
    text = txt_passthru(node, mode)
    if exists(node, 'ancestor::tei:note'):
        if exists(node, 'following-sibling::tei:p'):
            return text + '\n'
        else:
            return text
    else:
        return '\n' + text + '\n'


def txt_pb(node, mode):
    if not node.get('break') == 'no':
        return ' '


def txt_persname(node, mode):
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
        return txt_passthru(node, mode)


def txt_placename(node, mode):
    if mode == 'edit' and node.get('key'):
        return txt_passthru(node, mode) + '[' + node.get('key') + ']'
    else:
        return txt_passthru(node, mode)


def txt_publisher(node, mode):
    return txt_persname(node, mode)


def txt_pubplace(node, mode):
    return txt_placename(node, mode)


def txt_quote(node, mode):
    return '"' + txt_passthru(node, mode) + '"'


def txt_reg(node, mode):
    return txt_edit_elem(node, mode)


def txt_sic(node, mode):
    return txt_orig_elem(node, mode)


def txt_socalled(node, mode):
    return '"' + txt_passthru(node, mode) + '"'


def txt_space(node, mode):
    if node.get('dim') == 'horizontal' or node.get('rendition') == '#h-gap':
        return ' '


def txt_term(node, mode):
    if mode == 'edit' and node.get('key'):
        return txt_passthru(node, mode) + '[' + node.get('key') + ']'
    else:
        return txt_passthru(node, mode)


def txt_title(node, mode):
    if mode == 'edit' and node.get('key'):
        return txt_passthru(node, mode) + '[' + node.get('key') + ']'
    else:
        return txt_passthru(node, mode)


def txt_titlepage(node, mode):
    return txt_passthru(node, mode) + '\n'


# TXT UTIL FUNCTIONS


def txt_edit_elem(node, mode):
    if mode == 'edit':
        return txt_passthru(node, mode)
    else:
        return ''


def txt_orig_elem(node, mode):
    if mode == 'orig' or not exists(node, 'parent::tei:choice/*[self::tei:expan or self::tei:corr or self::tei:reg]'):
        return txt_passthru(node, mode)
    else:
        return ''


def normalize_space(text):
    return ' '.join(text.split())
