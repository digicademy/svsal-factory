from api.v1.xutils import xml_ns, get_list_type, get_target_node
from api.v1.works.txt import *
from api.v1.errors import TEIMarkupError, TEIUnkownElementError
from api.v1.works.config import edit_class, orig_class, image_server, iiif_img_default_params, tei_text_elements, \
    id_server, WorkConfig
from api.v1.works.analysis import WorkAnalysis


class WorkHTMLTransformer:

    def __init__(self, config: WorkConfig, analysis: WorkAnalysis):
        self.config = config
        self.analysis = analysis

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
            elif etree.QName(node).localname in tei_text_elements:
                return html_passthru(node)
            else:
                raise TEIUnkownElementError('Unknown element: ' + etree.QName(node).localname)
        elif is_text_node(node):
            return html_text_node(node)
        # omit comments and processing instructions


    def html_dispatch_multiple(nodes):
        dispatched = []
        for node in nodes:
            dispatched.append(html_dispatch(node))
        if len(dispatched) > 0:
            return list(flatten(dispatched))


    # TODO: error handling
    def html_passthru(node):
        children = [html_dispatch(child) for child in node.xpath('node()')
                        if not (is_element(child) and ((is_basic_elem(child) or is_structural_elem(child))
                                                        or is_list_elem(child) and has_basic_ancestor(child)))]
        children = []
        for child in node.xpath('node()'):
            if is_element(child):
                # Filters:
                # for page nodes, anchor nodes, and marginal nodes, passthru will only make *inline* placeholder elements
                # - their "actual" HTML (page links, teasers, marginal notes) will be produced through direct calls to
                # html_dispatch by node indexing
                if is_page_elem(child):
                    children.append(html_pb_inline(child))
                elif is_anchor_elem(child) or exists(node, 'self::tei:milestone'): # also include milestones that are not "anchors"
                    children.append(html_milestone_inline(child))
                elif is_marginal_elem(child):
                    children.append(html_make_marginal_inline(child))
                # the following shouldn't be the case, but we apply it as a safety filter in case html_dispatch
                # has been called from above the "basic" level:
                elif not (is_basic_elem(child) or is_structural_elem(child) \
                            or (is_list_elem(child) and has_basic_ancestor(child))):
                    children.append(html_dispatch(child))
            else:
                children.append(html_dispatch(child))
        # not (is_basic_elem(child) or is_structural_elem(child)) makes sure that only teasers are processed for structural
        # elements
        return list(flatten(children))


    def html_passthru_append(orig_node, new_node):
        children = html_passthru(orig_node)
        new_node = html_append_children(new_node, children)
        return new_node


    def html_append_children(html_elem, children):
        preceding_elem = None
        for child in children:
            if etree.iselement(child):
                html_elem.append(child)
                preceding_elem = child
            elif isinstance(child, str):
                if not preceding_elem is None:
                    if preceding_elem.tail:
                        preceding_elem.tail += child
                    else:
                        preceding_elem.tail = child
                else:
                    if html_elem.text:
                        html_elem.text += child
                    else:
                        html_elem.text = child
                # see also https://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
        return html_elem


    def html_text_node(node):
        return re.sub(r'\s+', ' ', str(node))


    # TEI->HTML ELEMENT FUNCTIONS

    def html_abbr(node):
        return html_orig_elem(node)


    def html_argument(node):
        argument = etree.Element('p')
        argument.set('class', 'argument')
        return html_passthru_append(node, argument)
        # TODO: css for argument if not is_basic_element


    def html_bibl(node):
        return html_passthru_append(node, make_element_with_class('span', 'bibl'))
        # TODO: use a human-readable form of @sortkey (if available) as @title


    def html_byline(node):
        return html_passthru_append(node, make_element_with_class('span', 'tp-p byline'))
        # TODO css


    def html_cb(node):
        if not node.get('break') == 'no':
            return ' '


    def html_cell(node):
        if node.get('role') == 'label':
            return html_passthru_append(node, make_element_with_class('td', 'table-label'))
        else:
            return html_passthru_append(node, make_element('td'))


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


    def html_div(node):
        pass # TODO: make_section_teaser


    def html_docauthor(node):
        return html_name


    def html_docimprint(node):
        span = make_element_with_class('span', 'tp-p docimprint')
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
            return make_element_with_class('hr', 'ornament')


    def html_foreign(node):
        cl = 'foreign'
        if node.xpath('@xml:lang', namespaces=xml_ns)[0]:
            cl += ' ' + node.xpath('@xml:lang', namespaces=xml_ns)[0]
        return html_passthru_append(node, make_element_with_class('span', cl))


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
                orig_span = make_element_with_class('span', orig_class + ' glyph hidden')
                orig_span.set('title', node.text)
                orig_span.text = orig_glyph
                edit_span = make_element_with_class('span', edit_class + ' glyph')
                edit_span.set('title', orig_glyph)
                edit_span.text = node.text
                return [orig_span, edit_span]
            # b) most common case: g simply marks a special character -> pass it through (except for the
            # very frequent "long s" and "long z", which are to be normalized
            elif char_code in ('char017f', 'char0292'):
                # long s and z shall be switchable to their standardized versions in constituted mode
                standardized_glyph = char.get('standardized')
                orig_span = make_element_with_class('span', orig_class + ' glyph hidden simple')
                orig_span.set('title', standardized_glyph)
                orig_span.text = orig_glyph
                edit_span = make_element_with_class('span', edit_class + ' glyph simple')
                edit_span.set('title', orig_glyph)
                edit_span.text = standardized_glyph
                return [orig_span, edit_span]
            # all other simple characters:
            else:
                return html_passthru(node)
        # TODO css


    def html_gap(node):
        if exists(node, 'ancestor::tei:damage'):
            span = make_element_with_class('span', 'gap')
            span.set('title', '?') # TODO
            return span


    def html_head(node):
        if is_list_elem(node):
            return html_passthru_append(node, make_element_with_class('li', 'head'))
            # TODO: to be rendered like h4, e.g., and without bullet or number
        elif is_main_elem(node):
            return html_passthru_append(node, make_element_with_class('h3', 'main-head'))
        elif exists(node, 'parent::tei:lg'):
            return html_passthru_append(node, make_element_with_class('h5', 'poem-head'))
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
        return html_passthru_append(node, make_element_with_class('span', 'tp-p imprimatur'))
        # TODO css


    def html_item(node):
        if is_basic_list_elem(node):
            list_type = get_list_type(node)
            if list_type == 'ordered': # ordered / enumerated
                li = make_element_with_class('li', 'ordered')
                num = str(len(node.xpath('preceding-sibling::tei:item', namespaces=xml_ns)))
                li.set('value', num) # this should state the number of the item within the ordered list
                return html_passthru_append(node, li)
            elif list_type == 'simple': # no HTML list at all
                span = make_element_with_class('span', 'li-inline')
                return [' ', html_passthru_append(node, span), ' ']
            else: # unordered/bulleted, e.g. 'index', 'summaries'
                li = make_element_with_class('li', 'unordered')
                return html_passthru_append(node, li)
        # TODO: ids for citability?


    def html_l(node):
        return [html_passthru_append(node, make_element_with_class('span', 'poem-l')), make_element('br')]


    def html_label(node):
        if is_marginal_elem(node):
            return html_make_marginal(node)
        elif node.get('place') == 'inline':
            return html_passthru_append(node, make_element_with_class('span', 'label-inline'))
        # TODO other types of nodes, such as dict labels
        else:
            return html_passthru(node)


    def html_lb(node):
        if not node.get('break') == 'no':
            return ' '


    def html_lg(node):
        return html_passthru_append(node, make_element_with_class('div', 'poem'))


    def html_milestone_inline(node):
        span = make_element_with_class('span', 'milestone')
        span.set('id', get_xml_id(node))
        if node.get('rendition') and node.get('rendition') == '#dagger':
            sup = make_element('sup')
            sup.text = '†'
            span.append(sup)
        elif node.get('rendition') and node.get('rendition') == '#asterisk':
            span.text = '*'
        return span


    def html_name(node):
        span = make_element_with_class('span', 'name ' + etree.QName(node).localname.lower())
        if node.get('key'):
            span.set('title', node.get('key'))
        return html_passthru_append(node, span)
        # TODO: make proper use of @ref here


    def html_note(node):
        if is_marginal_elem(node):
            return html_make_marginal(node)
        else:
            raise TEIMarkupError('Unknown type of tei:note')


    def html_orig(node):
        return html_orig_elem(node)


    def html_orgname(node):
        return html_name(node)


    def html_p(node):
        elem = None
        # special contexts:
        if exists(node, 'ancestor::tei:note'):
            elem = make_element_with_class('span', 'p-note')
        elif exists(node, 'ancestor::tei:item'):
            elem = make_element_with_class('span', 'p-item')
        elif exists(node, 'ancestor::tei:titlePage'):
            elem = make_element_with_class('span', 'p-titlepage')
        # main text:
        else:
            elem = make_element_with_class('p', 'p')
        return html_passthru_append(node, elem)


    def html_pb_inline(node):
        if is_page_elem(node):
            if node.get('type') == 'blank':
                return make_element('br')
            elif exists(node, 'preceding::tei:pb'
                              + ' and preceding-sibling::node()[descendant-or-self::text()[not(normalize-space() = "")]]'
                              + ' and following-sibling::node()[descendant-or-self::text()[not(normalize-space() = "")]]'):
                # mark page break as '|', but not at the beginning or end of structural sections
                pb = make_element_with_class('span', 'pb')
                pb.set('id', get_xml_id(node))
                if node.get('break') == 'no':
                    pb.text = '|'
                else:
                    pb.text = ' | '
                return pb


    def html_pb(node):
        if is_page_elem(node):
            print('html: processing pb ' + get_xml_id(node))
            pb_id = get_xml_id(node)
            title = node.get('n')
            if not re.match(r'^fol\.', title):
                title = 'p. ' + title
            page_link = make_element_with_class('a', 'page-link')
            page_link.set('title', title)
            page_link.set('href', facs_to_uri(node.get('facs')))
            # TODO i18n 'View image of ' + title
            page_link.append(make_element_with_class('i', 'fas fa-book-open'))
            label = make_element_with_class('span', 'page-label')
            label.text = get_node_title(node)
            page_link.append(label)
            return page_link
            # TODO data-canvas / render:resolveCanvasID !
            # TODO css


    def html_persname(node):
        return html_name(node)


    def html_placename(node):
        return html_name(node)


    def html_publisher(node):
        return html_name(node)


    def html_pubplace(node):
        return html_name(node)


    def html_quote(node):
        # Possible approach for dealing with quote:
        # quote may occur on any level (even above tei:div), so we indicate its start and end by means of empty anchors
        #quote_id = str(b64encode(urandom(8))) # TODO check if this really works
        #start = make_element_with_class('span', 'quote start-' + quote_id)
        #end = make_element_with_class('span', 'quote end-' + quote_id)
        #return [start, html_passthru(node), end]
        # css: make sure that span.quote is not visible
        return html_passthru(node)


    def html_ref(node):
        if node.get('type') == 'note-anchor':
            return html_passthru_append(node, make_element_with_class('sup', 'ref-note'))
            # TODO: get reference to note, e.g. for highlighting
        elif node.get('target'):
            resolved_uri = make_uri_from_target(node, node.get('target'))
            if resolved_uri:
                return html_transform_node_to_link(node, resolved_uri)
            else:
                return html_passthru(node)
        else:
            return html_passthru(node)


    def html_row(node):
        return html_passthru_append(node, make_element('tr'))


    def html_sic(node):
        return html_orig_elem(node)


    def html_signed(node):
        return html_passthru_append(node, make_element_with_class('p', 'signed'))


    def html_space(node):
        if node.get('dim') == 'horizontal' or node.get('rendition') == '#h-gap':
            return ' '


    def html_supplied(node):
        orig_text = txt_passthru(node, 'orig')
        edit_text = txt_passthru(node, 'edit')
        orig_span = make_element_with_class('span', orig_class + ' hidden supplied')
        orig_span.set('title', edit_text) # assuming that title is not too long...
        orig_span.text = '[' + orig_text + ']' # omitting any markup information here
        edit_span = make_element_with_class('span', edit_class + ' supplied')
        edit_span.set('title', '[' + orig_text + ']')  # assuming that title is not too long...
        edit_span.text = edit_text  # omitting any markup information here
        return [orig_span, edit_span]
        # TODO testing, css and i18n


    def html_table(node):
        return html_passthru_append(node, make_element('table'))


    def html_term(node):
        return html_name(node)


    def html_text(node):
        if node.get('type') == 'work_volume' and exists(node, 'preceding::tei:text[@type = "work_volume"]'):
            return make_element('hr')
            # TODO: section_teaser + teaser anchor


    def html_title(node):
        return html_name(node)


    def html_titlepage(node):
        tp_class = 'titlepage'
        if exists(node, 'preceding-sibling::tei:titlePage'):
            tp_class = 'titlepage-sec'
        return html_passthru_append(node, make_element_with_class('div', tp_class))
        # TODO css


    def html_titlepart(node):
        if node.get('type') == 'main':
            return html_passthru_append(node, make_element('h1'))
        else:
            return html_passthru(node)


    def html_unclear(node):
        unclear = make_element_with_class('span', 'unclear')
        if exists(node, 'descendant::text()'):
            return html_passthru_append(node, unclear)
        else:
            return unclear
        # TODO css, i18n



    # TODO
    #  - make sure every function returns content, if required


    # HTML UTIL FUNCTIONS


    def html_transform_node_to_link(node: etree._Element, uri: str):
        """
        Transforms a $node into an HTML link anchor (a[@href]). Prevents child::tei:pb from occurring within the link, if required.
        """
        if not exists(node, 'child::tei:pb'):
            a = html_make_a_with_href(uri, True)
            return html_passthru_append(node, a)
        else:
            # make an anchor for the preceding part, then render the pb, then "continue" the anchor
            # note that this currently works only if pb occurs at the child level, and only with the first pb
            before_children = html_dispatch_multiple(node.xpath('child::tei:pb[1]/preceding-sibling::node()', namespaces=xml_ns))
            before = html_append_children(html_make_a_with_href(uri, True), before_children)
            page_break = html_dispatch(node.xpath('child::tei:pb[1]', namespaces=xml_ns)[0])
            after_children = html_dispatch_multiple(node.xpath('child::tei:pb[1]/following-sibling::node()', namespaces=xml_ns))
            after = html_append_children(html_make_a_with_href(uri, True), after_children)
            return [before, page_break, after]


    def html_make_a_with_href(href_value, target_blank=True):
        a = etree.Element('a')
        a.set('href', href_value)
        if target_blank:
            a.set('target', '_blank')
        return a


    # TODO: testing, esp. from 1st "elif" onwards
    def make_uri_from_target(node, targets):
        target = targets.split()[0] # if there are several, first one wins
        work_scheme = r'(work:(W[A-z0-9.:_\-]+))?#(.*)' # TODO is this failsafe?
        facs_scheme = r'facs:((W[0-9]+)[A-z0-9.:#_\-]+)'
        generic_scheme = r'(\S+):([A-z0-9.:#_\-]+)'
        uri = target
        if target.startswith('#'):
            # target is some node in the current work
            targeted = get_target_node(node, id=target[1:])
            if len(targeted) == 1:
                uri = make_citetrail_uri_from_xml_id(get_xml_id(targeted[0]))
        elif re.match(work_scheme, target):
            # target is something like "work:W...#..."
            if re.sub(work_scheme, '$2', target):
                target_work_id = re.sub(work_scheme, '$2', target)
                uri = id_server + '/texts/' + target_work_id
                # TODO this merely refers to a complete work, how to handle specific nodes/citetrails?
            else:
                # target is just a link to a fragment anchor, so targetWorkId = currentWork
                anchor_id = re.sub(work_scheme, '$3', target)
                if anchor_id:
                    uri = make_citetrail_uri_from_xml_id(anchor_id)
        elif re.match(facs_scheme, target):
            # target is a facs string
            target_work_id = re.sub(facs_scheme, '$2', target)
            if target_work_id == node.xpath('preceding::tei:lb[1]', namespaces=xml_ns)[0]: # TODO: workaround for dynamic config
                # facs is in the same work
                pb = node.xpath('ancestor::tei:TEI//tei:pb[@facs = "' + target + '"'
                                + ' and not(@sameAs or @corresp) and @xml:id]', namespaces=xml_ns)
                if len(pb) > 0:
                    uri = make_citetrail_uri_from_xml_id(get_xml_id(pb[0]))
            else:
                raise TEIMarkupError('@target refers to @facs from a different work than the current one')
        elif re.match(generic_scheme, target):
            from api.v1.works.factory import config
            # use the general replacement mechanism as defined by the teiHeader's prefixDef
            prefix = re.sub(generic_scheme, '$1', target)
            value = re.sub(generic_scheme, '$2', target)
            prefix_def = config.get_prefix_defs().get(prefix)
            if prefix_def:
                if re.match(prefix_def['matchPattern'], value):
                    uri = re.sub(prefix_def['matchPattern'], prefix_def['replacementPattern'], value)
            else:
                search = re.search(generic_scheme, target)
                uri = re.sub(generic_scheme, '$0', target) # TODO is this working?
        return uri


    def make_citetrail_uri_from_xml_id(id: str):
        """
        Tries to derive the citetrail for a node from its @xml:id. Works only if the node/@xml:id is in work "config.wid"
        """
        from api.v1.works.factory import config
        citetrail = config.get_citetrail_mapping(id)
        wid = id[:5] # TODO this is a workaround until config is passed dynamically
        if citetrail:
            print('Deriving citetrail ' + citetrail + ' from xml:id ' + id)
            return id_server + '/texts/' + wid + ':' + citetrail
        else:
            return ''


    def facs_to_uri(pb_facs):
        facs = pb_facs.split()[0]
        single_vol_regex = r'facs:(W[0-9]{4})\-([0-9]{4})'
        multi_vol_regex = r'facs:(W[0-9]{4})\-([A-z])\-([0-9]{4})'
        if re.match(single_vol_regex, facs): # single-volume work, e.g. "facs:W0017-0005"
            work_id = re.sub(single_vol_regex, '$1', facs)
            facs_id = re.sub(single_vol_regex, '$2', facs)
            return image_server + '/iiif/image/' + work_id + '!' + work_id + '-' + facs_id + iiif_img_default_params
        elif re.match(multi_vol_regex, facs):
            work_id = re.sub(multi_vol_regex, '$1', facs)
            vol_id = re.sub(multi_vol_regex, '$2', facs)
            facs_id = re.sub(multi_vol_regex, '$3', facs)
            return image_server + '/iiif/image/' + work_id + '!' + vol_id + '!' + \
                   work_id + '-' + vol_id + '-' + facs_id + iiif_img_default_params
        else:
            raise TEIMarkupError('Illegal @facs value: ' + facs + ' (' + pb_facs + ')')


    def html_orig_elem(node):
        if exists(node, 'parent::tei:choice'):
            edit_elem = node.xpath('parent::tei:choice/*[self::tei:expan or self::tei:reg or self::tei:corr]',
                                   namespaces=xml_ns)[0]
            edit_str = txt_dispatch(edit_elem, 'edit')
            span = make_element_with_class('span', orig_class + ' ' + etree.QName(node).localname)
            span.set('title', edit_str)
            return html_passthru_append(node, span)
        else:
            return html_passthru(node)


    def html_make_marginal(node):
        note = make_element_with_class('div', 'marginal')
        note.set('id', get_xml_id(node))
        if node.get('n'):
            label = make_element_with_class('span', 'marginal-label')
            label.text = node.get('n')
            note.append(label)
        if exists(node, 'tei:p'):
            return html_passthru_append(node, note)
        else:
            p_note = make_element_with_class('span', 'p-note')
            note.append(html_passthru_append(node, p_note))
            return note


    def html_make_marginal_inline(node):
        # make an empty anchor for referencing purposes
        inline_marg = make_element_with_class('span', 'marginal')
        inline_marg.set('id', get_xml_id(node))
        return inline_marg


    def make_element(elem_name):
        return etree.Element(elem_name)


    def make_element_with_class(elem_name, class_name):
        el = etree.Element(elem_name)
        el.set('class', class_name)
        return el