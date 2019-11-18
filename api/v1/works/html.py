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
    __hi_is_within_specific_alignment_section_xpath = \
        etree.XPath('boolean(self::tei:hi[ancestor::tei:head or ' +
                    'ancestor::tei:signed or ancestor::tei:titlePage or ' +
                    'ancestor::tei:argument])',
                    namespaces=xml_ns)
    # determines whether hi's alignment information is "colliding" with alignment of other text nodes in the same section:
    __basic_hi_containers_def = """self::tei:p or self::tei:head or self::tei:note or 
                             self::tei:item or self::tei:cell or self::tei:label or 
                             self::tei:signed or self::tei:lg or self::tei:titlePage"""
    __hi_is_outlier_within_section_xpath = \
        etree.XPath('boolean(ancestor::*[' + __basic_hi_containers_def + '][1]'
                    + '//text()[not(ancestor::tei:hi[contains(@rendition, "#r-center")])])',
                    namespaces=xml_ns)

    def dispatch(self, node):
        if is_element(node):
            # check whether there is a specific transformation function defined for the element type - if not,
            # we pass the node through
            elem_function = getattr(self, 'transform_' + etree.QName(node).localname.lower(), None)
            if callable(elem_function):
                return elem_function(node)  # globals()[etree.QName(node).localname.lower()](node)
            elif etree.QName(node).localname in tei_text_elements:
                return self.passthru(node)
            else:
                raise TEIUnkownElementError('Unknown element: ' + etree.QName(node).localname)
        elif is_text_node(node):
            return self.transform_text_node(node)
        # omit comments and processing instructions

    def dispatch_multiple(self, nodes):
        dispatched = []
        for node in nodes:
            dispatched.append(self.dispatch(node))
        if len(dispatched) > 0:
            return list(flatten(dispatched))

    # TODO: error handling
    def passthru(self, node):
        children = [self.dispatch(child) for child in node.xpath('node()')
                        if not (is_element(child)
                                and ((self.analysis.is_basic_node(child) or self.analysis.is_structural_node(child))
                                     or (self.analysis.is_list_node(child) and self.analysis.has_basic_ancestor(child))))]
        children = []
        for child in node.xpath('node()'):
            if is_element(child):
                # Filters:
                # for page nodes, anchor nodes, and marginal nodes, passthru will only make *inline* placeholder elements
                # - their "actual" HTML (page links, teasers, marginal notes) will be produced through direct calls to
                # self.dispatch by node indexing
                if self.analysis.is_page_node(child):
                    children.append(self.transform_pb_inline(child))
                elif self.analysis.is_anchor_node(child) or exists(node, 'self::tei:milestone'): # also include milestones that are not "anchors"
                    children.append(self.transform_milestone_inline(child))
                elif self.analysis.is_marginal_node(child):
                    children.append(self.transform_make_marginal_inline(child))
                # the following shouldn't be the case, but we apply it as a safety filter in case self.dispatch
                # has been called from above the "basic" level:
                elif not (self.analysis.is_basic_node(child) or self.analysis.is_structural_node(child) \
                          or (self.analysis.is_list_node(child) and self.analysis.has_basic_ancestor(child))):
                    children.append(self.dispatch(child))
            else:
                children.append(self.dispatch(child))
        # not (is_basic_node(child) or is_structural_node(child)) makes sure that only teasers are processed for structural
        # elements
        return list(flatten(children))

    def passthru_append(self, orig_node, new_node):
        children = self.passthru(orig_node)
        new_node = self.transform_append_children(new_node, children)
        return new_node

    def transform_append_children(self, transform_elem, children):
        preceding_elem = None
        for child in children:
            if etree.iselement(child):
                transform_elem.append(child)
                preceding_elem = child
            elif isinstance(child, str):
                if not preceding_elem is None:
                    if preceding_elem.tail:
                        preceding_elem.tail += child
                    else:
                        preceding_elem.tail = child
                else:
                    if transform_elem.text:
                        transform_elem.text += child
                    else:
                        transform_elem.text = child
                # see also https://stackoverflow.com/questions/4624062/get-all-text-inside-a-tag-in-lxml
        return transform_elem

    def transform_text_node(self, node):
        return re.sub(r'\s+', ' ', str(node))

    # TEI->HTML ELEMENT FUNCTIONS

    def transform_abbr(self, node):
        return self.transform_orig_elem(node)

    def transform_argument(self, node):
        argument = etree.Element('p')
        argument.set('class', 'argument')
        return self.passthru_append(node, argument)
        # TODO: css for argument if not is_basic_nodeent

    def transform_bibl(self, node):
        return self.passthru_append(node, self.make_element_with_class('span', 'bibl'))
        # TODO: use a human-readable form of @sortkey (if available) as @title

    def transform_byline(self, node):
        return self.passthru_append(node, self.make_element_with_class('span', 'tp-p byline'))
        # TODO css

    def transform_cb(self, node):
        if not node.get('break') == 'no':
            return ' '

    def transform_cell(self, node):
        if node.get('role') == 'label':
            return self.passthru_append(node, self.make_element_with_class('td', 'table-label'))
        else:
            return self.passthru_append(node, self.make_element('td'))

    def transform_choice(self, node):
        """
        Editorial interventions: Don't hide original stuff where we have no modern alternative, otherwise
        put it in an "orig" class span which we make invisible by default.
        Put our own edits in spans of class "edit" and add another class to indicate what type of edit has happened.
        """
        return self.dispatch_multiple(node.xpath('child::*'))

    def transform_corr(self, node):
        return self.transform_edit_elem(node)

    def transform_del(self, node):
        if not exists(node, 'tei:supplied'):
            raise TEIMarkupError('No child tei:supplied exists in tei:del')
        return self.passthru(node)

    def transform_div(self, node):
        pass # TODO: make_section_teaser

    def transform_docauthor(self, node):
        return self.transform_name

    def transform_docimprint(self, node):
        span = self.make_element_with_class('span', 'tp-p docimprint')
        return self.passthru_append(node, span)

    def transform_edit_elem(self, node):
        if exists(node, 'parent::tei:choice'):
            orig_str = 'test' # TODO: string-join(render:dispatch($node/parent::tei:choice/(tei:abbr|tei:orig|tei:sic), 'orig'), '')
            span = etree.Element('span')
            span.set('class', 'edit ' + etree.QName(node).localname)
            span.set('title', orig_str)
            return self.passthru_append(node, span)
        else:
            return self.passthru(node)

    def transform_expan(self, node):
        return self.transform_edit_elem(node)

    def transform_figure(self, node):
        if node.get('type') == 'ornament':
            return self.make_element_with_class('hr', 'ornament')

    def transform_foreign(self, node):
        cl = 'foreign'
        if node.xpath('@xml:lang', namespaces=xml_ns)[0]:
            cl += ' ' + node.xpath('@xml:lang', namespaces=xml_ns)[0]
        return self.passthru_append(node, self.make_element_with_class('span', cl))

    def transform_g(self, node):
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
                orig_span = self.make_element_with_class('span', orig_class + ' glyph hidden')
                orig_span.set('title', node.text)
                orig_span.text = orig_glyph
                edit_span = self.make_element_with_class('span', edit_class + ' glyph')
                edit_span.set('title', orig_glyph)
                edit_span.text = node.text
                return [orig_span, edit_span]
            # b) most common case: g simply marks a special character -> pass it through (except for the
            # very frequent "long s" and "long z", which are to be normalized
            elif char_code in ('char017f', 'char0292'):
                # long s and z shall be switchable to their standardized versions in constituted mode
                standardized_glyph = char.get('standardized')
                orig_span = self.make_element_with_class('span', orig_class + ' glyph hidden simple')
                orig_span.set('title', standardized_glyph)
                orig_span.text = orig_glyph
                edit_span = self.make_element_with_class('span', edit_class + ' glyph simple')
                edit_span.set('title', orig_glyph)
                edit_span.text = standardized_glyph
                return [orig_span, edit_span]
            # all other simple characters:
            else:
                return self.passthru(node)
        # TODO css

    def transform_gap(self, node):
        if exists(node, 'ancestor::tei:damage'):
            span = self.make_element_with_class('span', 'gap')
            span.set('title', '?') # TODO
            return span

    def transform_head(self, node):
        if self.analysis.is_list_node(node):
            return self.passthru_append(node, self.make_element_with_class('li', 'head'))
            # TODO: to be rendered like h4, e.g., and without bullet or number
        elif self.analysis.is_main_node(node):
            return self.passthru_append(node, self.make_element_with_class('h3', 'main-head'))
        elif exists(node, 'parent::tei:lg'):
            return self.passthru_append(node, self.make_element_with_class('h5', 'poem-head'))
        # TODO css
        else:
            raise TEIMarkupError('Unknown context of tei:head')

    def transform_hi(self, node):
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
            elif s == '#r-center' and not self.__hi_is_within_specific_alignment_section_xpath(node) \
                                  and not self.__hi_is_outlier_within_section_xpath(node):
                css_classes.append('hi-r-center') # display:block;text-align:center;
            elif s == '#right' and not self.__hi_is_within_specific_alignment_section_xpath(node) \
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
        return self.passthru_append(node, span)

    def transform_imprimatur(self, node):
        return self.passthru_append(node, self.make_element_with_class('span', 'tp-p imprimatur'))
        # TODO css

    def transform_item(self, node):
        if self.analysis.is_basic_list_node(node):
            list_type = get_list_type(node)
            if list_type == 'ordered': # ordered / enumerated
                li = self.make_element_with_class('li', 'ordered')
                num = str(len(node.xpath('preceding-sibling::tei:item', namespaces=xml_ns)))
                li.set('value', num) # this should state the number of the item within the ordered list
                return self.passthru_append(node, li)
            elif list_type == 'simple': # no HTML list at all
                span = self.make_element_with_class('span', 'li-inline')
                return [' ', self.passthru_append(node, span), ' ']
            else: # unordered/bulleted, e.g. 'index', 'summaries'
                li = self.make_element_with_class('li', 'unordered')
                return self.passthru_append(node, li)
        # TODO: ids for citability?

    def transform_l(self, node):
        return [self.passthru_append(node, self.make_element_with_class('span', 'poem-l')),
                self.make_element('br')]

    def transform_label(self, node):
        if self.analysis.is_marginal_node(node):
            return self.transform_make_marginal(node)
        elif node.get('place') == 'inline':
            return self.passthru_append(node, self.make_element_with_class('span', 'label-inline'))
        # TODO other types of nodes, such as dict labels
        else:
            return self.passthru(node)

    def transform_lb(self, node):
        if not node.get('break') == 'no':
            return ' '

    def transform_lg(self, node):
        return self.passthru_append(node, self.make_element_with_class('div', 'poem'))

    def transform_milestone_inline(self, node):
        span = self.make_element_with_class('span', 'milestone')
        span.set('id', get_xml_id(node))
        if node.get('rendition') and node.get('rendition') == '#dagger':
            sup = self.make_element('sup')
            sup.text = '†'
            span.append(sup)
        elif node.get('rendition') and node.get('rendition') == '#asterisk':
            span.text = '*'
        return span

    def transform_name(self, node):
        span = self.make_element_with_class('span', 'name ' + etree.QName(node).localname.lower())
        if node.get('key'):
            span.set('title', node.get('key'))
        return self.passthru_append(node, span)
        # TODO: make proper use of @ref here

    def transform_note(self, node):
        if self.analysis.is_marginal_node(node):
            return self.transform_make_marginal(node)
        else:
            raise TEIMarkupError('Unknown type of tei:note')

    def transform_orig(self, node):
        return self.transform_orig_elem(node)

    def transform_orgname(self, node):
        return self.transform_name(node)

    def transform_p(self, node):
        elem = None
        # special contexts:
        if exists(node, 'ancestor::tei:note'):
            elem = self.make_element_with_class('span', 'p-note')
        elif exists(node, 'ancestor::tei:item'):
            elem = self.make_element_with_class('span', 'p-item')
        elif exists(node, 'ancestor::tei:titlePage'):
            elem = self.make_element_with_class('span', 'p-titlepage')
        # main text:
        else:
            elem = self.make_element_with_class('p', 'p')
        return self.passthru_append(node, elem)

    def transform_pb_inline(self, node):
        if self.analysis.is_page_node(node):
            if node.get('type') == 'blank':
                return self.make_element('br')
            elif exists(node, 'preceding::tei:pb'
                              + ' and preceding-sibling::node()[descendant-or-self::text()[not(normalize-space() = "")]]'
                              + ' and following-sibling::node()[descendant-or-self::text()[not(normalize-space() = "")]]'):
                # mark page break as '|', but not at the beginning or end of structural sections
                pb = self.make_element_with_class('span', 'pb')
                pb.set('id', get_xml_id(node))
                if node.get('break') == 'no':
                    pb.text = '|'
                else:
                    pb.text = ' | '
                return pb

    def transform_pb(self, node):
        if self.analysis.is_page_node(node):
            print('html: processing pb ' + get_xml_id(node))
            pb_id = get_xml_id(node)
            title = node.get('n')
            if not re.match(r'^fol\.', title):
                title = 'p. ' + title
            page_link = self.make_element_with_class('a', 'page-link')
            page_link.set('title', title)
            page_link.set('href', self.facs_to_uri(node.get('facs')))
            # TODO i18n 'View image of ' + title
            page_link.append(self.make_element_with_class('i', 'fas fa-book-open'))
            label = self.make_element_with_class('span', 'page-label')
            label.text = self.get_node_title(node)
            page_link.append(label)
            return page_link
            # TODO data-canvas / render:resolveCanvasID !
            # TODO css

    def transform_persname(self, node):
        return self.transform_name(node)

    def transform_placename(self, node):
        return self.transform_name(node)

    def transform_publisher(self, node):
        return self.transform_name(node)

    def transform_pubplace(self, node):
        return self.transform_name(node)

    def transform_quote(self, node):
        # Possible approach for dealing with quote:
        # quote may occur on any level (even above tei:div), so we indicate its start and end by means of empty anchors
        #quote_id = str(b64encode(urandom(8))) # TODO check if this really works
        #start = self.make_element_with_class('span', 'quote start-' + quote_id)
        #end = self.make_element_with_class('span', 'quote end-' + quote_id)
        #return [start, self.passthru(node), end]
        # css: make sure that span.quote is not visible
        return self.passthru(node)

    def transform_ref(self, node):
        if node.get('type') == 'note-anchor':
            return self.passthru_append(node, self.make_element_with_class('sup', 'ref-note'))
            # TODO: get reference to note, e.g. for highlighting
        elif node.get('target'):
            resolved_uri = self.make_uri_from_target(node, node.get('target'))
            if resolved_uri:
                return self.transform_node_to_link(node, resolved_uri)
            else:
                return self.passthru(node)
        else:
            return self.passthru(node)

    def transform_row(self, node):
        return self.passthru_append(node, self.make_element('tr'))

    def transform_sic(self, node):
        return self.transform_orig_elem(node)

    def transform_signed(self, node):
        return self.passthru_append(node, self.make_element_with_class('p', 'signed'))

    def transform_space(self, node):
        if node.get('dim') == 'horizontal' or node.get('rendition') == '#h-gap':
            return ' '

    def transform_supplied(self, node):
        orig_text = txt_passthru(node, 'orig')
        edit_text = txt_passthru(node, 'edit')
        orig_span = self.make_element_with_class('span', orig_class + ' hidden supplied')
        orig_span.set('title', edit_text) # assuming that title is not too long...
        orig_span.text = '[' + orig_text + ']' # omitting any markup information here
        edit_span = self.make_element_with_class('span', edit_class + ' supplied')
        edit_span.set('title', '[' + orig_text + ']')  # assuming that title is not too long...
        edit_span.text = edit_text  # omitting any markup information here
        return [orig_span, edit_span]
        # TODO testing, css and i18n

    def transform_table(self, node):
        return self.passthru_append(node, self.make_element('table'))

    def transform_term(self, node):
        return self.transform_name(node)

    def transform_text(self, node):
        if node.get('type') == 'work_volume' and exists(node, 'preceding::tei:text[@type = "work_volume"]'):
            return self.make_element('hr')
            # TODO: section_teaser + teaser anchor

    def transform_title(self, node):
        return self.transform_name(node)

    def transform_titlepage(self, node):
        tp_class = 'titlepage'
        if exists(node, 'preceding-sibling::tei:titlePage'):
            tp_class = 'titlepage-sec'
        return self.passthru_append(node, self.make_element_with_class('div', tp_class))
        # TODO css

    def transform_titlepart(self, node):
        if node.get('type') == 'main':
            return self.passthru_append(node, self.make_element('h1'))
        else:
            return self.passthru(node)

    def transform_unclear(self, node):
        unclear = self.make_element_with_class('span', 'unclear')
        if exists(node, 'descendant::text()'):
            return self.passthru_append(node, unclear)
        else:
            return unclear
        # TODO css, i18n

    # TODO
    #  - make sure every function returns content, if required

    # UTIL FUNCTIONS

    def transform_node_to_link(self, node: etree._Element, uri: str):
        """
        Transforms a $node into an HTML link anchor (a[@href]). Prevents child::tei:pb from occurring within the link, if required.
        """
        if not exists(node, 'child::tei:pb'):
            a = self.make_a_with_href(uri, True)
            return self.passthru_append(node, a)
        else:
            # make an anchor for the preceding part, then render the pb, then "continue" the anchor
            # note that this currently works only if pb occurs at the child level, and only with the first pb
            before_children = self.dispatch_multiple(node.xpath('child::tei:pb[1]/preceding-sibling::node()', namespaces=xml_ns))
            before = self.transform_append_children(self.make_a_with_href(uri, True), before_children)
            page_break = self.dispatch(node.xpath('child::tei:pb[1]', namespaces=xml_ns)[0])
            after_children = self.dispatch_multiple(node.xpath('child::tei:pb[1]/following-sibling::node()', namespaces=xml_ns))
            after = self.transform_append_children(self.make_a_with_href(uri, True), after_children)
            return [before, page_break, after]

    def make_a_with_href(self, href_value, target_blank=True):
        a = etree.Element('a')
        a.set('href', href_value)
        if target_blank:
            a.set('target', '_blank')
        return a

    # TODO: testing, esp. from 1st "elif" onwards
    def make_uri_from_target(self, node, targets):
        target = targets.split()[0] # if there are several, first one wins
        work_scheme = r'(work:(W[A-z0-9.:_\-]+))?#(.*)' # TODO is this failsafe?
        facs_scheme = r'facs:((W[0-9]+)[A-z0-9.:#_\-]+)'
        generic_scheme = r'(\S+):([A-z0-9.:#_\-]+)'
        uri = target
        if target.startswith('#'):
            # target is some node in the current work
            targeted = get_target_node(node, id=target[1:])
            if len(targeted) == 1:
                uri = self.make_citetrail_uri_from_xml_id(get_xml_id(targeted[0]))
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
                    uri = self.make_citetrail_uri_from_xml_id(anchor_id)
        elif re.match(facs_scheme, target):
            # target is a facs string
            target_work_id = re.sub(facs_scheme, '$2', target)
            if target_work_id == self.config.wid: # TODO: workaround for dynamic config
                # facs is in the same work
                pb = node.xpath('ancestor::tei:TEI//tei:pb[@facs = "' + target + '"'
                                + ' and not(@sameAs or @corresp) and @xml:id]', namespaces=xml_ns)
                if len(pb) > 0:
                    uri = self.make_citetrail_uri_from_xml_id(get_xml_id(pb[0]))
            else:
                raise TEIMarkupError('@target refers to @facs from a different work than the current one')
        elif re.match(generic_scheme, target):
            # use the general replacement mechanism as defined by the teiHeader's prefixDef
            prefix = re.sub(generic_scheme, '$1', target)
            value = re.sub(generic_scheme, '$2', target)
            prefix_def = self.config.get_prefix_defs().get(prefix)
            if prefix_def:
                if re.match(prefix_def['matchPattern'], value):
                    uri = re.sub(prefix_def['matchPattern'], prefix_def['replacementPattern'], value)
            else:
                search = re.search(generic_scheme, target)
                uri = re.sub(generic_scheme, '$0', target)  # TODO is this working?
        return uri

    def make_citetrail_uri_from_xml_id(self, id: str):
        """
        Tries to derive the citetrail for a node from its @xml:id. Works only if the node/@xml:id is in work "config.wid"
        """
        citetrail = self.config.get_citetrail_mapping(id)
        if citetrail:
            print('Deriving citetrail ' + citetrail + ' from xml:id ' + id)
            return id_server + '/texts/' + self.config.wid + ':' + citetrail
        else:
            return ''

    def facs_to_uri(self, pb_facs):
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

    def transform_orig_elem(self, node):
        if exists(node, 'parent::tei:choice'):
            edit_elem = node.xpath('parent::tei:choice/*[self::tei:expan or self::tei:reg or self::tei:corr]',
                                   namespaces=xml_ns)[0]
            edit_str = txt_dispatch(edit_elem, 'edit')
            span = self.make_element_with_class('span', orig_class + ' ' + etree.QName(node).localname)
            span.set('title', edit_str)
            return self.passthru_append(node, span)
        else:
            return self.passthru(node)

    def make_marginal(self, node):
        note = self.make_element_with_class('div', 'marginal')
        note.set('id', get_xml_id(node))
        if node.get('n'):
            label = self.make_element_with_class('span', 'marginal-label')
            label.text = node.get('n')
            note.append(label)
        if exists(node, 'tei:p'):
            return self.passthru_append(node, note)
        else:
            p_note = self.make_element_with_class('span', 'p-note')
            note.append(self.passthru_append(node, p_note))
            return note

    def make_marginal_inline(self, node):
        # make an empty anchor for referencing purposes
        inline_marg = self.make_element_with_class('span', 'marginal')
        inline_marg.set('id', get_xml_id(node))
        return inline_marg

    def make_element(self, elem_name):
        return etree.Element(elem_name)

    def make_element_with_class(self, elem_name, class_name):
        el = etree.Element(elem_name)
        el.set('class', class_name)
        return el