import re
import argparse

from lxml import etree


class IniToXml():
    def __init__(self):
        self.side = b'client'
        self.regex_header = re.compile(b"""(?xi)
            ^[\s\t\r\n]*
            (?P<opt_code>[0-9a-f]{2,8})
            =
            (?P<header>[a-z][a-z0-9]*)
            :?
            (?P<body>.*)
        """)
        self.regex_body = re.compile(b"""(?xi)
            (?P<type>[a-z0-9-])
            \(
            (?P<name>[a-z0-9:.-_]+)
            \)
        """)
        self.regex_body_loop = re.compile(b"""(?xi) # :Loop.01.0001
            ^
            (?P<name>[a-z0-9:.-_]+?)
            :Loop.
            (?P<skip>\d{2}).
            (?P<loop>\d{4})
            $
        """)
        self.regex_complexity = re.compile(b"""(?xi)
            .*?s\(
            |
            .*?:Loop.
        """)
        self.ctypes_to_numpy = {
            b'b': b'i1',
            b'c': b'i1',
            b'B': b'u1',
            b'h': b'i2',
            b'H': b'u2',
            b'z': b'i4',
            b'd': b'i4',
            b'i': b'i4',
            b'l': b'i4',
            b'I': b'u4',
            b'L': b'u4',
            b'o': b'i4',
            b'd': b'i4',
            b'q': b'i8',
            b'Q': b'u8',
            b'f': b'f8',
            b's': b'|S', # UTF-16-LE string
            b'-': b'|S', # byte string
        }

    # header - replace cames style - > underscore
    @staticmethod
    def camel(s):
        if s == b':':
            return b'U'
        return s  #.lower()

    def element_append_loop(self, cursor, element_loop, primitive):
        el = element_loop.groupdict()
        skip = int(el['skip']) - 1
        loop = int(el['loop'])
        element = etree.SubElement(cursor, '{la2}loop',
            name=self.camel(el['name']),
            type=primitive[0],
            skip=str(skip).encode('utf-8'),
            loop=str(loop).encode('utf-8'),
        )
        return element, loop, skip

    def element_append_primitive(self, cursor, primitive):
        return etree.SubElement(cursor, '{la2}primitive',
            name=primitive[1],
            type=primitive[0])


    def element_append(self, cursor, primitive, loop, skip):
        element_loop = self.regex_body_loop.match(primitive[1])
        if element_loop:
            chield, loop, skip = self.element_append_loop(
                              cursor, element_loop, primitive)
            cursor = chield
        else:
            chield = self.element_append_primitive(cursor, primitive)
        return cursor, loop, skip


    def xml_body(self, primitives, root):
        cursor = root
        loop = 0
        skip = 0
        skipped = False
        loop_primitives = []
        skip_primitives = []
        primitives.reverse()
        primitive_names = []
        while primitives:
            primitive = primitives.pop()

            if skip:
                skip -= 1
                skip_primitives.append(primitive)
                if not skip:
                    element_skip = etree.SubElement(cursor, '{la2}skip',
                        # skip=cursor.attrib['skip'].encode('utf-8'),
                    )
                    self.xml_body(skip_primitives, element_skip)
                    skip_primitives = []
                    skipped = True
            elif loop:
                loop -= 1
                loop_primitives.append(primitive)
                if not loop:
                    if skipped:
                        element_loop = etree.SubElement(cursor, '{la2}loop',
                            # loop=cursor.attrib['loop'].encode('utf-8'),
                        )
                        self.xml_body(loop_primitives, element_loop)
                    else:
                        self.xml_body(loop_primitives, cursor)
                    loop_primitives = []
                    cursor = cursor.getparent()
                    skipped = False
            else:
                t = primitive[0]
                if primitive[0] == b'-':
                    t = b''.join([self.ctypes_to_numpy[primitive[0]], primitive[1]])
                else:
                    t = self.ctypes_to_numpy[primitive[0]]

                primitive_name = self.camel(primitive[1])
                while primitive_name in primitive_names:
                    primitive_name = b"".join([primitive_name, b"_"])

                primitive_names.append(primitive_name)
                cursor, loop, skip = self.element_append(
                    cursor, [t, primitive_name], loop, skip)
        if skip or loop:
            raise PacketCompileException("wrong ini body")


    def convert_one_line(self, line_in, root):
        try:
            d = self.regex_header.match(line_in).groupdict() #
        except:
            return 
        opt_code, header, body = d['opt_code'], d['header'], d['body']
        primitives = self.regex_body.findall(body) # list(type, name)
        if self.regex_complexity.match(body):
            complexity = b"complex"
        else:
            complexity = b"simple"
        
        line_root = etree.SubElement(root, '{la2}pck_struct',
            pck_name=b''.join([self.side[0:1], b'_', self.camel(header)]),
            side=self.side,
            opt_code=opt_code,
            complexity=complexity,
            name=b'pck_type',
            type=b'i1')
        self.xml_body(primitives, line_root)
        return


    def convert(self, list_in):
        xml_out = b''
        root = etree.Element('root', nsmap={'la2': 'la2'})
        tree = etree.ElementTree(root)
        line_n = 0

        for line in list_in:
            line_n += 1
            if isinstance(line, str):
                line = line.encode('utf8')

            if line.startswith(b'//'):
                pass
            elif line.lower().startswith(b'[server]'):
                self.side = b'server'
            elif line.lower().startswith(b'[client]'):
                self.side = b'client'
            elif line:
                try:
                    self.convert_one_line(line, root)
                except Exception as e:
                    err = b"".join([b"compile error, line: ",
                        line[:80], b", line number: ",
                        str(line_n).encode('latin-1')]).decode('latin-1')
                    err = "\n".join([e.value, err])
                    raise PacketCompileException(err)
            else:
                pass

        xml_out = etree.tostring(tree, encoding='ASCII', xml_declaration=True,
            pretty_print=True)
        return xml_out


    def convert_file(self, file_in, file_out):
        with open(file_out, "wb") as f_out:
            pass
        with open(file_in, 'rU') as f_in:
            with open(file_out, "ab") as f_out:
                xml_out = self.convert(f_in)
                f_out.write(xml_out)


class PacketCompileException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def agrparser():
    parser = argparse.ArgumentParser(
        description=' convert la2 packets.ini to xml ')
    parser.add_argument("--fi", dest='f_in',
        type=str, required=True, help='ini file')
    parser.add_argument("--fo", dest='f_out',
        type=str, help='xml file')
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = agrparser()
    initoxml = IniToXml()
    if not args.f_out:
        initoxml.convert_file(args.f_in, args.f_in[:args.f_in.find(".ini")]+".xml")
    else:
        initoxml.convert_file(args.f_in, args.f_out)