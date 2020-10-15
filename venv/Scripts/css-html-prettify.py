#!/usr/bin/python3
# -*- coding: utf-8 -*-


"""CSS-HTML-Prettify.

StandAlone Async cross-platform Prettifier Beautifier for the Web.
"""


import itertools
import os
import re
import sys

from argparse import ArgumentParser
from datetime import datetime
from multiprocessing import cpu_count, Pool
from time import sleep
from subprocess import getoutput

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    print("BeautifulSoup4 Not Found, use: pip install BeautifulSoup4")


__version__ = '2.5.5'


start_time = datetime.now()
CSS_PROPS_TEXT = '''

alignment-adjust alignment-baseline animation animation-delay
animation-direction animation-duration animation-iteration-count
animation-name animation-play-state animation-timing-function appearance
azimuth

backface-visibility background background-blend-mode background-attachment
background-clip background-color background-image background-origin
background-position background-position-block background-position-inline
background-position-x background-position-y background-repeat background-size
baseline-shift bikeshedding bookmark-label bookmark-level bookmark-state
bookmark-target border border-bottom border-bottom-color
border-bottom-left-radius border-bottom-parts border-bottom-right-radius
border-bottom-style border-bottom-width border-clip border-clip-top
border-clip-right border-clip-bottom border-clip-left border-collapse
border-color border-corner-shape border-image border-image-outset
border-image-repeat border-image-slice border-image-source border-image-width
border-left border-left-color border-left-style border-left-parts
border-left-width border-limit border-parts border-radius border-right
border-right-color border-right-style border-right-width border-right-parts
border-spacing border-style border-top border-top-color border-top-left-radius
border-top-parts border-top-right-radius border-top-style border-top-width
border-width bottom box-decoration-break box-shadow box-sizing

caption-side clear clip color column-count column-fill column-gap column-rule
column-rule-color column-rule-style column-rule-width column-span column-width
columns content counter-increment counter-reset corners corner-shape
cue cue-after cue-before cursor

direction display drop-initial-after-adjust drop-initial-after-align
drop-initial-before-adjust drop-initial-before-align drop-initial-size
drop-initial-value

elevation empty-cells

flex flex-basis flex-direction flex-flow flex-grow flex-shrink flex-wrap fit
fit-position float font font-family font-size font-size-adjust font-stretch
font-style font-variant font-weight

grid-columns grid-rows

justify-content

hanging-punctuation height hyphenate-character hyphenate-resource hyphens

icon image-orientation image-resolution inline-box-align

left letter-spacing line-height line-stacking line-stacking-ruby
line-stacking-shift line-stacking-strategy linear-gradient list-style
list-style-image list-style-position list-style-type

margin margin-bottom margin-left margin-right margin-top marquee-direction
marquee-loop marquee-speed marquee-style max-height max-width min-height
min-width

nav-index

opacity orphans outline outline-color outline-offset outline-style
outline-width overflow overflow-style overflow-x overflow-y

padding padding-bottom padding-left padding-right padding-top page
page-break-after page-break-before page-break-inside pause pause-after
pause-before perspective perspective-origin pitch pitch-range play-during
position presentation-level

quotes

resize rest rest-after rest-before richness right rotation rotation-point
ruby-align ruby-overhang ruby-position ruby-span

size speak speak-header speak-numeral speak-punctuation speech-rate src
stress string-set

table-layout target target-name target-new target-position text-align
text-align-last text-decoration text-emphasis text-indent text-justify
text-outline text-shadow text-transform text-wrap top transform
transform-origin transition transition-delay transition-duration
transition-property transition-timing-function

unicode-bidi unicode-range

vertical-align visibility voice-balance voice-duration voice-family
voice-pitch voice-range voice-rate voice-stress voice-volume volume

white-space widows width word-break word-spacing word-wrap

z-index

'''  # Do Not compact this string, new lines are used to Group up stuff.


###############################################################################
# CSS prettify


