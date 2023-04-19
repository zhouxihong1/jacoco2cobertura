#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File        : cover2cover.py
@Contact     : zhouxihong
@Version     : 1.0
@Modify Time : 2023/4/13 14:09
@Author      : zhouxihong
@Desciption  : None
@License     : (C)Copyright 2023-Inf, zhouxihong
"""

import sys
import xml.etree.ElementTree as Et
import re
import os.path
from xml.dom import minidom
import chardet

"""
首先感谢: https://github.com/rix0rrr/cover2cover该项目,
没有他就没有本项目

其次在该项目中做了如下优化:
1. 语法全面支持Python3
2. 优化ElementTree的tostring方法decode
3. 优化变量名,消除PEP8规范下的警告
4. 优化Usage用法描述
5. 添加 OUTPUT_PATH, 可直接将Cobertura输出文件(原有命令行>>输出也兼容)
6. 添加 --xml-pretty参数,使输出的Cobertura内容更易读
7. 新增 only --xml-pretty模式, 用于直接打印xml,而不进行 jacoco xml -> Cobertura的转义
8. 新增入口部分函数注释
"""

# branch-rate="0.0" complexity="0.0" line-rate="1.0"
# branch="true" hits="1" number="86"


def find_lines(j_package, file_name):
    """
    Return all <line> elements for a given source file in a package.
    :param j_package:
    :param file_name:
    :return:
    """
    lines = []
    source_files = j_package.findall("sourcefile")
    for sourcefile in source_files:
        if sourcefile.attrib.get("name") == os.path.basename(file_name):
            lines = lines + sourcefile.findall("line")
    return lines


def line_is_after(jm, start_line):
    return int(jm.attrib.get('line', 0)) > start_line


def method_lines(j_method, j_methods, j_lines):
    """
    Filter the lines from the given set of j_lines that apply to the given j_method.
    :param j_method:
    :param j_methods:
    :param j_lines:
    :return:
    """
    start_line = int(j_method.attrib.get('line', 0))
    larger = list(int(jm.attrib.get('line', 0)) for jm in j_methods if line_is_after(jm, start_line))
    end_line = min(larger) if len(larger) else 99999999

    for j in j_lines:
        if start_line <= int(j.attrib['nr']) < end_line:
            yield j


def convert_lines(j_lines, into):
    """
    Convert the JaCoCo <line> elements into Cobertura <line> elements, add them under the given element.
    :param j_lines:
    :param into:
    :return:
    """
    c_lines = Et.SubElement(into, 'lines')
    for j in j_lines:
        mb = int(j.attrib['mb'])
        cb = int(j.attrib['cb'])
        ci = int(j.attrib['ci'])

        cline = Et.SubElement(c_lines, 'line')
        cline.set('number', j.attrib['nr'])
        cline.set('hits', '1' if ci > 0 else '0')  # Probably not true but no way to know from JaCoCo XML file

        if mb + cb > 0:
            percentage = str(int(100 * (float(cb) / (float(cb) + float(mb))))) + '%'
            cline.set('branch', 'true')
            cline.set('condition-coverage', percentage + ' (' + str(cb) + '/' + str(cb + mb) + ')')

            cond = Et.SubElement(Et.SubElement(cline, 'conditions'), 'condition')
            cond.set('number', '0')
            cond.set('type', 'jump')
            cond.set('coverage', percentage)
        else:
            cline.set('branch', 'false')


def guess_filename(path_to_class):
    m = re.match('([^$]*)', path_to_class)
    return (m.group(1) if m else path_to_class) + '.java'


def add_counters(source, target):
    target.set('line-rate', counter(source, 'LINE'))
    target.set('branch-rate', counter(source, 'BRANCH'))
    target.set('complexity', counter(source, 'COMPLEXITY', sum_coverage))


def fraction(covered, missed):
    return covered / (covered + missed)


def sum_coverage(covered, missed):
    return covered + missed


def counter(source, _type, operation=fraction):
    cs = source.findall('counter')
    c = next((ct for ct in cs if ct.attrib.get('type') == _type), None)

    if c is not None:
        covered = float(c.attrib['covered'])
        missed = float(c.attrib['missed'])

        return str(operation(covered, missed))
    else:
        return '0.0'


def convert_method(j_method, j_lines):
    c_method = Et.Element('method')
    c_method.set('name', j_method.attrib['name'])
    c_method.set('signature', j_method.attrib['desc'])

    add_counters(j_method, c_method)
    convert_lines(j_lines, c_method)

    return c_method


def convert_class(j_class, j_package):
    c_class = Et.Element('class')
    c_class.set('name', j_class.attrib['name'].replace('/', '.'))
    c_class.set('filename', guess_filename(j_class.attrib['name']))

    all_j_lines = list(find_lines(j_package, c_class.attrib['filename']))

    c_methods = Et.SubElement(c_class, 'methods')
    all_j_methods = list(j_class.findall('method'))
    for j_method in all_j_methods:
        j_method_lines = method_lines(j_method, all_j_methods, all_j_lines)
        c_methods.append(convert_method(j_method, j_method_lines))

    add_counters(j_class, c_class)
    convert_lines(all_j_lines, c_class)

    return c_class


def convert_package(j_package):
    c_package = Et.Element('package')
    c_package.attrib['name'] = j_package.attrib['name'].replace('/', '.')

    c_classes = Et.SubElement(c_package, 'classes')
    for j_class in j_package.findall('class'):
        c_classes.append(convert_class(j_class, j_package))

    add_counters(j_package, c_package)

    return c_package


def convert_root(source, target, _source_roots):
    target.set('timestamp', str(int(source.find('session' + 'info').attrib['start']) / 1000))

    sources = Et.SubElement(target, 'sources')
    for s in _source_roots:
        Et.SubElement(sources, 'source').text = s

    packages = Et.SubElement(target, 'packages')
    for package in source.findall('package'):
        packages.append(convert_package(package))

    add_counters(source, target)


def pretty_parse_xml(xml_body):
    """
    xml添加缩进的函数
    :param xml_body: xml内容
    :return:
    """
    content = minidom.parseString(xml_body).toprettyxml(indent="  ")
    return content


def write_pretty_xml(file_path):
    """
    美观打印xml
    :param file_path: 文件路径
    :return:
    """
    with open(file_path, 'rb') as f:
        content = f.read()
        encoding = chardet.detect(content)['encoding']
        print(f"检测的编码格式为 {encoding}")
        xml_body = content.decode(encoding)
    xml_body = pretty_parse_xml(xml_body)

    with open(file_path.rsplit(".")[0] + "_pretty.xml", "w+", encoding="utf-8") as f:
        f.write(xml_body)


def jacoco2cobertura(file_name, _source_roots, _output_path=None, _xml_pretty=False):
    """
    jacoco转化为cobertura的主入口
    :param file_name: jacoco的文件名
    :param _source_roots: jacoco转化为cobertura的source root名称
    :param _output_path: 输出路径
    :param _xml_pretty: 是否开启美观打印
    :return:
    """
    if file_name == '-':
        root = Et.fromstring(sys.stdin.read())
    else:
        tree = Et.parse(file_name)
        root = tree.getroot()

    into = Et.Element('coverage')
    convert_root(root, into, _source_roots)
    xml_head = '<?xml version="1.0" ?>'
    # xml_body = Et.tostring(into).decode()
    # xml_body = Et.tostring(into, encoding='utf-8', xml_declaration=True).decode()
    xml_body = xml_head + "\n" + Et.tostring(into, encoding='utf-8').decode()
    # xml_body = Et.tostring(into, encoding='utf-8').decode()
    if _xml_pretty:
        xml_body = pretty_parse_xml(xml_body)
    if _output_path is None:
        # print(xml_head)
        print(xml_body)
        _output_path = "coverage.xml"
    # xml_content = xml_head + "\n" + xml_body
    xml_content = xml_body
    with open(_output_path, "w+", encoding="utf-8") as f:
        f.write(xml_content)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: cover2cover.py FILENAME [SOURCE_ROOTS] OUTPUT_PATH [--xml-pretty]")
        sys.exit(1)
    elif sys.argv[1] == "-h":
        print("Usage: cover2cover.py FILENAME [SOURCE_ROOTS] OUTPUT_PATH [--xml-pretty]")
        print("Example: python cover2cover.py jacoco.xml . --xml-pretty")
        print("NOTE: --xml-pretty 参数开启后,将导致输出xml大幅增长")
        print("Example: python cover2cover.py jacoco.xml")
        print("NOTE: 此示例将转换jacoco.xml为jacoco_pretty.xml,一般用于调试或需要查看美化后的xml文件")

    # Add only --xml-pretty
    if "--xml-pretty" in sys.argv and len(sys.argv) == 3:
        write_pretty_xml(sys.argv[1])
        sys.exit(0)

    filename = sys.argv[1]
    source_roots = sys.argv[2] if len(sys.argv) > 2 else '.'
    if len(sys.argv) < 4:
        output_path = None
    else:
        output_path = sys.argv[3]
    if "--xml-pretty" in sys.argv:
        xml_pretty = True
    else:
        xml_pretty = False
        if len(sys.argv) >= 5:
            if sys.argv[4] != "--xml-pretty":
                print("NOTE: 优化xml输出的参数不对,美观打印默认关闭")

    jacoco2cobertura(filename, source_roots, output_path, xml_pretty)
