from lxml import etree
import re
from api.v1.xutils import flatten, is_element, is_text_node, xml_ns, exists
from api.v1.works.analysis import is_marginal_elem
from api.v1.works.txt import *

# TODO: simplify the following XPaths
# determines whether hi occurs within a section with overwriting alignment information:
hi_is_within_specific_alignment_section = \
    etree.XPath('boolean(self::tei:hi[ancestor::tei:head or ' +
                'ancestor::tei:signed or ancestor::tei:titlePage or ' +
                'ancestor::tei:argument])',
                namespaces=xml_ns)
# determines whether hi's alignment information is "colliding" with alignment of other text nodes in the same section:
basic_hi_containers = """self::tei:p or self::tei:head or self::tei:note or 
                         self::tei:item or self::tei:cell or self::tei:label or 
                         self::tei:signed or self::tei:lg or self::tei:titlePage"""
hi_is_outlier_within_section = \
    etree.XPath('boolean(ancestor::*[' + basic_hi_containers + '][1]'
                + '//text()[not(ancestor::tei:hi[contains(@rendition, "#r-center")])])',
                namespaces=xml_ns)


def html_dispatch(node):
    if is_element(node):
        return globals()['html_' + etree.QName(node).localname](node)
        # this automatically throws a KeyError if there is no function defined for the element
        # in that case, simply add a function (called 'html_' + element_localname) below
    elif is_text_node(node):
        return html_text_node(node)
    # omit comments and processing instructions


def html_dispatch_multiple(nodes):
    dispatched = []
    for node in nodes:
        dispatched.append(html_dispatch(node))
    if len(dispatched) > 0:
        return list(flatten(dispatched))
    else:
        return


def html_text_node(node):
    return re.sub(r'\s+', ' ', str(node))


def html_passthru(node):
    children = [html_dispatch(child) for child in node.xpath('node()')
                    if not (is_element(child) and (is_basic_elem(child) or is_structural_elem(child)))]
    # not (is_basic_elem(child) or is_structural_elem(child)) makes sure that only teasers are processed for structural
    # elements
    return list(flatten(children))


def html_passthru_append(orig_node, new_node):
    children = html_passthru(orig_node)
    preceding_elem = None
    for child in children:
        if etree.iselement(child):
            new_node.append(child)
            preceding_elem = child
        elif isinstance(child, str):
            if not preceding_elem is None:
                if preceding_elem.tail:
                    preceding_elem.tail += child
                else:
                    preceding_elem.tail = child
            else:
                if new_node.text:
                    new_node.text += child
                else:
                    new_node.text = child
            # see also https://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
    return new_node


# TEI->HTML Element Functions

def html_abbr(node):
    return html_orig_elem(node)


def html_argument(node):
    argument = etree.Element('p')
    argument.set('class', 'argument')
    return html_passthru_append(node, argument) # TODO: css for argument if not is_basic_element


# TODO: continue


def html_choice(node):
    return html_dispatch_multiple(node.xpath('child::*'))


def html_corr(node):
    return html_edit_elem(node)


def html_edit_elem(node):
    if exists(node, 'parent::tei:choice'):
        orig_str = 'test' # TODO: string-join(render:dispatch($node/parent::tei:choice/(tei:abbr|tei:orig|tei:sic), 'orig'), '')
        span = etree.Element('span')
        span.set('class', 'edit ' + etree.QName(node).localname)
        span.set('title', orig_str)
        return html_passthru_append(node, span)
    else:
        return html_passthru(node)


def html_expan(node):
    return html_edit_elem(node)


def html_g(node):
    return html_passthru(node) # TODO


# TODO: simplify
def html_hi(node):
    styles = node.get('rendition').split(' ')
    css_classes = []
    for s in styles:
        if s == '#b':
            css_classes.append('hi-b') # font-weight:bold;
        elif s == '#initCaps':
            css_classes.append('hi-initcaps') # css style?
        elif s == '#it':
            css_classes.append('hi-it') # font-style:italic;
        elif s == '#rt':
            css_classes.append('hi-rt') # font-style:normal;
        elif s == '#l-indent':
            css_classes.append('hi-l-indent') # display:block;margin-left:4em;
        elif s == '#r-center' and not hi_is_within_specific_alignment_section(node) \
                              and not hi_is_outlier_within_section(node):
            css_classes.append('hi-r-center') # display:block;text-align:center;
        elif s == '#right' and not hi_is_within_specific_alignment_section(node) \
                           and not exists(node, 'ancestor::tei:item'):
            css_classes.append('hi-right') # display:block;text-align:right;
        elif s == '#sc':
            css_classes.append('hi-sc') # font-variant:small-caps;
        elif s == '#spc':
            css_classes.append('hi-spc') # letter-spacing:2px;
        elif s == '#sub':
            css_classes.append('hi-sub') # vertical-align:sub;font-size:.83em;
        elif s == '#sup':
            css_classes.append('hi-sup') # vertical-align:super;font-size: .83em;
    span = etree.Element('span')
    span.set('class', ' '.join(css_classes))
    return html_passthru_append(node, span)



# ELEMENT FUNCTIONS


def html_cb(node):
    return txt_cb(node, None)


def html_orig_elem(node):
    if exists(node, 'parent::tei:choice'):
        edit_str = 'test' # TODO: string-join(render:dispatch($node/parent::tei:choice/(tei:expan|tei:reg|tei:corr), 'edit'), '')
        span = etree.Element('span')
        span.set('class', 'orig ' + etree.QName(node).localname)
        span.set('title', edit_str)
        return html_passthru_append(node, span)
    else:
        return html_passthru(node)


def html_lb(node):
    return txt_lb(node, None)


def html_p(node):
    elem = None
    # special contexts:
    if exists(node, 'ancestor::tei:note'):
        elem = etree.Element('span')
        elem.set('class', 'p-note')
    elif exists(node, 'ancestor::tei:item'):
        elem = etree.Element('span')
        elem.set('class', 'p-item')
    elif exists(node, 'ancestor::tei:titlePage'):
        elem = etree.Element('span')
        elem.set('class', 'p-titlepage')
    # main text:
    else:
        elem = etree.Element('p')
        elem.set('class', 'p')
    return html_passthru_append(node, elem)


def html_sic(node):
    return html_orig_elem(node)