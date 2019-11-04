from lxml import etree
from api.v1.works.config import id_server
from api.v1.xutils import xml_ns, exists

context = {
    '@vocab': 'https://www.w3.org/ns/hydra/core#',
    'dc': 'http://purl.org/dc/terms/',
    'dts': 'https://w3id.org/dts/api#',
}


def make_passage_metadata(sal_node: etree._Element, config):
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
    return passage_metadata
    # TODO sal:passage(trail)
    # first? last?
    # dts:citeType? sal:extensions?

    # dts:passage: to be added downstream; @id: set dynamically based on request data


def make_resource_metadata(tei_header: etree._Element, config):
    """Translates data from the teiHeader of a work to DTS+DC metadata for a DTS textual Resource"""

    # 1.) gather metadata
    # a) digital edition
    id = id_server + '/texts/' + config.get_wid()
    # TODO @id shouldn't be the same as the @id of the parent collection, but sth more specific
    title = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:title[@type = "short"]', namespaces=xml_ns)[0]
    alt_title = tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:title[@type = "main"]', namespaces=xml_ns)[0]  # or short title here?
    author = '; '.join(format_person_names(tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:author/tei:persName',
                                                  namespaces=xml_ns), reverse=False))
    editors = format_person_names(tei_header.xpath('tei:fileDesc/tei:titleStmt/tei:editor/tei:persName',
                                                   namespaces=xml_ns))
    # TODO this currently makes no difference between scholarly, technical, and additional editors
    pub_date = get_publish_date(tei_header)

    # b) print source
    source_title = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/tei:title[@type = "main"]/text()',
                                    namespaces=xml_ns)[0]
    source_publishers = format_person_names(get_source_publishers(tei_header), reverse=False)
    source_extents = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/tei:extent',
                                      namespaces=xml_ns)
    source_extents_i18n = []
    for extent in source_extents:
        if exists(extent, '@xml:lang'):
            extent_i18n = {
                '@language': extent.xpath('@xml:lang/string()', namespaces=xml_ns)[0],
                '@value': extent.xpath('text()')[0]
            }
            source_extents_i18n.append(extent_i18n)
        else:
            source_extents_i18n.append(extent.xpath('text()')[0])
    source_lang = []
    for lang in tei_header.xpath('tei:profileDesc/tei:langUsage/tei:language/@ident/string()', namespaces=xml_ns):
        source_lang.append(lang)
    source_pub_date = get_source_publish_date(tei_header)

    # c) other dts metadata
    total_items = 0  # there are no members
    dts_total_parents = 1  # resource is part only of the parent collection that represents the work

    # 2.) construct metadata object
    resource_metadata = {
        '@context': context,
        '@id': id,
        '@type': 'Resource',
        'title': title,
        'dts:dublincore': {
            'dc:title': title,
            'dc:alternative': alt_title,
            'dc:contributor': editors,  # TODO editors simply as "contributors"?
            'dc:type': [
                'http://purl.org/spar/fabio/work',
                'dc:Text'
            ],
            'dc:created': pub_date,
            'dc:source': {
                'dc:title' : source_title,
                'dc:creator': author,
                'dc:publisher': source_publishers,
                'dc:format': source_extents_i18n,
                'dv:language': source_lang,
                'dc:created': source_pub_date
            }
        }
    }
    # dc:hasPart for volumes? @id of volumes
    return resource_metadata
    # TODO:
    #  - publish place - is there
    #  - hasVersion for expressing the version of this dig. edition
    #  - dc:isFormatOf/dc:hasFormat?
    #  - creator/publisher on top level as well?
    #  - additional/better values for dc:type?
    #  - https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#terms-tableOfContent for TOC?
    #  - specify that we use iso639-1 for language codes? e.g., http://www.lexvo.org/page/iso639-1/la


    pass


def make_collection_metadata():
    pass



# UTIL FUNCTIONS FOR EXTRACTION OF METADATA


def get_publish_date(tei_header: etree._Element):
    range = tei_header.xpath('tei:fileDesc/tei:publicationStmt/tei:date[@type = "summaryDigitizedEd"]')
    date = tei_header.xpath('tei:fileDesc/tei:publicationStmt/tei:date[@type = "digitizedEd"]')
    if len(range):
        return get_publish_date_range(range[0])
    else:
        return date[0]


def get_source_publish_date(tei_header: etree._Element):
    this_range = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                  'tei:imprint/tei:date[@type = "summaryThisEd"]', namespaces=xml_ns)
    first_range = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                   'tei:imprint/tei:date[@type = "summaryFirstEd"]', namespaces=xml_ns)
    this_date = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                 'tei:imprint/tei:date[@type = "thisEd"]/@when/string()', namespaces=xml_ns)
    first_date = tei_header.xpath('tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:monogr/' +
                                  'tei:imprint/tei:date[@type = "firstEd"]/@when/string()', namespaces=xml_ns)
    if len(this_range):
        return get_publish_date_range(this_range[0])
    elif len(first_range):
        return get_publish_date_range(first_range[0])
    if len(this_date):
        return int(this_date[0][:4]) # assuming format like yyyy-mm-dd
    else:
        return int(first_date[0][:4])


def get_publish_date_range(date: etree._Element):
    if exists(date, '@from'):
        date = {'start': date.xpath('@start/string()')[0]}
        if exists(date, '@to'):
            date['to'] = date.xpath('@to/string()')[0]
        return date
    else:
        return date.xpath('text()')[0]


def get_source_publishers(tei_header: etree._Element):
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


def format_person_names(person_names, reverse=False):
    """
    From each tei:name/tei:persName/... in person_names, extracts a full name of the form
    'surname, forename [name link] [& additional name]' or (if reverse=True) 'forename [name link] surname [<additional name>]'.
    However, if there is an @key, this will be used as the full name.
    """
    names = []
    for person in person_names:
        name = ''
        if exists(person, '@key'):
            name = person.xpath('@key/string()')[0]
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
