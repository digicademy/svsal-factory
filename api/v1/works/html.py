from lxml import etree
import re
from api.v1.xutils import flatten, is_element, is_text_node, xml_ns, exists, get_list_type, get_xml_id
from api.v1.works.txt import *
from api.v1.works.errors import TEIMarkupError
from api.v1.works.config import edit_class, orig_class
from api.v1.works.fragmentation import is_list_elem, is_main_elem, is_basic_list_elem

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
        if globals().get('html_' + etree.QName(node).localname.lower()):
            return globals()['html_' + etree.QName(node).localname.lower()](node)
        else:
            return html_passthru(node)
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

# TODO: error handling
def html_passthru(node):
    children = [html_dispatch(child) for child in node.xpath('node()')
                    if not (is_element(child) and ((is_basic_elem(child) or is_structural_elem(child))
                                                    or is_list_elem(child) and has_basic_ancestor(child)))]
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


def html_text_node(node):
    return re.sub(r'\s+', ' ', str(node)) # same as txt


# TEI->HTML ELEMENT FUNCTIONS

def html_abbr(node):
    return html_orig_elem(node)


def html_argument(node):
    argument = etree.Element('p')
    argument.set('class', 'argument')
    return html_passthru_append(node, argument)
    # TODO: css for argument if not is_basic_element


def html_bibl(node):
    return html_passthru_append(node, html_make_element_with_class('span', 'bibl'))
    # TODO: use a human-readable form of @sortkey (if available) as @title


def html_byline(node):
    return html_passthru_append(node, html_make_element_with_class('span', 'tp-p byline'))
    # TODO css


def html_cb(node):
    return txt_cb(node, None)


def html_cell(node):
    if node.get('role') == 'label':
        return html_passthru_append(node, html_make_element_with_class('td', 'table-label'))
    else:
        return html_passthru_append(node, html_make_element('td'))


def html_choice(node):
    """
    Editorial interventions: Don't hide original stuff where we have no modern alternative, otherwise
    put it in an "orig" class span which we make invisible by default.
    Put our own edits in spans of class "edit" and add another class to indicate what type of edit has happened.
    """
    return html_dispatch_multiple(node.xpath('child::*'))


def html_corr(node):
    return html_edit_elem(node)


def html_del(node):
    if not exists(node, 'tei:supplied'):
        raise TEIMarkupError('No child tei:supplied exists in tei:del')
    return html_passthru(node)


def html_docauthor(node):
    return html_name


def html_docimprint(node):
    span = html_make_element_with_class('span', 'tp-p docimprint')
    return html_passthru_append(node, span)


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


def html_figure(node):
    if node.get('type') == 'ornament':
        return html_make_element_with_class('hr', 'ornament')


def html_foreign(node):
    cl = 'foreign'
    if node.xpath('@xml:lang', namespaces=xml_ns)[0]:
        cl += ' ' + node.xpath('@xml:lang', namespaces=xml_ns)[0]
    return html_passthru_append(node, html_make_element_with_class('span', cl))


def html_g(node):
    if not node.text:
        raise TEIMarkupError('tei:g does not contain text')
    char_code = node.get('ref')[1:]
    char = factory.config.get_chars()[char_code]
    orig_glyph = char.get('precomposed')
    if char.get('composed'):
        orig_glyph = char.get('composed')
        # composed strings are preferable since some precomposed chars are displayed oddly in certain contexts
        # (e.g. chare0303 in bold headings)
    # Depending on the context or content of the g element, there are several possible cases:
    # 1.) if g occurs within choice, we can simply take an original character since any expansion should be handled
    # through the choice mechanism
    if exists(node, 'ancestor::tei:choice'):
        return orig_glyph
    # 2.) g occurs outside of choice:
    else:
        # a) g has been used for resolving abbreviations (in early texts W0004, W0013 and W0015)
        # -> treat it like a choice element
        if not str(node.text) in (char.get('precomposed'), char.get('composed')) \
                and not char_code in ('char017f', 'char0292'):
            orig_span = html_make_element_with_class('span', orig_class + ' glyph hidden')
            orig_span.set('title', node.text)
            orig_span.text = orig_glyph
            edit_span = html_make_element_with_class('span', edit_class + ' glyph')
            edit_span.set('title', orig_glyph)
            edit_span.text = node.text
            return [orig_span, edit_span]
        # b) most common case: g simply marks a special character -> pass it through (except for the
        # very frequent "long s" and "long z", which are to be normalized
        elif char_code in ('char017f', 'char0292'):
            # long s and z shall be switchable to their standardized versions in constituted mode
            standardized_glyph = char.get('standardized')
            orig_span = html_make_element_with_class('span', orig_class + ' glyph hidden simple')
            orig_span.set('title', standardized_glyph)
            orig_span.text = orig_glyph
            edit_span = html_make_element_with_class('span', edit_class + ' glyph simple')
            edit_span.set('title', orig_glyph)
            edit_span.text = standardized_glyph
            return [orig_span, edit_span]
        # all other simple characters:
        else:
            return html_passthru(node)
    # TODO css


