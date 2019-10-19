from lxml import etree


xml_ns = {'xml': 'http://www.w3.org/XML/1998/namespace',
          'tei': 'http://www.tei-c.org/ns/1.0',
          'xi': 'http://www.w3.org/2001/XInclude'}


def flatten(l):
    for el in l:
        if isinstance(el, list) and not isinstance(el, etree._Element):
            yield from flatten(el)
        else:
            yield el


#is_element = etree.XPath('boolean(self::*)') # this throws an error with processing instructions ...

is_comment = etree.XPath('boolean(self::comment())')
is_processing_instruction = etree.XPath('boolean(self::processing-instruction())')


def is_text_node(node): # TODO is ElementStringResult really a simple text node?
    return isinstance(node, etree._ElementStringResult) or \
           isinstance(node, etree._ElementUnicodeResult) or \
           node.xpath('boolean(self::text())')


def is_element(node):
    #return etree.iselement(node) and not isinstance(node, etree._ProcessingInstruction)
    return isinstance(node, etree._Element)


def exists(elem, xpath_expr):
    return elem.xpath('boolean(' + xpath_expr + ')', namespaces=xml_ns)