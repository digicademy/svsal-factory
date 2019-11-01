from lxml import etree


def make_resource_metadata(sal_node: etree._Element, config):
    metadata = {}
    metadata['@id'] = sal_node.get('citetrail')
    if sal_node.get('citetrailParent'):
        metadata['up'] = sal_node.get('citetrailParent')
    if sal_node.get('prev'):
        metadata['prev'] = config.get_citetrail_mapping(sal_node.get('prev'))
    if sal_node.get('next'):
        metadata['next'] = config.get_citetrail_mapping(sal_node.get('next'))
    metadata['dts:citeDepth'] = int(config.get_cite_depth())
    metadata['dts:level'] = int(sal_node.get('level'))
    if sal_node.get('member'):
        member = []
        for member_id in sal_node.get('member').split(';'):
            member_citetrail = config.get_citetrail_mapping(member_id)
            member.append({'dts:ref': member_citetrail})
        metadata['member'] = member
    return metadata
    # first? last?
    # dts:citeType? sal:extensions?

    # dts:passage: to be added downstream; @id: set dynamically based on request data


def make_document_metadata(tei_header: etree._Element):
    pass