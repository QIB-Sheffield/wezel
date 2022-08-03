__all__ = [
    'MaskView', 
    'MaskViewBrush', 
    'MaskViewPenFreehand',
    'MaskViewPenRectangle', 
    'MaskViewPenPolygon', 
    'MaskViewPenCircle',
    'MaskViewRegionGrowing',
    'MaskViewDeleteROI',
    'MaskViewEdgeDetection',
    'MaskViewErode',
    'MaskViewDilate'
]

import math
import numpy as np
from matplotlib.path import Path as MplPath
import cv2 as cv2
import time
from skimage import feature

from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, qRgb, QIcon, QCursor, QColor, QPen
from PyQt5.QtWidgets import QGraphicsObject, QAction, QAction, QMenu

from .. import widgets as widgets


class MaskView(widgets.ImageView):
    """Extends image view with a MaskItem for drawing masks.
    
    If no mask instance is provided, this creates
    a canvas that can be drawn on
    but the results can't be saved or retrieved."""

    newMask = pyqtSignal()

    def __init__(self, image=None, mask=None): 
        super().__init__(image)
      
        shape = self._shape(mask)
        self.maskItem = MaskItem(mask, shape)
        self.maskItem.newMask.connect(self._newMask)
        self.scene.addItem(self.maskItem)

    @property
    def mask(self):
        return self.maskItem.mask

    def _shape(self, mask): # private

        if mask is None:
            width = self.imageItem.pixMap.width()
            height = self.imageItem.pixMap.height() 
        else:            
            width = mask.Rows
            height = mask.Columns
        return width, height

#    def isBlank(self):

#        nrMaskPixels = np.count_nonzero(self.maskItem.bin)
#        return nrMaskPixels == 0

    def setObject(self, mask): # obsolete?
        self.maskItem.mask = mask

    def setData(self, image, mask):
        
        self.setImage(image)
        self.setMask(mask)

    def setImage(self, image):
        super().setData(image)
        
    def setMask(self, mask):

        self._updatePixelArray()
        shape = self._shape(mask)
        self.maskItem.mask = mask
        self.maskItem._setMaskImage(shape)

    def getMask(self):

        return self.mask

#    def getPixelArray(self):
#        return self.maskItem._getMaskImage()

    def _updatePixelArray(self):
        """Write the current pixel array in the mask image"""

        if self.mask is None: return
        array = self.maskItem._getMaskImage()
        self.mask.set_array(array)

    def eraseMask(self): # not yet in use

        self.maskItem.eraseMaskImage()
        self._updatePixelArray()

    def _newMask(self):

        mask = self.image.copy()
        mask.WindowCenter = 1
        mask.WindowWidth = 2
        self.maskItem.mask = mask
        self._updatePixelArray()
        self.newMask.emit()


class MaskItem(QGraphicsObject):
    """Displays a mask as an overlay on an image.
    """

    newMask = pyqtSignal()

    def __init__(self, mask=None, shape=None): 
        super().__init__()

        self.mask = mask
        self._setMaskImage(shape=shape)

    def _setMaskImage(self, shape=(128,128)):

        if self.mask is None:
            self.bin = np.zeros(shape, dtype=bool)
        else:
            self.bin = self.mask.array() != 0
        self.qImage = QImage(self.bin.shape[0], self.bin.shape[1], QImage.Format_RGB32)
        self.fillQImage()
        self.update()

    def _getMaskImage(self):

        return self.bin.astype(float)

    def eraseMaskImage(self):

        self.bin.fill(False)
        self.fillQImage()

    def boundingRect(self): 
        """Abstract method - must be overridden."""

        return QRectF(0, 0, self.bin.shape[0], self.bin.shape[1])

    def paint(self, painter, option, widget):
        """Executed by GraphicsView when calling update()"""

        pixMap = QPixmap.fromImage(self.qImage)
        width = pixMap.width()
        height = pixMap.height()
        painter.setOpacity(0.25)
        painter.drawPixmap(0, 0, width, height, pixMap)
 
    def fillQImage(self):

        for x in range(self.bin.shape[0]):
            for y in range(self.bin.shape[1]):
                self.setPixel(x, y)

    def setPixel(self, x, y, add=None):

        if add is None:
            add = self.bin[x, y]
        else:
            self.bin[x,y] = add
        if add: 
            red = 255
            if self.mask is None:
                self.newMask.emit()
        else:
            red = 0
        color = qRgb(red, 0, 0)
        self.qImage.setPixel(x, y, color)


