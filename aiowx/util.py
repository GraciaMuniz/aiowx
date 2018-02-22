import hashlib
import random
import string
import xml.etree.ElementTree as ElementTree


def gen_sign(to_signed, api_key):
    keys = sorted(to_signed.keys())
    tmp_list = []
    for key in keys:
        if key == 'sign':
            continue
        value = to_signed[key]
        if not value:
            continue
        tmp_list.append('{}={}'.format(key, value))
    to_hash = '&'.join(tmp_list)
    to_hash += '&key={}'.format(api_key)
    return hashlib.md5(to_hash.encode()).hexdigest().upper()


def gen_sign_sha1(to_signed):
    keys = sorted(to_signed.keys())
    tmp_list = []
    for key in keys:
        if key == 'sign':
            continue
        value = to_signed[key]
        if not value:
            continue
        tmp_list.append('{}={}'.format(key, value))
    to_hash = '&'.join(tmp_list)
    return hashlib.sha1(to_hash.encode()).hexdigest()


ALPHABET = string.digits + string.ascii_letters


def gen_nonce():
    return ''.join(random.sample(ALPHABET, 32))


def dict_to_xml(d):
    root = ElementTree.Element('xml')
    for k in d:
        v = d[k]
        child = ElementTree.SubElement(root, k)
        child.text = str(v)
    return ElementTree.tostring(root, encoding='unicode')


def xml_to_dict(xml):
    root = ElementTree.fromstring(xml)
    result = {}
    for child in root:
        tag = child.tag
        text = child.text
        result[tag] = text
    return result
