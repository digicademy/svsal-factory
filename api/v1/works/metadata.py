from lxml import etree
from api.v1.works.config import id_server
from api.v1.xutils import xml_ns, exists
from api.v1.works.config import WorkConfig
from api.v1.works.analysis import WorkAnalysis

context = {
    '@vocab': 'https://www.w3.org/ns/hydra/core#',
    'dc': 'http://purl.org/dc/terms/',
    'dts': 'https://w3id.org/dts/api#',
    'sal': 'https://api.salamanca.school/' # TODO point to an actual reference document here
}

class WorkMetadataTransformer:

    def __init__(self, config: WorkConfig, analysis: WorkAnalysis):
        self.config = config
        self.analysis = analysis

    def make_passage_metadata(self, sal_node: etree._Element, config):
        passage_metadata = {}
        passage_metadata['@id'] = sal_node.get('citetrail')
        if sal_node.get('citetrailParent'):
            passage_metadata['up'] = sal_node.get('citetrailParent')
        if sal_node.get('prev'):
            passage_metadata['prev'] = config.get_citetrail_mapping(sal_node.get('prev'))
        if sal_node.get('next'):
            passage_metadata['next'] = config.get_citetrail_mapping(sal_node.get('next'))
        passage_metadata['dts:citeDepth'] = int(config.get_cite_depth())
        passage_metadata['dts:level'] = int(sal_node.get('level'))
        if sal_node.get('member'):
            member = []
            for member_id in sal_node.get('member').split(';'):
                member_citetrail = config.get_citetrail_mapping(member_id)
                member.append({'dts:ref': member_citetrail})
            passage_metadata['member'] = member
        passage_metadata['dts:citeType'] = sal_node.get('citeType')
        return passage_metadata
        # TODO sal:passage(trail)
        # first? last?
        # dts:citeType? sal:extensions?

        # dts:passage: to be added downstream; @id: set dynamically based on request data

    def make_resource_metadata(self, tei_header: etree._Element, config, wid: str):
        """Translates data from the teiHeader of a work to DTS+DC metadata for a DTS textual Resource"""

        # 1.) gather metadata
        # a) digital edition
        id = id_server + '/texts/' + config.get_wid()
        # TODO @id shouldn't be the same as the @id of the parent collection, but sth more specific
        title = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:title[@type = "short"]/text()', namespaces=xml_ns)[0]
        alt_title = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:title[@type = "main"]/text()', namespaces=xml_ns)[0]  # or short title here?
        author = '; '.join(self.format_person_names(tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:author/tei:persName',
                                                      namespaces=xml_ns), reverse=False))
        scholarly_editors = self.format_person_names(tei_header.xpath('tei:fileDesc/tei:titleStmt/' +
                                                                 'tei:editor[contains(@role, "#scholarly")]/tei:persName',
                                                                 namespaces=xml_ns))
        technical_editors = self.format_person_names(tei_header.xpath('tei:fileDesc/tei:titleStmt/' +
                                                                 'tei:editor[contains(@role, "#technical")]/tei:persName',
                                                                 namespaces=xml_ns))
        editors = list(set(scholarly_editors + technical_editors))
        pub_date = self.get_publish_date(tei_header)
        version = tei_header.xpath('tei:fileDesc/tei:editionStmt/tei:edition/@n', namespaces=xml_ns)[0]
        series_volume = tei_header.xpath('tei:fileDesc/tei:seriesStmt/tei:biblScope[@unit = "volume"]/@n',
                                         namespaces=xml_ns)[0]
        rights_holder = {
            '@id': 'https://id.salamanca.school',
            'name': {
                '@language': 'en',
                '@value': 'The School of Salamanca'
            }
        }  # TODO provisional values
        bibliographic_citation = self.make_bibliographic_citations(tei_header, wid)

        # b) print source
        source_title = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/tei:title[@type = "main"]/text()',
                                        namespaces=xml_ns)[0]
        source_publishers = self.format_person_names(self.get_source_publishers(tei_header), reverse=False)
        source_extents = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/tei:extent',
                                          namespaces=xml_ns)
        source_extents_i18n = []
        for extent in source_extents:
            if exists(extent, '@xml:lang'):
                extent_i18n = {
                    '@language': extent.xpath('@xml:lang', namespaces=xml_ns)[0],
                    '@value': extent.xpath('text()')[0]
                }
                source_extents_i18n.append(extent_i18n)
            else:
                source_extents_i18n.append(extent.xpath('text()')[0])
        source_lang = []
        for lang in tei_header.xpath('tei:profileDesc/tei:langUsage/tei:language/@ident', namespaces=xml_ns):
            source_lang.append(lang)
        source_pub_date = self.get_source_publish_date(tei_header)
        source_pub_place = self.get_source_publish_place(tei_header)
        source_repositories = self.get_source_repositories(tei_header)

        # c) other dts metadata
        total_items = 0 # TODO
        dts_total_children = 0  # TODO
        dts_total_parents = 1  # resource is part only of the parent collection that represents the work
        dts_cite_depth = config.get_cite_depth() # TODO multivol vs singlevol?

        # 2.) construct metadata object
        resource_metadata = {
            '@context': context,
            '@id': id,
            '@type': 'Resource',
            'title': title,
            'totalItems': total_items,
            'dts:totalParents': dts_total_parents,
            'dts:totalChildren': dts_total_children,
            'dts:citeDepth': dts_cite_depth,
            'dts:dublincore': {
                'dc:title': title,
                'dc:alternative': alt_title,
                'dc:contributor': editors,  # TODO editors as "contributors"? information can be found also in sal:...Editors
                'dc:type': [
                    'http://purl.org/spar/fabio/work',
                    'dc:Text'
                ],
                'dc:created': pub_date,
                'dc:bibliographicCitation': bibliographic_citation,
                'dc:rightsHolder': rights_holder,
                'dc:license': 'http://creativecommons.org/licenses/by/4.0/',
                'dc:source': {
                    'dc:title': source_title,
                    'dc:creator': author,
                    'dc:publisher': source_publishers,
                    'dc:format': source_extents_i18n,
                    'dc:language': source_lang,
                    'dc:created': source_pub_date
                }
            },
            'dts:extensions': {  # supplementary information that doesn't easily fit into dts/dc elements
                'sal:version': version,  # the version of this edition of the text
                'sal:scholarlyEditors': scholarly_editors,
                'sal:technicalEditors': technical_editors,
                # omitting "#additional" editors here
                'sal:seriesVolume': series_volume,
                'sal:sourcePublishPlace': source_pub_place,  # there seem to be no dc elements for this type of information...
                'sal:sourceRepositories': source_repositories
            }
        }
        return resource_metadata
        # TODO/questions:
        #  - dealing with unpublished works
        #  - single volumes of multivolume works (dc:hasPart for volumes? @id of volumes)
        #  - root collection: automatically update when single work is processed, or should it have its own endpoint?
        #  - dts:references
        #  - dts:passage
        #  - dts:citeStructure (?)
        #  - series editors?
        #  - dc:isFormatOf/dc:hasFormat?
        #  - additional/better values for dc:type?
        #  - https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#terms-tableOfContent for TOC?
        #  - specify that we use iso639-1 for language codes? e.g., http://www.lexvo.org/page/iso639-1/la

    def make_work_collection_metadata(self, tei_header: etree._Element):
        """Produces metadata for a DTS collection representing a single work or a (multivolume work's) volume."""
        pass

    def make_multivolume_work_collection_metadata(self, tei_header: etree._Element):
        """Produces metadata for a DTS (child) collection containing multiple 'works' (i.e., volumes). This can only be
        used for creating metadata for a multivolume work, where each member is the collection for a single volume (see
        make_work_collection_metadata)."""
        pass

    def make_root_collection_metadata(self):
        """Produces metadata for the DTS root collection that represents the corpus (i.e., the Digital Collection of Sources).
        Each member is either a collection for a multivolume work (see make_multivolume_work_collection_metadata) that
        contains multiple child collections representing the single volumes, or a collection representing a single-volume
        work (see make_work_collection_metadata)."""
        pass

    # UTIL FUNCTIONS FOR EXTRACTION OF METADATA

    def make_bibliographic_citations(self, tei_header: etree._Element, wid: str):
        author_surname = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:author/tei:persName/tei:surname/text()',
                                          namespaces=xml_ns)[0]
        title = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:title[@type = "short"]/text()', namespaces=xml_ns)[0]
        publish_year = tei_header.xpath('tei:fileDesc/tei:editionStmt/tei:edition/' +
                                        'tei:date[@type = "digitizedEd" or @type = "summaryDigitizedEd"]/@when',
                                        namespaces=xml_ns)[0][:4]  # getting year only
        source_this_publish_year = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                                 'tei:imprint/tei:date[@type = "thisEd"]/@when', namespaces=xml_ns)
        source_first_publish_year = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                                'tei:imprint/tei:date[@type = "firstEd"]/@when', namespaces=xml_ns)
        # assuming here that work_multivolume also have a date[@type = "firstEd|thisEd"], additional to their summary...Ed
        source_publish_year = source_first_publish_year[0]
        if len(source_this_publish_year):
            source_publish_year = source_this_publish_year[0]
        link = id_server + '/texts/' + wid
        bibliographic_citations = []
        for series_title in tei_header.xpath('tei:fileDesc/tei:seriesStmt/tei:title[@level = "s"]', namespaces=xml_ns):
            lang = series_title.xpath('@xml:lang', namespaces=xml_ns)[0]
            citation = author_surname + ', ' + title + '(' + publish_year + '[' + source_publish_year + ']), ' \
                       + series_title.text + ' <' + link + '>'
            citation_obj = {'@language': lang, '@value': citation}
            bibliographic_citations.append(citation_obj)
        return bibliographic_citations

    def get_source_repositories(self, tei_header: etree._Element):
        repositories = []
        for ms_identifier in tei_header.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/' +
                                              'tei:msDesc/tei:msIdentifier', namespaces=xml_ns):
            lang = ms_identifier.xpath('tei:repository/@xml:lang', namespaces=xml_ns)[0]
            name = ms_identifier.xpath('tei:repository/text()', namespaces=xml_ns)[0]
            link = ms_identifier.xpath('tei:idno[@type = "catlink"]/text()', namespaces=xml_ns)[0]
            repo = {
                'owner': {'@language': lang, '@value': name}, # TODO lod ID
                'link': link
            }
            repositories.append(repo)
        return repositories

    def get_publish_date(self, tei_header: etree._Element):
        range = tei_header.xpath('tei:fileDesc/tei:editionStmt/tei:edition/tei:date[@type = "summaryDigitizedEd"]',
                                 namespaces=xml_ns)
        date = tei_header.xpath('tei:fileDesc/tei:editionStmt/tei:edition/tei:date[@type = "digitizedEd"]/text()',
                                namespaces=xml_ns)
        if len(range):
            return self.get_publish_date_range(range[0])
        else:
            return date[0]

    def get_source_publish_date(self, tei_header: etree._Element):
        this_range = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                      'tei:imprint/tei:date[@type = "summaryThisEd"]', namespaces=xml_ns)
        first_range = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                       'tei:imprint/tei:date[@type = "summaryFirstEd"]', namespaces=xml_ns)
        this_date = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                     'tei:imprint/tei:date[@type = "thisEd"]/@when', namespaces=xml_ns)
        first_date = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                      'tei:imprint/tei:date[@type = "firstEd"]/@when', namespaces=xml_ns)
        if len(this_range):
            return self.get_publish_date_range(this_range[0])
        elif len(first_range):
            return self.get_publish_date_range(first_range[0])
        if len(this_date):
            return int(this_date[0][:4]) # assuming format like yyyy-mm-dd
        else:
            return int(first_date[0][:4])

    def get_publish_date_range(self, date: etree._Element):
        if exists(date, '@from'):
            date = {'start': date.xpath('@start')[0]}
            if exists(date, '@to'):
                date['to'] = date.xpath('@to')[0]
            return date
        else:
            return date.xpath('text()')[0]

    def get_source_publishers(self, tei_header: etree._Element):
        this_publishers = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                           'tei:imprint/tei:publisher[@n = "firstEd"]/tei:persName',
                                           namespaces=xml_ns)
        first_publishers = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                            'tei:imprint/tei:publisher[@n = "firstEd"]/tei:persName',
                                            namespaces=xml_ns)
        if len(this_publishers):
            return this_publishers
        else:
            return first_publishers

    def get_source_publish_place(self, tei_header: etree._Element):
        this_place = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                      'tei:imprint/tei:pubPlace[@role = "thisEd"]', namespaces=xml_ns)
        first_place = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                       'tei:imprint/tei:pubPlace[@role = "firstEd"]', namespaces=xml_ns)
        if len(this_place):
            return self.get_place_name(this_place[0])
        else:
            return self.get_place_name(first_place[0])

    def get_place_name(self, place_name: etree._Element):
        if exists(place_name, '@key'):
            return place_name.get('key')
        else:
            return place_name.text

    def format_person_names(self, person_names, reverse=False):
        """
        From each tei:name/tei:persName/... in person_names, extracts a full name of the form
        'surname, forename [name link] [& additional name]' or (if reverse=True) 'forename [name link] surname [<additional name>]'.
        However, if there is an @key, this will be used as the full name.
        """
        names = []
        for person in person_names:
            name = ''
            if exists(person, '@key'):
                name = person.xpath('@key')[0]
            elif exists(person, 'tei:surname and tei:forename'):
                surname = person.xpath('tei:surname/text()', namespaces=xml_ns)[0]
                forename = person.xpath('tei:forename/text()', namespaces=xml_ns)[0]
                name_link = ''
                if exists(person, 'tei:nameLink'):
                    name_link += ' ' + person.xpath('tei:nameLink/text()', namespaces=xml_ns)[0]
                add_name = ''
                if exists(person, 'tei:addName'):
                    if reverse:
                        add_name += ' <' + person.xpath('tei:addName/text()', namespaces=xml_ns)[0] + '>'
                    else:
                        add_name += ' & (' + person.xpath('tei:addName/text()', namespaces=xml_ns)[0] + ')'
                if reverse:
                    name = forename + ' ' + surname + name_link + add_name
                else:
                    name = surname + ', ' + forename + name_link + add_name
            else:
                name = str(person.xpath('string(.)')[0])
            names.append(name)
        return names