class MaskViewBrush(widgets.ImageViewCursor):
    """Painting or erasing tool.
    
    Features
    --------
    >>> Left click and drag to paint or erase.
    >>> Right click to change the brush properties
    (erase or paint, size of the brush).
    >>> Right click and drag to change the windowing.
    """

    def __init__(self, brushSize=1, mode="paint"):
        super().__init__()

        self.setBrushSize(brushSize)
        self.setMode(mode)

    def setView(self, imageView):
        """Assign an ImageView instance to handle"""

        super().setView(imageView)
        self.maskItem = imageView.maskItem

    def setBrushSize(self, brushSize):

        self.brushSize = brushSize

    def setMode(self, mode):

        self.mode = mode
        if mode == "paint":
            pixMap = QPixmap(widgets.icons.paint_brush)
            self.cursor = QCursor(pixMap, hotX=0, hotY=16)
            self.toolTip = 'Paint brush'
        elif mode == "erase":
            pixMap = QPixmap(widgets.icons.eraser)
            self.cursor = QCursor(pixMap, hotX=0, hotY=16)
            self.toolTip = 'Eraser'
        self.icon = QIcon(pixMap)

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        button = event.button()
        if button == Qt.LeftButton:
            self.paintPixels()
        elif button == Qt.RightButton:
            self.launchContextMenu(event)

    def itemMouseReleaseEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        buttons = event.buttons()
        if buttons == Qt.LeftButton:
            self.paintPixels()  
        self.view.mousePositionMoved.emit()

    def paintPixels(self):
   
        w = int((self.brushSize - 1)/2)
        for x in range(self.x-w, self.x+w+1, 1):
            if 0 <= x < self.maskItem.bin.shape[0]:
                for y in range(self.y-w, self.y+w+1, 1):
                    if 0 <= y < self.maskItem.bin.shape[1]:
                        self.maskItem.setPixel(x, y, self.mode == "paint")
        self.maskItem.update()
       
    def launchContextMenu(self, event):

        pickBrush = QAction(QIcon(widgets.icons.paint_brush), 'Paint', None)
        pickBrush.setCheckable(True)
        pickBrush.setChecked(self.mode == "paint")
        pickBrush.triggered.connect(lambda: self.setMode("paint"))
        
        pickEraser = QAction(QIcon(widgets.icons.eraser), 'Erase', None)
        pickEraser.setCheckable(True)
        pickEraser.setChecked(self.mode == "erase")
        pickEraser.triggered.connect(lambda: self.setMode("erase"))

        clearMask = QAction(QIcon(widgets.icons.arrow_curve_180_left), 'Clear Region', None)
        clearMask.triggered.connect(self.maskItem.eraseMaskImage)

        onePixel = QAction('1 pixel', None)
        onePixel.setCheckable(True)
        onePixel.setChecked(self.brushSize == 1)
        onePixel.triggered.connect(lambda: self.setBrushSize(1))

        threePixels = QAction('3 pixels', None)
        threePixels.setCheckable(True)
        threePixels.setChecked(self.brushSize == 3)
        threePixels.triggered.connect(lambda: self.setBrushSize(3))

        fivePixels = QAction('5 pixels', None)
        fivePixels.setCheckable(True)
        fivePixels.setChecked(self.brushSize == 5)
        fivePixels.triggered.connect(lambda: self.setBrushSize(5))

        sevenPixels = QAction('7 pixels', None)
        sevenPixels.setCheckable(True)
        sevenPixels.setChecked(self.brushSize == 7)
        sevenPixels.triggered.connect(lambda: self.setBrushSize(7))

        ninePixels = QAction('9 pixels', None)
        ninePixels.setCheckable(True)
        ninePixels.setChecked(self.brushSize == 9)
        ninePixels.triggered.connect(lambda: self.setBrushSize(9))

        elevenPixels = QAction('11 pixels', None)
        elevenPixels.setCheckable(True)
        elevenPixels.setChecked(self.brushSize == 11)
        elevenPixels.triggered.connect(lambda: self.setBrushSize(11))

        twentyOnePixels = QAction('21 pixels', None)
        twentyOnePixels.setCheckable(True)
        twentyOnePixels.setChecked(self.brushSize == 21)
        twentyOnePixels.triggered.connect(lambda: self.setBrushSize(21))

        contextMenu = QMenu()
        contextMenu.addAction(pickBrush)
        contextMenu.addAction(pickEraser)
        contextMenu.addAction(clearMask)

        subMenu = contextMenu.addMenu('Brush size')
        subMenu.setEnabled(True)
        # subMenu.clear()
        subMenu.addAction(onePixel)
        subMenu.addAction(threePixels)
        subMenu.addAction(fivePixels)
        subMenu.addAction(sevenPixels)
        subMenu.addAction(ninePixels)
        subMenu.addAction(elevenPixels)
        subMenu.addAction(twentyOnePixels)

        contextMenu.exec_(event.screenPos())


