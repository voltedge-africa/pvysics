"""Print non-placeholder shapes, fonts and fills of masters/layouts. Usage: inspect_master.py <file.pptx>"""
import sys
from pptx import Presentation
from pptx.util import Emu
prs = Presentation(sys.argv[1])
def dump(name, shapes):
    for sh in shapes:
        print(f"  [{name}] {sh.shape_type} '{sh.name}' ph={sh.is_placeholder} {Emu(sh.left).inches:.2f},{Emu(sh.top).inches:.2f} {Emu(sh.width).inches:.2f}x{Emu(sh.height).inches:.2f}")
m = prs.slide_master
print("MASTER"); dump("master", m.shapes)
for i in (0,1,2,5):
    l = prs.slide_layouts[i]; print("LAYOUT", i, l.name); dump("lay", l.shapes)
