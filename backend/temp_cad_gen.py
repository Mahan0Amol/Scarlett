
from build123d import *
import numpy as np

with BuildPart() as p:
    Box(10, 10, 10)

result_part = p.part
export_stl(result_part, 'output.stl')