class MaskViewPenFreehand(widgets.ImageViewCursor):
    """Freehand region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, mode="draw"):
        super().__init__()

        self.icon = QIcon(widgets.icons.layer_shape_curve)
        self.path = None
        self.setMode(mode)
        
    def setMode(self, mode):

        self.mode = mode
        if mode == "draw":
            pixMap = QPixmap(widgets.icons.pencil)
            self.cursor = QCursor(pixMap, hotX=0, hotY=16)
            self.toolTip = 'Draw'
        elif mode == "cut":
            pixMap = QPixmap(widgets.icons.cutter)
            self.cursor = QCursor(pixMap, hotX=0, hotY=16)
            self.toolTip = 'Cut'

    def setView(self, imageView):
        """Assign an ImageView instance to handle"""

        super().setView(imageView)
        self.maskItem = imageView.maskItem
        
    def paint(self, painter, option, widget):

        if self.path is None: return

        pen = QPen()
        pen.setColor(QColor(Qt.white))
        pen.setWidth(0)
        painter.setPen(pen)

        position = self.path[0]
        p1 = QPointF(position[0], position[1])
        for position in self.path[1:]:
            p2 = QPointF(position[0], position[1])
            painter.drawLine(p1, p2)
            p1 = p2
        position = self.path[0]
        p2 = QPointF(position[0], position[1])
        painter.drawLine(p1, p2)

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            position = [event.pos().x(), event.pos().y()]
            self.path = [position]
        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)

    def itemMouseReleaseEvent(self, event):
        
        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        button = event.button()
        if button == Qt.LeftButton:
            if self.path is not None:
                self.fillPath()
                self.path = None
            
    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        buttons = event.buttons()
        if buttons == Qt.LeftButton:
            position = [event.pos().x(), event.pos().y()]
            #if position not in self.path:
            if position != self.path[-1]:
                self.path.append(position)
                self.item.update()

    def fillPath(self):

        if len(self.path) == 0: 
            return

        nx, ny = self.maskItem.bin.shape[0], self.maskItem.bin.shape[1]
        x, y = np.meshgrid(np.arange(0.5, 0.5+nx), np.arange(0.5, 0.5+ny), indexing='ij')
        points = list(zip(x.flatten(), y.flatten()))
        #points = np.vstack((x.flatten(), y.flatten())).transpose()

        roiPath = MplPath(self.path, closed=True)
        bin = roiPath.contains_points(points, radius=0.0).reshape((nx, ny))
        #bin = np.transpose(bin != 0)
        #bin = bin != 0
        if self.mode == "draw":
            self.maskItem.bin = np.logical_or(self.maskItem.bin, bin)
        elif self.mode == "cut":
            self.maskItem.bin = np.logical_and(self.maskItem.bin, np.logical_not(bin))
        self.maskItem.fillQImage()
        self.maskItem.update()
        
    def launchContextMenu(self, event):

        pickBrush = QAction(QIcon(widgets.icons.pencil), 'Draw', None)
        pickBrush.setCheckable(True)
        pickBrush.setChecked(self.mode == "draw")
        pickBrush.triggered.connect(lambda: self.setMode("draw"))
        
        pickEraser = QAction(QIcon(widgets.icons.cutter), 'Cut', None)
        pickEraser.setCheckable(True)
        pickEraser.setChecked(self.mode == "cut")
        pickEraser.triggered.connect(lambda: self.setMode("cut"))

        clearMask = QAction(QIcon(widgets.icons.arrow_curve_180_left), 'Clear mask', None)
        clearMask.triggered.connect(self.maskItem.eraseMaskImage)

        contextMenu = QMenu()
        contextMenu.addAction(pickBrush)
        contextMenu.addAction(pickEraser)
        contextMenu.addAction(clearMask)
        contextMenu.exec_(event.screenPos())


class MaskViewPenPolygon(MaskViewPenFreehand):
    """Polygon region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, mode="draw"):
        super().__init__(mode=mode)

        self.icon = QIcon(widgets.icons.layer_shape_polygon)

    def itemHoverMoveEvent(self, event):

        if self.path is not None:
            self.path[-1] = [event.pos().x(), event.pos().y()]
            self.maskItem.update()
        super().itemHoverMoveEvent(event)

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            position = [event.pos().x(), event.pos().y()]
            if self.path is None:
                self.path = [position, position]
            else:
                self.path[-1] = position
                self.path.append(position)
        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)

    def itemMouseReleaseEvent(self, event):
        pass

    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        self.path[-1] = [event.pos().x(), event.pos().y()]
        self.maskItem.update()

    def itemMouseDoubleClickEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        button = event.button()
        if button == Qt.LeftButton:
            if self.path is not None:
                self.path[-1] = [event.pos().x(), event.pos().y()]
                self.fillPath()
                self.maskItem.update()
                self.path = None