def html_gap(node):
    if exists(node, 'ancestor::tei:damage'):
        span = html_make_element_with_class('span', 'gap')
        span.set('title', '?') # TODO
        return span


def html_head(node):
    if is_list_elem(node):
        return html_passthru_append(node, html_make_element_with_class('li', 'head'))
        # TODO: to be rendered like h4, e.g., and without bullet or number
    elif is_main_elem(node):
        return html_passthru_append(node, html_make_element_with_class('h3', 'main-head'))
    elif exists(node, 'parent::tei:lg'):
        return html_passthru_append(node, html_make_element_with_class('h5', 'poem-head'))
    # TODO css
    else:
        raise TEIMarkupError('Unknown context of tei:head')


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


def html_imprimatur(node):
    return html_passthru_append(node, html_make_element_with_class('span', 'tp-p imprimatur'))
    # TODO css


def html_item(node):
    if is_basic_list_elem(node):
        list_type = get_list_type(node)
        if list_type == 'ordered': # ordered / enumerated
            li = html_make_element_with_class('li', 'ordered')
            num = str(len(node.xpath('preceding-sibling::tei:item', namespaces=xml_ns)))
            li.set('value', num) # this should state the number of the item within the ordered list
            return html_passthru_append(node, li)
        elif list_type == 'simple': # no HTML list at all
            span = html_make_element_with_class('span', 'li-inline')
            return [' ', html_passthru_append(node, span), ' ']
        else: # unordered/bulleted, e.g. 'index', 'summaries'
            li = html_make_element_with_class('li', 'unordered')
            return html_passthru_append(node, li)
    # TODO: ids for citability?


def html_lg(node):
    return html_passthru_append(html_make_element_with_class('div', 'poem'))


def html_milestone(node):
    span = html_make_element_with_class('span', 'milestone')
    span.set('id', get_xml_id(node))
    if node.get('rendition') and node.get('rendition') == '#dagger':
        sup = html_make_element('sup')
        sup.text = '†'
        span.append(sup)
    elif node.get('rendition') and node.get('rendition') == '#asterisk':
        span.text = '*'
    return span


def html_name(node):
    span = html_make_element_with_class('span', 'name ' + etree.QName(node).localname)
    if node.get('key'):
        span.set('title', node.get('key'))
    return html_passthru_append(node, span)
    # TODO: make proper use of @ref here



# TODO:
#def html_note(node):



# TODO: forward to this from orig, sic, abbr
def html_orig_elem(node):
    if exists(node, 'parent::tei:choice'):
        edit_elem = node.xpath('parent::tei:choice/(tei:expan|tei:reg|tei:corr)', namespaces=xml_ns)[0]
        edit_str = txt_dispatch(edit_elem, 'edit')
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
        elem = html_make_element_with_class('span', 'p-note')
    elif exists(node, 'ancestor::tei:item'):
        elem = html_make_element_with_class('span', 'p-item')
    elif exists(node, 'ancestor::tei:titlePage'):
        elem = html_make_element_with_class('span', 'p-titlepage')
    # main text:
    else:
        elem = html_make_element_with_class('p', 'p')
    return html_passthru_append(node, elem)


def html_sic(node):
    return html_orig_elem(node)





# HTML UTIL FUNCTIONS


def html_make_element(elem_name):
    return etree.Element(elem_name)


def html_make_element_with_class(elem_name, class_name):
    el = etree.Element(elem_name)
    el.set('class', class_name)
    return el