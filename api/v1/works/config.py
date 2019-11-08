from lxml import etree
from api.v1.xutils import xml_ns


# preliminary path to works TEI until we have svsal-tei online:
tei_works_path = 'tests/resources/in/svsal-tei/works'


# TEMPORARY / DEBUGGING
id_server = 'https://id.salamanca.school'
image_server = 'https://facs.salamanca.school' # TODO

# IIIF
iiif_img_default_params = '/full/full/0/default.jpg' # TODO

tei_text_elements = ('g', 'lb', 'pb', 'cb', 'head', 'p', 'note', 'div', 'milestone', 'choice', 'abbr', 'orig', 'sic',
                      'expan', 'reg', 'corr', 'persName', 'placeName', 'docAuthor', 'orgName', 'pubPlace', 'publisher',
                      'title', 'term', 'bibl', 'hi', 'emph', 'ref', 'quote', 'soCalled', 'list', 'item', 'gloss', 'eg',
                      'birth', 'death', 'lg', 'l', 'signed', 'titlePage', 'titlePart', 'docTitle', 'docDate', 'byline',
                      'imprimatur', 'docImprint', 'label', 'argument', 'damage', 'gap', 'supplied', 'unclear', 'del',
                      'space', 'figure', 'text', 'front', 'body', 'back', 'table', 'row', 'cell', 'foreign', 'date',
                      'cit', 'author', 'docEdition', 'TEI', 'group', 'figDesc', 'teiHeader', 'fw')


citation_labels = {
        # div/@label and milestone/@unit
        'additional': {'full': 'addendum', 'abbr': 'add.', 'isCiteRef': True},
        'administrative': {'full': 'administratio', 'abbr': 'admin.'},
        'article': {'full': 'articulus', 'abbr': 'art.', 'isCiteRef': True},
        'book': {'full': 'liber', 'abbr': 'lib.', 'isCiteRef': True},
        'chapter': {'full': 'capitulum', 'abbr': 'cap.', 'isCiteRef': True},
        'colophon': {'full': 'colophon', 'abbr': 'coloph.', 'isCiteRef': True},
        'commentary': {'full': 'commentarius', 'abbr': 'comment.', 'isCiteRef': True},
        'contained_work': (),
        'contents': {'full': 'tabula', 'abbr': 'tab.', 'isCiteRef': True},
        'corrigenda': {'full': 'corrigenda', 'abbr': 'corr.', 'isCiteRef': True},
        'dedication': {'full': 'dedicatio', 'abbr': 'dedic.', 'isCiteRef': True},
        'disputation': {'full': 'disputatio', 'abbr': 'disp.', 'isCiteRef': True},
        'doubt': {'full': 'dubium', 'abbr': 'dub.', 'isCiteRef': True},
        'entry': (), # 'lemma'?
        'foreword': {'full': 'prooemium', 'abbr': 'pr.', 'isCiteRef': True},
        'gloss': {'full': 'glossa', 'abbr': 'gl.', 'isCiteRef': True},
        'index': {'full': 'index', 'abbr': 'ind.', 'isCiteRef': True},
        'law': {'full': 'lex', 'abbr' :'l.', 'isCiteRef': True},
        'lecture': {'full': 'relectio', 'abbr': 'relect.', 'isCiteRef': True},
        'partida': {'full': 'partida', 'abbr': 'part.', 'isCiteRef': True},
        'map': (),
        'number': {'full': 'numerus', 'abbr': 'num.', 'isCiteRef': True}, # only in milestone
        'part': {'full': 'pars', 'abbr': 'pars', 'isCiteRef': True},
        'preface': {'full': 'praefatio', 'abbr': 'praef.', 'isCiteRef': True},
        'privileges': {'full': 'privilegium', 'abbr': 'priv.', 'isCiteRef': True},
        'question': {'full': 'quaestio', 'abbr': 'q.', 'isCiteRef': True},
        'section': {'full': 'sectio', 'abbr': 'sect.'},
        'segment': {'full': 'sectio', 'abbr': 'sect.', 'isCiteRef': True},
        'source': {'full': 'sectio', 'abbr': 'sect.'},
        'title': {'full': 'titulus', 'abbr': 'tit.', 'isCiteRef': True},
        'unknown': (),
        'work_part': (),
        # other elements: local names
        'back': {'full': 'appendix', 'abbr': 'append.', 'isCiteRef': True},
        'front': {'full': 'front', 'abbr': 'front.'},
        'titlePage': {'full': 'titulus', 'abbr': 'tit.'},
        'pb': {'full': 'pagina', 'abbr': 'pag.', 'isCiteRef': True},
        'p': {'full': 'paragraphus', 'abbr': 'paragr.', 'isCiteRef': True},
        'note': {'full': 'nota', 'abbr': 'not.', 'isCiteRef': True}
    }

teaser_length = 60

orig_class = 'orig'
edit_class = 'edit'


class WorkConfig:
    def __init__(self, wid, node_count=0):
        self.wid = wid
        self.citation_labels = citation_labels
        self.teaser_length = teaser_length
        self.chars = None
        self.prefix_defs = {}
        self.node_mappings = {}
        self.node_count = node_count
        self.cite_depth = 0

    def get_cite_depth(self):
        return self.cite_depth

    def set_cite_depth(self, value):
        self.cite_depth = value

    def get_chars(self):
        return self.chars

    def set_chars(self, char_decl):
        chars = {}
        for char in char_decl.xpath('tei:char', namespaces=xml_ns):
            id = char.xpath('@xml:id', namespaces=xml_ns)[0]
            mappings = {}
            for mapping in char.xpath('tei:mapping', namespaces=xml_ns):
                mappings[mapping.get('type')] = mapping.text
            chars[id] = mappings
        self.chars = chars

    def get_prefix_defs(self):
        return self.prefix_defs

    def set_prefix_def(self, prefix_def: etree._Element):
        this_def = {}
        ident = prefix_def.get('ident')
        this_def['matchPattern'] = prefix_def.get('matchPattern')
        this_def['replacementPattern'] = prefix_def.get('replacementPattern')
        self.prefix_defs[ident] = this_def

    def get_node_mappings(self):
        return self.node_mappings

    def get_citetrail_mapping(self, xml_id):
        if self.node_mappings.get(xml_id) and self.node_mappings.get(xml_id).get('citetrail'):
            return self.node_mappings[xml_id]['citetrail']

    def get_passagetrail_mapping(self, xml_id):
        if self.node_mappings.get(xml_id) and self.node_mappings.get(xml_id).get('passagetrail'):
            return self.node_mappings[xml_id]['passagetrail']

    def put_citetrail_mapping(self, xml_id, citetrail):
        if not self.node_mappings.get(xml_id):
            self.node_mappings[xml_id] = {}
        self.node_mappings[xml_id]['citetrail'] = citetrail

    def put_passagetrail_mapping(self, xml_id, passagetrail):
        if not self.node_mappings.get(xml_id):
            self.node_mappings[xml_id] = {}
        self.node_mappings[xml_id]['passagetrail'] = passagetrail

    def get_citation_labels(self):
        return self.citation_labels

    def get_wid(self):
        return self.wid