class MaskViewPenRectangle(MaskViewPenFreehand):
    """Rectangle region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, mode="draw"):
        super().__init__(mode=mode)

        self.icon = QIcon(widgets.icons.layer_shape)
            
    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        buttons = event.buttons()
        if buttons == Qt.LeftButton:
            corner1 = self.path[0]
            corner2 = [event.pos().x(), event.pos().y()]
            self.path = [
                [corner1[0], corner1[1]], 
                [corner2[0], corner1[1]], 
                [corner2[0], corner2[1]],
                [corner1[0], corner2[1]],
                [corner1[0], corner1[1]]]
            self.maskItem.update()


class MaskViewPenCircle(MaskViewPenFreehand):
    """Rectangle region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, mode="draw"):
        super().__init__(mode=mode)

        self.icon = QIcon(widgets.icons.layer_shape_ellipse)
        self.center = None

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            self.center = [event.pos().x(), event.pos().y()]
        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)
            
    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        buttons = event.buttons()
        if buttons == Qt.LeftButton:
            p = [event.pos().x(), event.pos().y()]
            self.setCirclePath(p)
            self.maskItem.update()

    def setCirclePath(self, p):
        """Return a circle with center in c and going through point p"""

        c = self.center
        pc = [p[0]-c[0], p[1]-c[1]]
        radius = math.sqrt(pc[0]**2 + pc[1]**2)
        if radius == 0: return
        step = 0.5 # pixel - precision of the circle
        if step > radius: step = radius
        angle = math.acos(1-0.5*(step/radius)**2)
        nsteps = round(2*math.pi/angle)
        angle = 2*math.pi/nsteps
        x0 = pc[0]
        y0 = pc[1]
        self.path = [p]
        for _ in range(nsteps):
            x = math.cos(angle)*x0 - math.sin(angle)*y0
            y = math.sin(angle)*x0 + math.cos(angle)*y0
            self.path.append([c[0] + x, c[1] + y])
            x0 = x
            y0 = y

