from lxml import etree
import re
from api.v1.xutils import flatten, is_element, is_text_node, xml_ns, exists
from api.v1.works.analysis import is_marginal_elem
import api.v1.works.factory as factory



# CONTROLLER FUNCTIONS


def txt_dispatch(node, mode):
    if is_element(node):
        if globals().get('txt_' + etree.QName(node).localname):
            return globals()['txt_' + etree.QName(node).localname](node, mode)
        else:
            return txt_passthru(node, mode)
    elif is_text_node(node):
        return txt_text_node(node)
    # omit comments and processing instructions


def txt_passthru(node, mode):
    children = [txt_dispatch(child, mode) for child in node.xpath('node()') if not (is_element(child) and is_marginal_elem(child))]
    return flatten(children) # TODO: list(flatten(children)) ?


def txt_text_node(node):
    return re.sub(r'\s+', ' ', str(node)) # TODO: same as HTML



# ELEMENT FUNCTIONS


def txt_abbr(node, mode):
    if not (mode == 'edit' and exists(node, 'parent::tei:choice/tei:expan')):
        return txt_passthru(node, mode)


def txt_bibl(node, mode):
    if mode == 'edit' and exists(node, '@sortKey'):
        text = txt_passthru(node, mode)
        return text + ' [' + re.sub(r'_', ', ', node.get('sortKey')) + ']' # TODO revision of bibl/@sortKey
    else:
        return txt_passthru(node, mode)


def txt_cb(node, mode):
    if not node.get('break') == 'no':
        return ' '


#def txt_choice(node, mode):
#    return txt_passthru(node, mode)


def txt_corr(node, mode):
    if mode == 'orig' and exists(node, 'parent::tei:choice/tei:sic'):
        return
    else:
        return txt_passthru(node, mode)


def txt_div(node, mode):
    if mode == 'edit':
        text = txt_passthru(node, mode)
        title = ''
        if node.get('n') and not re.match(r'^[\[\]\d]+$]', node.get('n')): # if @n is more than a mere number
            title = '[ *' + node.get('n') + '* ]\n'
        return '\n' + title + text + '\n'
    else:
        return txt_passthru(node, mode)


def txt_expan(node, mode):
    if mode == 'orig' and exists(node, 'parent::tei:choice/tei:abbr'):
        return ''
    else:
        return txt_passthru(node, mode)


def txt_g(node, mode):
    char = factory.config.get_chars()[node.get('ref')[1:]]
    print('Getting char ' + node.get('ref')[1:] + ', got ' + str(len(char)) + ' chars')
    if mode == 'orig':
        if char.get('precomposed'):
            return char['precomposed']
        elif char.get('composed'):
            return char['composed']
        else:
            return char['standardized']
    else: # mode == 'edit'
        char_code = factory.config.get_chars()[node.get('ref')[1:]]
        if char_code in ('char017f', 'char0292'):
            if node.text in (char['precomposed'], char['composed']):
                return char['standardized']
            else:
                return txt_passthru(node, mode)
        else:
            return txt_passthru(node, mode)



def txt_lb(node, mode):
    if not node.get('break') == 'no':
        return ' '


def txt_orig(node, mode):
    if mode == 'edit' and exists(node, 'parent::tei:choice/tei:reg'):
        return
    else:
        return txt_passthru(node, mode)


def txt_reg(node, mode):
    if mode == 'orig' and exists(node, 'parent::tei:choice/tei:orig'):
        return
    else:
        return txt_passthru(node, mode)


def txt_sic(node, mode):
    if mode == 'edit' and exists(node, 'parent::tei:choice/tei:corr'):
        return
    else:
        return txt_passthru(node, mode)