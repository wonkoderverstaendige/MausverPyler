__author__ = 'Ronny Eichler'

import cv2


class Tracker(object):

    def __init__(self):
        self.frame = None

    @staticmethod
    def pre_process(frame, method=None):
        return frame

    @staticmethod
    def threshold(frame, method=None):
        if method is None:
            rv = False
        elif method == 1:
            blur = cv2.GaussianBlur(frame, (5, 5), 0)
            rv, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)

        elif method == 2:
            rv = False

        if rv:
            return th

    @staticmethod
    def find_contour(frame, range_area=(20, 2000), method=None):
        """
        Return contour with largest area. Returns None if no contour within
        admissible range_area is found.
        """
        contours, hierarchy = cv2.findContours(frame, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        largest_area = 0
        best_cnt = None
        min_area = range_area[0]
        max_area = range_area[1]
        for cnt in contours:
            area = cv2.contourArea(cnt.astype(int))
            if area > largest_area and area >= min_area:
                if max_area == 0 or area < max_area:
                    largest_area = area
                    best_cnt = cnt
        return largest_area, best_cnt

    def track(self, frame):
        # pre-process
        pp = self.pre_process(frame)

        # threshold
        th = self.threshold(pp)

        # find contours
        contour_area, contour = self.find_contour(th)

        # sort out contours
        if contour is not None:
            moments = cv2.moments(contour.astype(int))
            cx = moments['m10']/moments['m00']
            cy = moments['m01']/moments['m00']
            # if frame_offset:
            #     cx += ax
            #     cy += ay
            return cx, cy
        else:
            # Couldn't find a good enough spot
            return None
