# -*- coding: utf-8 -*-
"""
Created on Wed Mar  7 12:55:44 2018

@author: dnor
"""

import sys

""" Qt5 dependent stuff """
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5 import uic, QtCore, QtGui, QtWidgets

""" The actual Qt-ui setup """
from shapeinspector import Ui_ShapeInspector as UII

""" All stuff needed for plotting """
from matplotlib.pyplot import cm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D
import matplotlib as m
import numpy as np

# Stupid warning when casting imaginary part
import warnings
warnings.filterwarnings("ignore")

class allDataC:
    """ All the data needed for easy control """
    def __init__(self, mu, n, p, componentAmount, sigma, conlist, L):
        self.mu = mu
        self.n = n
        self.p = p
        self.componentAmount = componentAmount
        self.sigma = sigma
        self.conlist = conlist
        self.L = L

class Application(UII):
    def __init__(self, mainWind, allData):
        super().__init__()
        self.initUI(mainWind, allData)

    def initUI(self, mainWind, allData):
        """ Set-up all qt classes for autocomplete capabilities etc """
        self.verticalSlider_Component_1 = QtWidgets.QSlider()
        self.verticalSlider_Component_2 = QtWidgets.QSlider()
        self.verticalSlider_Component_3 = QtWidgets.QSlider()
        self.verticalSlider_Component_4 = QtWidgets.QSlider()
        self.verticalSlider_Component_5 = QtWidgets.QSlider()
        self.verticalSlider_Component_6 = QtWidgets.QSlider()

        self.pushButton = QtWidgets.QPushButton()

        # UII is the ui created from Qt5 creator and exported as a py object, overrides above pre-defined with "real" attributes
        UII.__init__(self)
        UII.setupUi(self, mainWind)

        # Should stuff them all in a list for ease of looping, but... meh...
        self.verticalSlider_Component_1.valueChanged.connect(self.sliderChanged)
        self.verticalSlider_Component_2.valueChanged.connect(self.sliderChanged)
        self.verticalSlider_Component_3.valueChanged.connect(self.sliderChanged)
        self.verticalSlider_Component_4.valueChanged.connect(self.sliderChanged)
        self.verticalSlider_Component_5.valueChanged.connect(self.sliderChanged)
        self.verticalSlider_Component_6.valueChanged.connect(self.sliderChanged)

        # Make buttons clickable, by connecting to function controlling them
        self.pushButton.clicked.connect(self.resetInstance)

        #, mu = allData.mu, conlist = allData.conlist
        self.facePlot = MyMplCanvas(mainWind, width=5, height=4, dpi=100, mu=allData.mu, conlist=allData.conlist)
        self.verticalLayout_Plot.addWidget(self.facePlot)
        
        # Save the data in the class, so we have it handy
        self.allData = allData

    def sliderChanged(self):
        self.updatePlot()

    def resetInstance(self):
        # Should really have made that loop now
        self.verticalSlider_Component_1.setProperty("value", 50)
        self.verticalSlider_Component_2.setProperty("value", 50)
        self.verticalSlider_Component_3.setProperty("value", 50)
        self.verticalSlider_Component_4.setProperty("value", 50)
        self.verticalSlider_Component_5.setProperty("value", 50)
        self.verticalSlider_Component_6.setProperty("value", 50)
        self.updatePlot()

    def getSliderValues(self):
        shifts = [0] * 6
        shifts[0] = self.verticalSlider_Component_1.value()
        shifts[1] = self.verticalSlider_Component_2.value()
        shifts[2] = self.verticalSlider_Component_3.value()
        shifts[3] = self.verticalSlider_Component_4.value()
        shifts[4] = self.verticalSlider_Component_5.value()
        shifts[5] = self.verticalSlider_Component_6.value()
        return shifts

    def updatePlot(self):
        shifts = self.getSliderValues()
        allData = self.allData
        self.facePlot.updateFacePlot(shifts, allData.mu, allData.conlist, allData.sigma, allData.L)
        self.facePlot.draw()


class MyMplCanvas(FigureCanvas):
    """ Ultimately, this is a QWidget (as well as a FigureCanvasAgg, etc.).
    This is the whole plot object, and can be updated accordingly """

    def __init__(self, parent=None, width=5, height=4, dpi=100, mu=[], conlist=[]):
        """ Set everything plot related, and setup whole plot environment at object creation """
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        FigureCanvas.__init__(self, self.fig)
        self.axes1 = self.fig.add_subplot(1,1,(1,1))
        self.axes1.set_aspect("equal")
        self.line = self.drawShape(mu, conlist, self.axes1)
        self.fig.tight_layout()
        # Set figure such that it rescales with window
        FigureCanvas.setSizePolicy(self,
                QSizePolicy.Expanding,
                QSizePolicy.Expanding)
        
        FigureCanvas.updateGeometry(self)

    def drawShape(self, mu, conlist, ax, color="b"):
        for i in range(len(conlist)): # How many different lines exist in the data (7)
            xpoints = mu[conlist[i,0]:conlist[i,1]+1]
            ypoints = mu[conlist[i,0] +  58:conlist[i,1] + 59]
        
            if conlist[i][2] == 1: # If it is a closed loop
                xpoints = np.append(xpoints, xpoints[0]) 
                ypoints = np.append(ypoints, ypoints[0])
            ax.plot(xpoints, ypoints, color = color)
        ax.axis('equal')

    def updateFacePlot(self, shifts, mu, conlist, sigma, L):
        # Clear old axes
#        self.axes1.clear()
#        scaled_plot = np.copy(allData.mu)
#        for ind, value in enumerate(shifts):
#            shiftVal = (value - 50) / 10 # Scale
#            scaled_plot += np.sqrt(sigma[ind]) * shiftVal * allData.L[:,ind]
#        self.drawShape(scaled_plot, allData.conlist, self.axes1)
        self.axes1.clear()
        scaled_plot = np.copy(mu)
        for ind, value in enumerate(shifts):
            shiftVal = (value - 50) / 10 # Scale
            scaled_plot += np.sqrt(sigma[ind]) * shiftVal * L[:,ind]
        self.drawShape(scaled_plot, conlist, self.axes1)

def runGUI(allData):

    app = QApplication(sys.argv)
    mainWind = QMainWindow()
    ex = Application(mainWind, allData)

    mainWind.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    from PythonWeek6GetData import getVarsWeek6
    # Get vars week 6 has a input var that controls data path, if you want to execute it directly
    # Control says if a different scheme, rotation, verimax or elastic net should be used for choosing the PCA
    # Control Values;
    # 0 / nothing = PCA
    # 1 = Threshold 0.15
    # 2 = Verimax
    # 3 = Elastic net
    n, p, L, X, conlist, Xc, mu, sigma2, S = getVarsWeek6(control=0)
    allData = allDataC(mu, n, p, 6, sigma2, conlist, L)
    runGUI(allData)
