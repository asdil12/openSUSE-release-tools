#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2017 SUSE Linux GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import logging
import sys
import urllib2
import re
from xml.etree import cElementTree as ET

import osc.conf
import osc.core

from osc import oscerr

OPENSUSE = 'openSUSE:Leap:15.0'
SLE = 'SUSE:SLE-15:GA'

makeurl = osc.core.makeurl
http_GET = osc.core.http_GET
http_POST = osc.core.http_POST

class CompareList(object):
    def __init__(self, old_prj, new_prj, verbose, newonly):
        self.new_prj = new_prj
        self.old_prj = old_prj
        self.verbose = verbose
        self.newonly = newonly
        self.apiurl = osc.conf.config['apiurl']
        self.debug = osc.conf.config['debug']

    def get_source_packages(self, project):
        """Return the list of packages in a project."""
        query = {'expand': 1}
        root = ET.parse(http_GET(makeurl(self.apiurl, ['source', project],
                                 query=query))).getroot()
        packages = [i.get('name') for i in root.findall('entry')]

        return packages

    def is_linked_package(self, project, package):
        u = makeurl(self.apiurl, ['source', project, package])
        root = ET.parse(http_GET(u)).getroot()
        linked = root.find('linkinfo')
        return linked

    def check_diff(self, package, old_prj, new_prj):
        logging.debug('checking %s ...' % package)
        query = {'cmd': 'diff',
                 'view': 'xml',
                 'oproject': old_prj,
                 'opackage': package}
        u = makeurl(self.apiurl, ['source', new_prj, package], query=query)
        root = ET.parse(http_POST(u)).getroot()
        old_srcmd5 = root.findall('old')[0].get('srcmd5')
        logging.debug('%s old srcmd5 %s in %s' % (package, old_srcmd5, old_prj))
        new_srcmd5 = root.findall('new')[0].get('srcmd5')
        logging.debug('%s new srcmd5 %s in %s' % (package, new_srcmd5, new_prj))
        # Compare srcmd5
        if old_srcmd5 != new_srcmd5:
            # check if it has diff element
            diffs = root.findall('files/file/diff')
            if diffs:
                return ET.tostring(root)
        return False

    def crawl(self):
        """Main method"""
        # get souce packages from target
        print 'Gathering the package list from %s' % self.old_prj
        source = self.get_source_packages(self.old_prj)
        print 'Gathering the package list from %s' % self.new_prj
        target = self.get_source_packages(self.new_prj)

        for pkg in source:
            if pkg.startswith('000'):
                continue

            if pkg not in target:
                # ignore the second specfile package
                linked = self.is_linked_package(self.old_prj, pkg)
                if linked is not None:
                    continue

                print("New package than {:<8} - {}".format(self.new_prj, pkg))
            elif not self.newonly:
                diff = self.check_diff(pkg, self.old_prj, self.new_prj)
                if diff:
                    print("Different source in {:<8} - {}".format(self.new_prj, pkg))
                    if self.verbose:
                        print("=== Diff ===\n{}".format(diff))

def main(args):
    # Configure OSC
    osc.conf.get_config(override_apiurl=args.apiurl)
    osc.conf.config['debug'] = args.debug

    uc = CompareList(args.old_prj, args.new_prj, args.verbose, args.newonly)
    uc.crawl()

if __name__ == '__main__':
    description = 'Compare packages status between two project'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-A', '--apiurl', metavar='URL', help='API URL')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='print info useful for debuging')
    parser.add_argument('-o', '--old', dest='old_prj', metavar='PROJECT',
                        help='the old project where to compare (default: %s)' % SLE,
                        default=SLE)
    parser.add_argument('-n', '--new', dest='new_prj', metavar='PROJECT',
                        help='the new project where to compare (default: %s)' % OPENSUSE,
                        default=OPENSUSE)
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show the diff')
    parser.add_argument('--newonly', action='store_true',
                        help='show new package only')

    args = parser.parse_args()

    # Set logging configuration
    logging.basicConfig(level=logging.DEBUG if args.debug
                        else logging.INFO)

    sys.exit(main(args))
