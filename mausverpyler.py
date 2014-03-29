__author__ = 'Ronny Eichler'

# System libraries
import sys
import logging

# Aux libraries
from lib.pyqtgraph import QtGui, QtCore  # ALL HAIL LUKE!
import lib.pyqtgraph as pg
import cv2

# try avoiding these annoying mscvr90d.dll errors on Windows
pg.functions.USE_WEAVE = False
pg.setConfigOption('useWeave', False)

# core libraries
from lib.core.FrameSource import FrameSource
from lib.core.Tracker import Tracker

# User interface
from lib.ui import MainWindowUi

NO_EXIT_CONFIRMATION = True


class Main(QtGui.QMainWindow):

    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(__name__)

        # control state flags
        self.playing = False
        self.paused = False
        self.repeat = True

        self.frame = None  # currently handled (shown, processed, etc.) frame
        self.source = None
        self.ptr = 0  # pointer to store the index of the currently handled frame
        self.rois = None  # list of regions of interest
        self.last_active_roi = None

        # Main Window stuff
        QtGui.QMainWindow.__init__(self)
        self.ui = MainWindowUi.Ui_MainWindow()
        self.ui.setupUi(self)
        # File Menu
        self.ui.action_Quit.setShortcut('Ctrl+Q')
        self.ui.action_Quit.setStatusTip('Quit MicePyFiler')
        self.connect(self.ui.action_Quit, QtCore.SIGNAL('triggered()'), QtCore.SLOT('close()'))
        self.ui.actionShow_Mask.triggered.connect(self.toggle_mask)

        self.ui.action_Open.setShortcut('Ctrl+O')
        self.ui.action_Open.setStatusTip('Open Video File')
        self.ui.action_Open.triggered.connect(self.file_open_video)

        # Toolbar
        self.ui.action_Play.toggled.connect(self.toggle_play)
        self.ui.actionPause.toggled.connect(self.toggle_pause)
        self.ui.actionRepeat.toggled.connect(self.toggle_repeat)
        self.ui.actionFastForward.triggered.connect(self.fast_forward)
        self.ui.actionRewind.triggered.connect(self.rewind)

        # Central Video Frame
        self.vb = pg.ViewBox()
        self.ui.gv_video.setCentralItem(self.vb)
        self.vb.setAspectLocked()
        self.img = pg.ImageItem()
        self.vb.addItem(self.img)
        self.vb.setRange(QtCore.QRectF(0, 0, 640, 380))
        #self.vb.disableAutoRange('xy'); self.vb.autoRange()
        self.ui.scrollbar_time.valueChanged.connect(self.slider_changed)

        # Detail Video Frame
        # image is taken from the main video frame based on a ROI
        self.vb_detail = pg.ViewBox()
        self.ui.gv_detail.setCentralItem(self.vb_detail)
        self.vb_detail.setAspectLocked()
        self.img_detail = pg.ImageItem()
        self.vb_detail.addItem(self.img_detail)
        self.vb_detail.setRange(QtCore.QRectF(0, 0, 100, 100))

        # UI refresh timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(30)

        self.tracker = Tracker

    def populate_rois(self, w, h):
        """ Generate a bunch of regions of interest and throw them all over the video frame
        to play around with.

        Ultimately, ROIs will be used for tracking and feedback.

        Updates rest of UI (labels, statusbars etc.)
        """
        self.rois = list()
        #self.rois.append(pg.LineROI([0, 60], [20, 80], width=5, pen=(1, 9)))
        #self.rois.append(pg.MultiRectROI([[20, 90], [50, 60], [60, 90]], width=5, pen=(2, 9)))
        self.rois.append(pg.RectROI([w*.2, h*.2], [w*.2, h*.2], pen=(0, 9)))
        self.rois[-1].addRotateHandle([1, 0], [0.5, 0.5])
        self.rois.append(pg.EllipseROI([w*.4, h*.2], [w*.2, h*.2], pen=(3, 9)))
        self.rois.append(pg.CircleROI([w*.8, h*.2], [w*.2, h*.2], pen=(4, 9)))
        for roi in self.rois:
            roi.sigRegionChanged.connect(self.activate_roi)
            self.vb.addItem(roi)

    def activate_roi(self, roi):
        """ Tag last used ROI. This one will from now on be used to select the image region that is
        displayed in the detail view.
        """
        if self.last_active_roi is not roi:
            self.last_active_roi = roi

    def update_roi(self, roi=None):
        """ Updating ROIs uses position and shape to extract a sub-region of the main video frame image
        and display this smaller detail view.
        """
        if roi is None:
            return
        if self.source is not None:
            if self.source.color:
                # Color images may require some more work, as far as I can see, getArrayRegion only works on
                # 2D arrays. Will have to do it three times, use masking, or get the bounding box?
                self.img_detail.setImage(roi.getArrayRegion(self.source.current_frame[..., 0], self.img), autoLevels=False)
            else:
                self.img_detail.setImage(roi.getArrayRegion(self.source.current_frame, self.img), autoLevels=False)

                # do some dummy tracking here


            self.vb_detail.autoRange()
            self.last_active_roi = roi

    def update(self, *args, **kwargs):
        """ Main UI update function.

        Requests new frame based on current playback state flags (playing, paused) and source availability.

        Requests thresholding of current frame, if masking flag (checkbox/action) is set.
        """
        if self.source is not None:

            # Grab next/new/current frame from source
            if self.playing and not self.paused:
                self.source.next()
            else:
                if not self.ptr == self.source.index:
                    self.source.grab(self.ui.scrollbar_time.value())

            # Threshold/Masking
            if self.ui.ckb_bin_thresh.isChecked():
                self.source.bin_thresh(self.ui.spin_bin_thresh.value())
                self.frame = self.source.mask
            else:
                self.frame = self.source.current_frame

            # Update video frame
            self.img.setImage(self.frame, autoLevels=False)
            self.ui.scrollbar_time.setValue(self.source.index)
            self.ptr = self.source.index

            # automatically reset zoom on first frame
            if self.ptr == 2:
                self.vb.autoRange()

            # refresh detail frame with last used ROI
            if self.rois:
                self.update_roi(self.last_active_roi)

            # refresh position labels
            self.ui.lbl_frame_num.setText('Frame %d/%d' % (self.ptr, self.source.num_frames))
            ms = self.source.pos_time
            h = int(ms/3600000)
            m = int((ms-h*360000)/60000)
            s = int((ms-m*6000)/1000)
            ms = int(ms-s*1000)
            self.ui.lbl_frame_time.setText('{:0>2d}:{:0>2d}:{:0>2d}.{:0>3d}'.format(h, m, s, ms))

    def slider_changed(self, val):
        """ Video index slider was changed by the user. This will move the index to open the next frame
        from to the new value. Actually loading the next frame etc. is done in the update() function.

        TODO: This should ideally trigger caching frames near the new position, maybe with a small time
        to only start caching large amounts of frames once the scrollbar was released.
        """
        self.ptr = self.ui.scrollbar_time.value()

    def toggle_play(self):
        """ Start playback of video source sequence. """
        self.playing = self.ui.action_Play.isChecked()
        if not self.playing:
            self.ui.actionPause.setChecked(False)
            self.ui.actionPause.setEnabled(False)
        else:
            self.ui.actionPause.setEnabled(True)

    def toggle_pause(self):
        """ Pause playback at current frame. Right now, there is not really a difference
        between not playing, and being paused.
        """
        self.paused = self.ui.actionPause.isChecked()

    def toggle_repeat(self):
        """ Continuously loop over source sequence. """
        self.repeat = self.ui.actionRepeat.isChecked()
        if self.source is not None:
            self.source.repeat = self.repeat

    def rewind(self):
        """ Jump to first frame. """
        if self.source is not None:
            self.source.rewind()

    def fast_forward(self):
        """ Jump to last frame. """
        if self.source is not None:
            self.source.fast_forward()

    def toggle_mask(self):
        # TODO: Needs to update action state when checkbox is changed, too.
        self.ui.ckb_bin_thresh.setChecked(self.ui.actionShow_Mask.isChecked())

    def file_open_video(self, rv, path='./examples'):
        """ Open a video file. Should  close currently opened video.
        TODO: Open file dialog in a useful folder. E.g. store the last used one
        """
        # Windows 7 uses 'HOMEPATH' instead of 'HOME'
        #path = os.getenv('HOME')
        #if not path:
        # path = os.getenv('HOMEPATH')
        filename = QtGui.QFileDialog.getOpenFileName(self, 'Open Video', path, 'Video: *.avi; *.mpg; *.mp4 ;; All Files: *.*')  # , *.mpg, *.mp4, *.mpeg, *.mkv;; *.wav, *.mp3, *.flac
        if len(filename):
            self.log.debug('File dialog given %s', str(filename))
            self.ui.statusbar.showMessage('Opened %s' % filename, 2000)
            self.ui.gb_video.setTitle(filename)
            self.new_source(str(filename))

    def new_source(self, source=None):
        """ Open a new data source. If an old one exists, tell it to close itself in
        case open file handles are involved. """
        if self.source is not None:
            self.source.close()

        self.source = FrameSource(source)
        if self.rois is None:
            self.populate_rois(self.source.width, self.source.height)
            self.last_active_roi = self.rois[0]

        self.source.repeat = self.repeat
        self.ui.action_Play.setChecked(True)
        if self.source.num_frames > 0:
            self.ui.scrollbar_time.setEnabled(True)
            self.ui.scrollbar_time.setMaximum(self.source.num_frames-1)
        else:
            self.ui.scrollbar_time.setEnabled(True)
            self.ui.scrollbar_time.setMaximum(1)

    def closeEvent(self, event):
        """ Exiting the interface """
        if NO_EXIT_CONFIRMATION:
            reply = QtGui.QMessageBox.Yes
        else:
            reply = QtGui.QMessageBox.question(self, 'Exiting...', 'Are you sure?',
                                               QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            # close core loops here...
            event.accept()
        else:
            event.ignore()


#############################################################
def main(*args, **kwargs):
    app = QtGui.QApplication([])
    window = Main(*args, **kwargs)
    window.show()
    window.raise_()  # needed on OSX?

    sys.exit(app.exec_())

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()