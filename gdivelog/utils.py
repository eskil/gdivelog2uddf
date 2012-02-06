"""
Utilities and constants
"""

__all__ = ['celcius_to_kelvin', 'celcius_to_fahrenheit', 'xml_add']
__author__ = "Eskil Heyn <eskil@eskil.org>"
__maintainer__ = "Eskil Olsen <eskil@eskil.org>"
__copyright__ = "Copyright 2011"
__license__ = "Public Domain"
__version__ = "1.0"
__status__ = "Production"


def celcius_to_kelvin(celcius):
    '''Convert a temperature from C to K'''
    return celcius + 273.15;


def celcius_to_fahrenheit(celcius):
    '''Convert a temperature from C to F'''
    return ((celcius * 9) / 5) + 32


def xml_add(top, node, tag, text=None, subfields={}, attr={}):
    """
    Helper method to add data to an XML file.

    Args;
       top -- the root for the document
       node -- the node at which to attach the tag under
       tag -- the tag to add
       text -- optional text field for the tag
       subfields -- dictionary of subfields to add, where the key will be the tag name and the value will be the text.
       attr -- dictionary of attributes to add as key=val elements.

    Returns;
       the created element
    """
    element = top.createElement(tag)

    for k, v in attr.iteritems():
        element.setAttribute(k, '%r' % v)

    if text is not None:
        textelement = top.createTextNode('%s' % text)
        element.appendChild(textelement)

    node.appendChild(element)

    for k, v in subfields.iteritems():
        xml_add(top, element, k, text=v)

    return element