def _compile_props(props_text: str, grouped: bool=False) -> tuple:
    """Take a list of props and prepare them."""
    props, prefixes = [], "-webkit-,-khtml-,-epub-,-moz-,-ms-,-o-,".split(",")
    for propline in props_text.strip().lower().splitlines():
        props += [pre + pro for pro in propline.split(" ") for pre in prefixes]
    props = filter(lambda line: not line.startswith('#'), props)
    if not grouped:
        props = list(filter(None, props))
        return props, [0] * len(props)
    final_props, groups, g_id = [], [], 0
    for prop in props:
        if prop.strip():
            final_props.append(prop)
            groups.append(g_id)
        else:
            g_id += 1
    return (final_props, groups)


def _prioritify(line_of_css: str, css_props_text_as_list: tuple) -> tuple:
    """Return args priority, priority is integer and smaller means higher."""
    sorted_css_properties, groups_by_alphabetic_order = css_props_text_as_list
    priority_integer, group_integer = 9999, 0
    for css_property in sorted_css_properties:
        if css_property.lower() == line_of_css.split(":")[0].lower().strip():
            priority_integer = sorted_css_properties.index(css_property)
            group_integer = groups_by_alphabetic_order[priority_integer]
            break
    return (priority_integer, group_integer)


def _props_grouper(props, pgs):
    """Return groups for properties."""
    if not props:
        return props
    # props = sorted([
        # _ if _.strip().endswith(";") and
        # not _.strip().endswith("*/") and not _.strip().endswith("/*")
        # else _.rstrip() + ";\n" for _ in props])
    props_pg = zip(map(lambda prop: _prioritify(prop, pgs), props), props)
    props_pg = sorted(props_pg, key=lambda item: item[0][1])
    props_by_groups = map(
        lambda item: list(item[1]),
        itertools.groupby(props_pg, key=lambda item: item[0][1]))
    props_by_groups = map(lambda item: sorted(
        item, key=lambda item: item[0][0]), props_by_groups)
    props = []
    for group in props_by_groups:
        group = map(lambda item: item[1], group)
        props += group
        props += ['\n']
    props.pop()
    return props


def sort_properties(css_unsorted_string: str) -> str:
    """CSS Property Sorter Function.

    This function will read buffer argument, split it to a list by lines,
    sort it by defined rule, and return sorted buffer if it's CSS property.
    This function depends on '_prioritify' function.
    """
    css_pgs = _compile_props(CSS_PROPS_TEXT, grouped=bool(args.group))
    pattern = re.compile(r'(.*?{\r?\n?)(.*?)(}.*?)|(.*)',
                         re.DOTALL + re.MULTILINE)
    matched_patterns = pattern.findall(css_unsorted_string)
    sorted_patterns, sorted_buffer = [], css_unsorted_string
    RE_prop = re.compile(r'((?:.*?)(?:;)(?:.*?\n)|(?:.*))',
                         re.DOTALL + re.MULTILINE)
    if len(matched_patterns) != 0:
        for matched_groups in matched_patterns:
            sorted_patterns += matched_groups[0].splitlines(True)
            props = map(lambda line: line.lstrip('\n'),
                        RE_prop.findall(matched_groups[1]))
            props = list(filter(lambda line: line.strip('\n '), props))
            props = _props_grouper(props, css_pgs)
            sorted_patterns += props
            sorted_patterns += matched_groups[2].splitlines(True)
            sorted_patterns += matched_groups[3].splitlines(True)
        sorted_buffer = ''.join(sorted_patterns)
    return sorted_buffer


def remove_empty_rules(css: str) -> str:
    """Remove empty rules."""
    return re.sub(r"[^\}\{]+\{\}", "", css)


def condense_zero_units(css: str) -> str:
    """Replace `0(px, em, %, etc)` with `0`."""
    return re.sub(r"([\s:])(0)(px|em|%|in|q|ch|cm|mm|pc|pt|ex|rem|s|ms|"
                  r"deg|grad|rad|turn|vw|vh|vmin|vmax|fr)", r"\1\2", css)