class MaskViewRegionGrowing(MaskViewPenFreehand):
    """Rectangle region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, radius='default'):

        self.radius = radius
        self.icon = QIcon(widgets.icons.paint)
        pixMap = QPixmap(widgets.icons.paint)
        self.cursor = QCursor(pixMap, hotX=0, hotY=16)
        self.toolTip = 'Select a Region to Paint'
        self.center = None
        self.path = None
    
    def setRadius(self, radius):
        self.radius = radius

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            self.center = [event.pos().x(), event.pos().y()]
            im = self.item.image
            array = im.array()
            img_array_Blurred = cv2.GaussianBlur(array, (3,3),cv2.BORDER_DEFAULT)
            if self.radius == 'default':
                radius = 3
                seedThreshold = 1.5*np.sqrt(np.var(img_array_Blurred[int(self.center[0])-int(radius):int(self.center[0])+int(radius),int(self.center[1])-int(radius):int(self.center[1])+int(radius)]))
                if seedThreshold >np.sqrt(np.var(img_array_Blurred))*0.1:
                    seedThreshold=np.sqrt(np.var(img_array_Blurred))*0.1
                #print(seedThreshold)
            elif self.radius != 'default':
                radius = self.radius
                seedThreshold = 1.5*np.sqrt(np.var(img_array_Blurred[int(self.center[0])-int(radius):int(self.center[0])+int(radius),int(self.center[1])-int(radius):int(self.center[1])+int(radius)]))

            seeds = [Point(int(self.center[0]),int(self.center[1]))]
            pixels = regionGrow(img_array_Blurred,seeds,seedThreshold)
            yx_corr = np.column_stack(np.where(pixels==1))                
            for p in yx_corr: self.maskItem.setPixel(p[0],p[1],True)
            self.path = None
            self.maskItem.update()

        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)
            
    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        #buttons = event.buttons()

    def launchContextMenu(self, event):

 
        onePixel = QAction('Default', None)
        onePixel.setCheckable(True)
        onePixel.setChecked(self.radius == 'default')
        onePixel.triggered.connect(lambda: self.setRadius('default'))

        threePixels = QAction('3 pixels', None)
        threePixels.setCheckable(True)
        threePixels.setChecked(self.radius == 3)
        threePixels.triggered.connect(lambda: self.setRadius(3))

        fivePixels = QAction('5 pixels', None)
        fivePixels.setCheckable(True)
        fivePixels.setChecked(self.radius == 5)
        fivePixels.triggered.connect(lambda: self.setRadius(5))

        sevenPixels = QAction('7 pixels', None)
        sevenPixels.setCheckable(True)
        sevenPixels.setChecked(self.radius == 7)
        sevenPixels.triggered.connect(lambda: self.setRadius(7))

        contextMenu = QMenu()
        subMenu = contextMenu.addMenu('Radius')
        subMenu.setEnabled(True)
        # subMenu.clear()
        subMenu.addAction(onePixel)
        subMenu.addAction(threePixels)
        subMenu.addAction(fivePixels)
        subMenu.addAction(sevenPixels)
        contextMenu.exec_(event.screenPos())

class MaskViewEdgeDetection(MaskViewPenFreehand):
    """Rectangle region drawing tool.
    
    Features
    --------
    >>> Left click and drag to draw, release to close
    >>> Right click to change the pen properties
    """

    def __init__(self, mode="draw"):
        super().__init__(mode=mode)

        self.icon = QIcon(widgets.icons.wand_hat)
        pixMap = QPixmap(widgets.icons.wand)
        self.cursor = QCursor(pixMap, hotX=0, hotY=16)
        self.toolTip = 'Select a Region to Detect'
        self.center = None

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            p = [int(event.pos().x()), int(event.pos().y())]
            self.edgeCalculation(p)
            self.maskItem.update()

        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)
            
    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

    
    def edgeCalculation(self,p):

        im = self.item.image
        array = im.array()
        pixelSize = im.PixelSpacing
        pixels = kidneySegmentation(array,p[1],p[0],pixelSize,side=None)
        yx_corr = np.column_stack(np.where(pixels==1))                
        for p in yx_corr: self.maskItem.setPixel(p[0],p[1],True)
        self.path = None
        self.maskItem.update
    
    

class MaskViewErode(MaskViewPenFreehand):
    """Erode Button.
    
    Features
    --------
    >>> Left click to erode the corresponding mask
    """

    def __init__(self, kernelSize=3, mode="SingleROI"):
        super().__init__(mode=mode)

        self.setkernelSize(kernelSize)

        self.icon = QIcon(widgets.icons.arrow_in)
        pixMap = QPixmap(widgets.icons.paint_brush_minus)
        self.cursor = QCursor(pixMap, hotX=0, hotY=16)
        self.toolTip = 'Erode'
        self.center = None

    def setMode(self, mode):

        self.mode = mode
        if mode == "SingleROI":
            self.toolTip = 'Single ROI'
        elif mode == "AllROI":
            self.toolTip = 'All ROIs'
    
    def setkernelSize(self, kernelSize):
        self.kernelSize = kernelSize

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            p = [self.x, self.y]
            im = self.maskItem.bin.astype(np.uint8)
            if self.mode == "SingleROI":
                if im[p[0],p[1]] ==1:
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize))
                    seeds = [Point(p[0],p[1])]
                    pixels = regionGrow(im,seeds,1)                
                    im = im*pixels
                else:
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize))
            if self.mode == "AllROI":
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize))
                
            im_eroded = cv2.erode(im, kernel)
            pixels = im-im_eroded
            yx_corr = np.column_stack(np.where(pixels==1))                
            for p in yx_corr: self.maskItem.setPixel(p[0],p[1],False)
            self.maskItem.update()

        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)

    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

    
    def launchContextMenu(self, event):


        pickSingleROI = QAction('Single ROI', None)
        pickSingleROI.setCheckable(True)
        pickSingleROI.setChecked(self.mode == "SingleROI")
        pickSingleROI.triggered.connect(lambda: self.setMode("SingleROI"))
        
        pickAllROI = QAction('All ROIs', None)
        pickAllROI.setCheckable(True)
        pickAllROI.setChecked(self.mode == "AllROI")
        pickAllROI.triggered.connect(lambda: self.setMode("AllROI"))

        contextMenu = QMenu()
        contextMenu.addAction(pickSingleROI)
        contextMenu.addAction(pickAllROI)
 
        onePixel = QAction('1 pixel', None)
        onePixel.setCheckable(True)
        onePixel.setChecked(self.kernelSize == 1)
        onePixel.triggered.connect(lambda: self.setkernelSize(1))

        threePixels = QAction('3 pixels', None)
        threePixels.setCheckable(True)
        threePixels.setChecked(self.kernelSize == 3)
        threePixels.triggered.connect(lambda: self.setkernelSize(3))

        fivePixels = QAction('5 pixels', None)
        fivePixels.setCheckable(True)
        fivePixels.setChecked(self.kernelSize == 5)
        fivePixels.triggered.connect(lambda: self.setkernelSize(5))

        sevenPixels = QAction('7 pixels', None)
        sevenPixels.setCheckable(True)
        sevenPixels.setChecked(self.kernelSize == 7)
        sevenPixels.triggered.connect(lambda: self.setkernelSize(7))

        ninePixels = QAction('9 pixels', None)
        ninePixels.setCheckable(True)
        ninePixels.setChecked(self.kernelSize == 9)
        ninePixels.triggered.connect(lambda: self.setkernelSize(9))

        elevenPixels = QAction('11 pixels', None)
        elevenPixels.setCheckable(True)
        elevenPixels.setChecked(self.kernelSize == 11)
        elevenPixels.triggered.connect(lambda: self.setkernelSize(11))

        twentyOnePixels = QAction('21 pixels', None)
        twentyOnePixels.setCheckable(True)
        twentyOnePixels.setChecked(self.kernelSize == 21)
        twentyOnePixels.triggered.connect(lambda: self.setkernelSize(21))

        contextMenu = QMenu()
        contextMenu.addAction(pickSingleROI)
        contextMenu.addAction(pickAllROI)
        subMenu = contextMenu.addMenu('Kernel size')
        subMenu.setEnabled(True)
        # subMenu.clear()
        subMenu.addAction(onePixel)
        subMenu.addAction(threePixels)
        subMenu.addAction(fivePixels)
        subMenu.addAction(sevenPixels)
        subMenu.addAction(ninePixels)
        subMenu.addAction(elevenPixels)
        subMenu.addAction(twentyOnePixels)
        contextMenu.exec_(event.screenPos())

class MaskViewDilate(MaskViewPenFreehand):
    """Erode Button.
    
    Features
    --------
    >>> Left click to erode the corresponding mask
    """

    def __init__(self, kernelSize=3, mode="SingleROI"):
        super().__init__(mode=mode)

        self.setkernelSize(kernelSize)

        self.icon = QIcon(widgets.icons.arrow_out)
        pixMap = QPixmap(widgets.icons.paint_brush_plus)
        self.cursor = QCursor(pixMap, hotX=0, hotY=16)
        self.toolTip = 'Dilate'
        self.center = None

    def setMode(self, mode):

        self.mode = mode
        if mode == "SingleROI":
            self.toolTip = 'Single ROI'
        elif mode == "AllROI":
            self.toolTip = 'All ROIs'
    
    def setkernelSize(self, kernelSize):
        self.kernelSize = kernelSize

    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

        if event.button() == Qt.LeftButton:
            p = [self.x, self.y]
            im = self.maskItem.bin.astype(np.uint8)
            if self.mode == "SingleROI":

                if im[p[0],p[1]] ==1:
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize))
                    seeds = [Point(p[0],p[1])]
                    pixels = regionGrow(im,seeds,1)
                    im = im*pixels
                else:
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize)) #display a message that no ROI was selected
            elif self.mode == "AllROI":
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.kernelSize, self.kernelSize))

            im_dilated = cv2.dilate(im, kernel)#
            pixels = im_dilated-im
            yx_corr = np.column_stack(np.where(pixels==1))                
            for p in yx_corr: self.maskItem.setPixel(p[0],p[1],True)
            self.maskItem.update()
        
        elif event.button() == Qt.RightButton:
            self.launchContextMenu(event)

    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

    def launchContextMenu(self, event):

        pickSingleROI = QAction('Single ROI', None)
        pickSingleROI.setCheckable(True)
        pickSingleROI.setChecked(self.mode == "SingleROI")
        pickSingleROI.triggered.connect(lambda: self.setMode("SingleROI"))
        
        pickAllROI = QAction('All ROIs', None)
        pickAllROI.setCheckable(True)
        pickAllROI.setChecked(self.mode == "AllROI")
        pickAllROI.triggered.connect(lambda: self.setMode("AllROI"))

        onePixel = QAction('1 pixel', None)
        onePixel.setCheckable(True)
        onePixel.setChecked(self.kernelSize == 1)
        onePixel.triggered.connect(lambda: self.setkernelSize(1))

        threePixels = QAction('3 pixels', None)
        threePixels.setCheckable(True)
        threePixels.setChecked(self.kernelSize == 3)
        threePixels.triggered.connect(lambda: self.setkernelSize(3))

        fivePixels = QAction('5 pixels', None)
        fivePixels.setCheckable(True)
        fivePixels.setChecked(self.kernelSize == 5)
        fivePixels.triggered.connect(lambda: self.setkernelSize(5))

        sevenPixels = QAction('7 pixels', None)
        sevenPixels.setCheckable(True)
        sevenPixels.setChecked(self.kernelSize == 7)
        sevenPixels.triggered.connect(lambda: self.setkernelSize(7))

        ninePixels = QAction('9 pixels', None)
        ninePixels.setCheckable(True)
        ninePixels.setChecked(self.kernelSize == 9)
        ninePixels.triggered.connect(lambda: self.setkernelSize(9))

        elevenPixels = QAction('11 pixels', None)
        elevenPixels.setCheckable(True)
        elevenPixels.setChecked(self.kernelSize == 11)
        elevenPixels.triggered.connect(lambda: self.setkernelSize(11))

        twentyOnePixels = QAction('21 pixels', None)
        twentyOnePixels.setCheckable(True)
        twentyOnePixels.setChecked(self.kernelSize == 21)
        twentyOnePixels.triggered.connect(lambda: self.setkernelSize(21))

        contextMenu = QMenu()
        contextMenu = QMenu()
        contextMenu.addAction(pickSingleROI)
        contextMenu.addAction(pickAllROI)
        subMenu = contextMenu.addMenu('Kernel size')
        subMenu.setEnabled(True)
        # subMenu.clear()
        subMenu.addAction(onePixel)
        subMenu.addAction(threePixels)
        subMenu.addAction(fivePixels)
        subMenu.addAction(sevenPixels)
        subMenu.addAction(ninePixels)
        subMenu.addAction(elevenPixels)
        subMenu.addAction(twentyOnePixels)
        contextMenu.exec_(event.screenPos())

class MaskViewDeleteROI(MaskViewPenFreehand):
    """Delete ROI Button.
    
    Features
    --------
    >>> Left click to delete the corresponding mask
    """

    def __init__(self):

        self.icon = QIcon(widgets.icons.paint_can_minus)
        pixMap = QPixmap(widgets.icons.paint_can_minus)
        self.cursor = QCursor(pixMap, hotX=0, hotY=16)
        self.toolTip = 'Delete ROI'
        self.center = None
        self.path = None
    
    def itemMousePressEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())
        if event.button() == Qt.LeftButton:
            p = [self.x, self.y]
            im = self.maskItem.bin.astype(np.uint8)
            if im[p[0],p[1]] ==1:
                seeds = [Point(p[0],p[1])]
                pixels = regionGrow(im,seeds,1)
                yx_corr = np.column_stack(np.where(pixels==1))                
                for p in yx_corr: self.maskItem.setPixel(p[0],p[1],False)
                self.maskItem.update()
            else:
                pass #display a message that no ROI was selected

    def itemMouseMoveEvent(self, event):

        self.x = int(event.pos().x())
        self.y = int(event.pos().y())

class Point(object):
 def __init__(self,x,y):
  self.x = x
  self.y = y

 def getX(self):
  return self.x
 def getY(self):
  return self.y

def getGrayDiff(img,currentPoint,tmpPoint):
 return abs(int(img[currentPoint.x,currentPoint.y]) - int(img[tmpPoint.x,tmpPoint.y]))

def selectConnects(p):
 if p != 0:
  connects = [Point(-1, -1), Point(0, -1), Point(1, -1), Point(1, 0), Point(1, 1), \
     Point(0, 1), Point(-1, 1), Point(-1, 0)]
 else:
  connects = [ Point(0, -1), Point(1, 0),Point(0, 1), Point(-1, 0)]
 return connects

def regionGrow(img,seeds,thresh,p = 1):
 height, weight = img.shape
 seedMark = np.zeros(img.shape)
 seedList = []
 for seed in seeds:
  seedList.append(seed)
 label = 1
 connects = selectConnects(p)
 while(len(seedList)>0):
  currentPoint = seedList.pop(0)

  seedMark[currentPoint.x,currentPoint.y] = label
  for i in range(8):
   tmpX = currentPoint.x + connects[i].x
   tmpY = currentPoint.y + connects[i].y
   if tmpX < 0 or tmpY < 0 or tmpX >= height or tmpY >= weight:
    continue
   grayDiff = getGrayDiff(img,currentPoint,Point(tmpX,tmpY))
   if grayDiff < thresh and seedMark[tmpX,tmpY] == 0:
    seedMark[tmpX,tmpY] = label
    seedList.append(Point(tmpX,tmpY))
 return seedMark



def kidneySegmentation(img_array,pixelY,pixelX,pixelSize,side=None):

        img_array_Blurred = cv2.GaussianBlur(img_array, (31,31),cv2.BORDER_DEFAULT)

        KidneyBlurred = np.zeros(np.shape(img_array_Blurred))
        if pixelX>img_array.shape[0]/2:
            KidneyBlurred[int(np.shape(img_array_Blurred)[0]/2):np.shape(img_array_Blurred)[0],:] = img_array_Blurred[int(np.shape(img_array_Blurred)[0]/2):np.shape(img_array_Blurred)[0],:]
        if pixelX<img_array.shape[0]/2:
            KidneyBlurred[0:int(np.shape(img_array_Blurred)[0]/2),:] = img_array_Blurred[0:int(np.shape(img_array_Blurred)[0]/2),:]

        sigmaCanny = 0
        edges = feature.canny(KidneyBlurred, sigma =sigmaCanny)
        edges= edges.astype(np.uint8)
        #plt.imshow(edges)

        maxIteration = 10
        maxIteration_2 =5

        Kidney=[]
        #dilate edges until you find a potential renal contour 
        for j in range(maxIteration):

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(1+j,1+j))
            dilated = cv2.dilate(edges, kernel)
            #plt.imshow(dilated)
            cnts_Kidney,hierarchy_Kidney = cv2.findContours(dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            cnts_Kidney = sorted(cnts_Kidney, key=cv2.contourArea, reverse=True)

            #loop through the different contours until you find a potential renal contour 
            for i in range(len(cnts_Kidney)):
                cntTemp = cnts_Kidney[i]
                #print(i)
                #print(cv2.contourArea(cntTemp))
                #print(cv2.pointPolygonTest(cntTemp,(pixelY,pixelX),True))

                #Kidney = cntTemp
                #mask_Kidney = np.ones(np.shape(img_array))
                #cv2.drawContours(mask_Kidney,[Kidney],0,(0,255,0),thickness=cv2.FILLED)
                #mask_Kidney = np.abs(mask_Kidney + 1 - 2)
                #plt.imshow(mask_Kidney)
                #Kidney = []

                if cv2.contourArea(cntTemp)*pixelSize[0]*pixelSize[1]>1500: #check if the area of the contour is suitable with the kidneys

                    dist = cv2.pointPolygonTest(cntTemp,(pixelY,pixelX),True)
                    
                    if dist > 0:
                        #print('Dilation iteration: ' +str(j))
                        #print('Contour Number: ' +str(i))
                        #print('Distance: ' +str(dist))
                        #print('ROI Area: ' +str(cv2.contourArea(cntTemp)) +' pixels')
                        #print('Son: '+str(hierarchy_Kidney[0,i][2]))
                        #print('Grandfather: '+str(hierarchy_Kidney[0,i][3]))

                        Kidney = cntTemp
                        mask_Kidney = np.ones(np.shape(img_array))
                        cv2.drawContours(mask_Kidney,[Kidney],0,(0,255,0),thickness=cv2.FILLED)
                        mask_Kidney = np.abs(mask_Kidney + 1 - 2)
                        
                        kernel_mask = np.ones((j+3,j+3)).astype(np.uint8)
                        edges_Kidney_new = (cv2.erode(mask_Kidney,kernel_mask)*edges).astype(np.uint8)
                        
                        kernel_new = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(1,1))
                        edges_Kidney_new = cv2.erode(edges_Kidney_new,kernel_new).astype(np.uint8)
                        edges_Kidney_new = cv2.dilate(edges_Kidney_new,kernel_new).astype(np.uint8)

                        edges_Kidney_new_dilated = cv2.dilate(edges_Kidney_new, kernel_new)
                        cnts_Kidney_new,hierarchy_Kidney_new = cv2.findContours(edges_Kidney_new_dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE) 
                        cnts_Kidney_new_Sorted = sorted(cnts_Kidney_new, key=cv2.contourArea, reverse=True)

                        #check if contours needed to be removed from the main mask (nasty pelvis pixels)
                        for i_2 in range(len(cnts_Kidney_new_Sorted)):
                            cntTemp_new = cnts_Kidney_new_Sorted[i_2]
                            if cv2.contourArea(cntTemp_new)==0:
                                break

                            cntHull = cv2.convexHull(cntTemp_new, returnPoints=True)
                            #mask_Kidney_son = np.ones(np.shape(img_array))
                            #cv2.drawContours(mask_Kidney_son,[cntHull],0,(0,255,0),thickness=cv2.FILLED)
                            #plt.imshow(mask_Kidney_son)


                            if (cv2.contourArea(cntHull) < 0.5*cv2.contourArea(cntTemp) and cv2.contourArea(cntHull) > 0.03*cv2.contourArea(cntTemp)):
                                
                                Kidney_son = cntHull

                                mask_Kidney_son = np.ones(np.shape(img_array))
                                cv2.drawContours(mask_Kidney_son,[Kidney_son],0,(0,255,0),thickness=cv2.FILLED)
                                mask_Kidney_son = np.abs(mask_Kidney_son + 1 - 2)
                                mask_Kidney = mask_Kidney - mask_Kidney_son
                                mask_Kidney[mask_Kidney<0]=0

                if Kidney!=[]:
                    #print(' Kindey Found')
                    return mask_Kidney
