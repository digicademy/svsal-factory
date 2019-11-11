
# mappings for deriving the correct filename for a given doc_id
doc_id_filenames = {
    'guidelines': 'works-general',
    'sources': 'sources-list',
    'chars': 'specialchars',
    'team': 'projectteam',
    'faq': 'works-faq'
}

class DocConfig:

    tei_docs_path = 'tests/resources/in/svsal-tei/revision'  # TODO

    def __init__(self, did: str, node_count=0):
        self.node_mappings = {}
        self.did = did
        self.node_count = node_count
        self.cite_depth = 0

    def get_cite_depth(self):
        return self.cite_depth

    def set_cite_depth(self, value):
        self.cite_depth = value

    def get_node_mappings(self):
        return self.node_mappings

    def get_citetrail_mapping(self, xml_id):
        if self.node_mappings.get(xml_id) and self.node_mappings.get(xml_id).get('citetrail'):
            return self.node_mappings[xml_id]['citetrail']

    def put_citetrail_mapping(self, xml_id, citetrail):
        if not self.node_mappings.get(xml_id):
            self.node_mappings[xml_id] = {}
        self.node_mappings[xml_id]['citetrail'] = citetrail