def condense_semicolons(css: str) -> str:
    """Condense multiple adjacent semicolon characters into one."""
    return re.sub(r";;+", ";", css)


def wrap_css_lines(css: str, line_length: int=80) -> str:
    """Wrap the lines of the given CSS to an approximate length."""
    print(f"Wrapping lines to ~{line_length} max line lenght.")
    lines, line_start = [], 0
    for i, char in enumerate(css):
        # Its safe to break after } characters.
        if char == '}' and (i - line_start >= line_length):
            lines.append(css[line_start:i + 1])
            line_start = i + 1
    if line_start < len(css):
        lines.append(css[line_start:])
    return "\n".join(lines)


def add_encoding(css: str) -> str:
    """Add @charset 'UTF-8'; if missing."""
    return "@charset utf-8;\n\n\n" + css if "@charset" not in css else css


def normalize_whitespace(css: str) -> str:
    """Normalize css string white spaces."""
    css_no_trailing_whitespace = ""
    for line_of_css in css.splitlines():  # remove all trailing white spaces
        css_no_trailing_whitespace += line_of_css.rstrip() + "\n"
    css = css_no_trailing_whitespace
    css = re.sub(r"\n{3}", "\n\n\n", css)  # if 3 new lines,make them 2
    css = re.sub(r"\n{5}", "\n\n\n\n\n", css)  # if 5 new lines, make them 4
    css = re.sub(r"\n{6,}", f"\n\n\n/*{'-' * 72}*/\n\n\n", css)
    css = css.replace(" ;\n", ";\n").replace("{\n", " {\n")
    css = re.sub("\s{2,}{\n", " {\n", css)
    return css.replace("\t", "    ").rstrip() + "\n"


def justify_right(css: str) -> str:
    """Justify to the Right all CSS properties on the argument css string."""
    max_indent, right_justified_css = 1, ""
    for css_line in css.splitlines():
        c_1 = len(css_line.split(":")) == 2 and css_line.strip().endswith(";")
        c_2 = "{" not in css_line and "}" not in css_line and len(css_line)
        c_4 = not css_line.lstrip().lower().startswith("@import ")
        if c_1 and c_2 and c_4:
            lenght = len(css_line.split(":")[0].rstrip()) + 1
            max_indent = lenght if lenght > max_indent else max_indent
    for line_of_css in css.splitlines():
        c_1 = "{" not in line_of_css and "}" not in line_of_css
        c_2 = max_indent > 1 and len(line_of_css.split(":")) == 2
        c_3 = line_of_css.strip().endswith(";") and len(line_of_css)
        c_4 = "@import " not in line_of_css
        if c_1 and c_2 and c_3 and c_4:
            propert_len = len(line_of_css.split(":")[0].rstrip()) + 1
            xtra_spaces = " " * (max_indent + 1 - propert_len)
            xtra_spaces = ":" + xtra_spaces
            justified_line_of_css = ""
            justified_line_of_css = line_of_css.split(":")[0].rstrip()
            justified_line_of_css += xtra_spaces
            justified_line_of_css += line_of_css.split(":")[1].lstrip()
            right_justified_css += justified_line_of_css + "\n"
        else:
            right_justified_css += line_of_css + "\n"
    return right_justified_css if max_indent > 1 else css


def split_long_selectors(css: str) -> str:
    """Split too large CSS Selectors chained with commas if > 80 chars."""
    result = ""
    for line in css.splitlines():
        cond_1 = len(line) > 80 and "," in line and line.strip().endswith("{")
        cond_2 = line.startswith(("*", ".", "#"))
        if cond_1 and cond_2:
            result += line.replace(", ", ",").replace(",", ",\n").replace(
                "{", "{\n")
        else:
            result += line + "\n"
    return result


def simple_replace(css: str) -> str:
    """dumb simple replacements on CSS."""
    return css.replace("}\n#", "}\n\n#").replace(
        "}\n.", "}\n\n.").replace("}\n*", "}\n\n*")


