from lxml import etree
from api.v1.xutils import xml_ns


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


class WorkConfig:
    def __init__(self):
        self.citation_labels = citation_labels
        self.teaser_length = teaser_length
        self.chars = None

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

    def get_citation_labels(self):
        return self.citation_labels