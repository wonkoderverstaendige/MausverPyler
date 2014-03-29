import logging
import cv2

__author__ = 'Ronny Eichler'


class FrameSource(object):

    current_frame = None
    mask = None
    _ptr = 0
    repeat = True
    width = None
    height = None

    def __init__(self, source, color=False):
        self.log = logging.getLogger(__name__)

        assert source is not None
        self.capture = cv2.VideoCapture(source)
        assert self.capture.isOpened()
        self.color = color

    def grab(self, index=0):
        """ Actually read a new frame at given index.

        Setting color flag to False will convert frames to greyscale.
        """
        if index != self.index:
            self.index = index
            rv, frame = self.capture.read()
            if rv:
                if self.color:
                    self.current_frame = cv2.transpose(cv2.cvtColor(frame, code=cv2.COLOR_BGR2RGB))
                else:
                    self.current_frame = cv2.transpose(cv2.cvtColor(frame, code=cv2.COLOR_BGR2GRAY))
                return self.current_frame

    def bin_thresh(self, thresh=127, type='to_zero'):
        """ Thresholding of the current frame. Result is stored in the mask.
        """
        rv, self.mask = cv2.threshold(self.current_frame, thresh, 255, cv2.THRESH_BINARY_INV)
        #rv, self.mask = cv2.threshold(self.current_frame, thresh, 255, type=cv2.THRESH_TOZERO)
        return self.mask

    def rewind(self):
        """ Jump to first frame in source sequence. """
        self.log.debug('rewinding')
        self.index = 0

    def fast_forward(self):
        """ Jump to last frame in source sequence. """
        self.log.debug('fast-forwarding')
        self.index = self.num_frames - 1

    def next(self):
        """ Grab the next frame in the source sequence. """
        return self.grab(self.index + 1)

    def __getitem__(self, index):
        # here shall be some buffering and pre-caching magic take place
        return self.grab(index)

    @property
    def num_frames(self):
        if self.capture is not None:
            return int(self.capture.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))

    @property
    def index(self):
        return int(self.capture.get(cv2.cv.CV_CAP_PROP_POS_FRAMES))
    @index.setter
    def index(self, index):
        index = int(index)
        if index < 0:
            index = 0
        if index >= self.num_frames:
            if self.repeat:
                index = 0
            else:
                index = self.num_frames - 1

        # if the current pointer is not the same as requested, update and seek in video file
        # (not sure about performance of the seeking, I'll avoid doing it all the time)
        # NB! Potential death trap thanks to float<>int conversions!??
        if self.index != index:
            self.capture.set(cv2.cv.CV_CAP_PROP_POS_FRAMES, float(index))

    @property
    def pos_time(self):
        return self.capture.get(cv2.cv.CV_CAP_PROP_POS_MSEC)

    @property
    def width(self):
        """ Width of the source frames. """
        return self.capture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)

    @property
    def height(self):
        """ Height of the source frames. """
        return self.capture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)

    def close(self):
        """ Release the source capture object.

        TODO: Release/remove cached images or empty buffer.
        """
        if self.capture is not None:
            self.capture.release()