def css_prettify(css: str, justify: bool=False, extraline: bool=False) -> str:
    """Prettify CSS main function."""
    css = sort_properties(css)
    css = condense_zero_units(css)
    css = wrap_css_lines(css, 80)
    css = split_long_selectors(css)
    css = condense_semicolons(css)
    css = normalize_whitespace(css)
    css = justify_right(css) if justify else css
    css = add_encoding(css)
    css = simple_replace(css)
    if extraline:
        css = "\n\n".join(css.replace("\t", "    ").splitlines()) + "\n"
    return css


##############################################################################
# HTML Prettify


if BeautifulSoup:
    # http://stackoverflow.com/a/15513483
    orig_prettify = BeautifulSoup.prettify
    regez = re.compile(r'^(\s*)', re.MULTILINE)


    def prettify(self, encoding=None, formatter="minimal", indent_width=4):
        """Monkey Patch the BS4 prettify to allow custom indentations."""
        print("Monkey Patching BeautifulSoup on-the-fly to process HTML...")
        return regez.sub(r'\1' * indent_width,
                         orig_prettify(self, encoding, formatter))

    BeautifulSoup.prettify = prettify


    def html_prettify(html: str, extraline: bool=False) -> str:
        """Prettify HTML main function."""
        html = BeautifulSoup(html).prettify()
        if extraline:
            html = "\n\n".join(html.replace("\t", "    ").splitlines()) + "\n"
        return html
else:
    # XHTML Prettify
    def html_prettify(html: str, extraline: bool=False) -> str:
        """Prettify XHTML main function."""
        html = minidom.parseString(html).toprettyxml(indent="    ")[22:]
        if extraline:
            html = "\n\n".join(html.replace("\t", "    ").splitlines()) + "\n"
        return html


##############################################################################


def walk2list(folder: str, target: tuple, omit: tuple=(),
              showhidden: bool=False, topdown: bool=True,
              onerror: object=None, followlinks: bool=False) -> tuple:
    """Perform full walk, gather full path of all files."""
    oswalk = os.walk(folder, topdown=topdown,
                     onerror=onerror, followlinks=followlinks)

    return [os.path.abspath(os.path.join(r, f))
            for r, d, fs in oswalk
            for f in fs if not f.startswith(() if showhidden else ".") and
            not f.endswith(omit) and f.endswith(target)]


def process_multiple_files(file_path):
    """Process multiple CSS, HTML files with multiprocessing."""
    print(f"Process {os.getpid()} is processing {file_path}.")
    if args.watch:
        previous = int(os.stat(file_path).st_mtime)
        print(f"Process {os.getpid()} is Watching {file_path}.")
        while True:
            actual = int(os.stat(file_path).st_mtime)
            if previous == actual:
                sleep(60)
            else:
                previous = actual
                print("Modification detected on {file_path}.")
                if file_path.endswith((".css", ".scss")):
                    process_single_css_file(file_path)
                else:
                    process_single_html_file(file_path)
    else:
        if file_path.endswith((".css", ".scss")):
            process_single_css_file(file_path)
        else:
            process_single_html_file(file_path)


def prefixer_extensioner(file_path: str) -> str:
    """Take a file path and safely prepend a prefix and change extension.

    This is needed because filepath.replace('.foo', '.bar') sometimes may
    replace '/folder.foo/file.foo' into '/folder.bar/file.bar' wrong!.
    """
    extension = os.path.splitext(file_path)[1].lower()
    filenames = os.path.splitext(os.path.basename(file_path))[0]
    filenames = args.prefix + filenames if args.prefix else filenames
    dir_names = os.path.dirname(file_path)
    file_path = os.path.join(dir_names, filenames + extension)
    return file_path


