__all__ = [
    'favicon',
    'slider_icon', 
    'application_import',
    'arrow_curve_180_left',
    'arrow_in',
    'arrow_move',
    'arrow_out',
    'bin_metal',
    'blue_document_export',
    'brightness',
    'contrast',
    'cursor',
    'cutter',
    'disk',
    'eraser',
    'hand',
    'hand_finger',
    'hand_point_090',
    'layer_shape',
    'layer_shape_ellipse',
    'layer_shape_curve',
    'layer_shape_polygon',
    'lock', 
    'lock_unlock',
    'magnifier',
    'minus',
    'paint',
    'paint_brush',
    'paint_brush_minus',
    'paint_brush_plus',
    'paint_can_minus',
    'pencil',
    'plus',
    'question_mark',
    'spectrum',
    'wand',
    'wand_hat',
    'wezel', 
]

# filepaths need to be identified with importlib_resources
# rather than __file__ as the latter does not work at runtime 
# when the package is installed via pip install

import sys

if sys.version_info < (3, 9):
    # importlib.resources either doesn't exist or lacks the files()
    # function, so use the PyPI version:
    import importlib_resources
else:
    # importlib.resources has files(), so use that:
    import importlib.resources as importlib_resources


f = importlib_resources.files('wezel.widgets.icons.images')

wezel = str(f.joinpath('wezel.jpg'))

f = importlib_resources.files('wezel.widgets.icons.my_icons')

favicon = str(f.joinpath('favicon.ico'))
slider_icon = str(f.joinpath('slider_icon.png'))
question_mark = str(f.joinpath('question-mark.png'))

f = importlib_resources.files('wezel.widgets.icons.fugue_icons')

application_import = str(f.joinpath('application-import.png'))
arrow_curve_180_left = str(f.joinpath('arrow-curve-180-left.png'))
arrow_in = str(f.joinpath('arrow-in.png'))
arrow_out = str(f.joinpath('arrow-out.png'))
arrow_move = str(f.joinpath('arrow-move.png'))
bin_metal = str(f.joinpath('bin-metal.png'))
blue_document_export = str(f.joinpath('blue-document-export.png'))
brightness = str(f.joinpath('brightness.png'))
contrast = str(f.joinpath('contrast.png'))
cursor = str(f.joinpath('cursor.png'))
cutter = str(f.joinpath('cutter.png'))
disk = str(f.joinpath('disk.png'))
eraser = str(f.joinpath('eraser.png'))
hand = str(f.joinpath('hand.png'))
hand_finger = str(f.joinpath('hand-finger.png'))
hand_point_090 = str(f.joinpath('hand-point-090.png'))
layer_shape = str(f.joinpath('layer-shape.png'))
layer_shape_ellipse = str(f.joinpath('layer-shape-ellipse.png'))
layer_shape_curve = str(f.joinpath('layer-shape-curve.png'))
layer_shape_polygon = str(f.joinpath('layer-shape-polygon.png'))
lock = str(f.joinpath('lock.png'))
lock_unlock = str(f.joinpath('lock-unlock.png'))
magnifier = str(f.joinpath('magnifier.png'))
minus = str(f.joinpath('minus.png'))
paint = str(f.joinpath('paint.png'))
paint_can_minus = str(f.joinpath('paint-can-minus.png'))
paint_brush = str(f.joinpath('paint-brush.png'))
paint_brush_minus = str(f.joinpath('paint-brush-minus.png'))
paint_brush_plus = str(f.joinpath('paint-brush-plus.png'))
pencil = str(f.joinpath('pencil.png'))
plus = str(f.joinpath('plus.png'))
spectrum = str(f.joinpath('spectrum.png'))
wand = str(f.joinpath('wand.png'))
wand_hat = str(f.joinpath('wand-hat.png'))