def process_single_css_file(css_file_path: str) -> str:
    """Process a single CSS file."""
    global args
    with open(css_file_path, encoding="utf-8-sig") as css_file:
        original_css = css_file.read()
    pretty_css = css_prettify(original_css, args.justify, args.extraline)
    if args.timestamp:
        taim = f"/* {datetime.now().replace(microsecond=0).isoformat(' ')} */ "
        pretty_css = taim + pretty_css
    min_css_file_path = prefixer_extensioner(css_file_path)
    with open(min_css_file_path, "w", encoding="utf-8") as output_file:
        output_file.write(pretty_css)
    return pretty_css


def process_single_html_file(html_file_path: str) -> str:
    """Process a single HTML file."""
    with open(html_file_path, encoding="utf-8-sig") as html_file:
        pretty_html = html_prettify(html_file.read(), args.extraline)
    html_file_path = prefixer_extensioner(html_file_path)
    with open(html_file_path, "w", encoding="utf-8") as output_file:
        output_file.write(pretty_html)
    return pretty_html


def make_arguments_parser():
    """Build and return a command line agument parser."""
    # Parse command line arguments.
    parser = ArgumentParser(description=__doc__, epilog="""CSS-HTML-Prettify:
    Takes file or folder full path string and process all CSS/SCSS/HTML found.
    If argument is not file/folder will fail. Check Updates works on Python3.
    StdIn to StdOut is deprecated since may fail with unicode characters.
    CSS Properties are AlphaSorted,to help spot cloned ones,Selectors not.
    Watch works for whole folders, with minimum of ~60 Secs between runs.""")
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('fullpath', metavar='fullpath', type=str,
                        help='Full path to local file or folder.')
    parser.add_argument('--prefix', type=str,
                        help="Prefix string to prepend on output filenames.")
    parser.add_argument('--timestamp', action='store_true',
                        help="Add a Time Stamp on all CSS/SCSS output files.")
    parser.add_argument('--quiet', action='store_true',
                        help="Quiet, Silent, force disable all Logging.")
    parser.add_argument('--after', type=str,
                        help="Command to execute after run (Experimental).")
    parser.add_argument('--before', type=str,
                        help="Command to execute before run (Experimental).")
    parser.add_argument('--watch', action='store_true',
                        help="Re-Compress if file changes (Experimental).")
    parser.add_argument('--group', action='store_true',
                        help="Group Alphabetically CSS Poperties by name.")
    parser.add_argument('--justify', action='store_true',
                        help="Right Justify CSS Properties (Experimental).")
    parser.add_argument('--extraline', action='store_true',
                        help="Add 1 New Line for each New Line (Experimental)")
    global args
    args = parser.parse_args()
    return args


def main():
    """Main Loop."""
    make_arguments_parser()
    global log
    print(__doc__ + __version__)
    if args.before and getoutput:
        print(getoutput(str(args.before)))
    if os.path.isfile(args.fullpath) and args.fullpath.endswith(
            (".css", ".scss")):  # Work based on if argument is file or folder.
        print("Target is a CSS / SCSS File.")
        list_of_files = str(args.fullpath)
        process_single_css_file(args.fullpath)
    elif os.path.isfile(args.fullpath
                        ) and args.fullpath.endswith((".htm", ".html")):
        print("Target is a HTML File.")
        list_of_files = str(args.fullpath)
        process_single_html_file(args.fullpath)
    elif os.path.isdir(args.fullpath):
        print("Target is a Folder with CSS / SCSS, HTML, JS.")
        print("Processing a whole Folder may take some time...")
        list_of_files = walk2list(
            args.fullpath, (".css", ".scss", ".html", ".htm"), ".min.css")
        pool = Pool(cpu_count())  # Multiprocessing Async
        pool.map_async(process_multiple_files, list_of_files)
        pool.close()
        pool.join()
    else:
        print("File or folder not found,or cant be read,or I/O Error.")
        sys.exit(1)
    if args.after and getoutput:
        print(getoutput(str(args.after)))
    print(f'\n {"-" * 80} \n Files Processed: {list_of_files}.')
    print(f'''Number of Files Processed:
          {len(list_of_files) if isinstance(list_of_files, tuple) else 1}''')


if __name__ in '__main__':
    main()
