"""
Radar tile geometry + frame compositing.

Ported from PyQtPiClock.py:
  - the tile-grid setup in Radar.__init__ (lines 1647-1708)
  - combineTiles() (lines 1786-1828)

Unlike the old code (which kept the basemap and the radar overlay as two
stacked QLabels), build_frame() composites the radar tiles *onto a copy of the
basemap* and returns a single QImage per frame. QImage is used throughout so
this can run on a worker thread; QPixmap conversion (if any) happens on the GUI
thread in the widget.
"""

from PyQt5.QtGui import QImage, QPainter

from radar.mercator import LatLng, getCorners, getTileXY

TILE = 256


class RadarGeometry:
    """Computes the slippy-tile grid covering a width x height viewport."""

    def __init__(self, center_lat, center_lng, zoom, width, height):
        self.zoom = zoom
        self.width = width
        self.height = height
        center = LatLng(center_lat, center_lng)

        corners = getCorners(center, zoom, width, height)
        self.cornerTiles = {
            "NW": getTileXY(LatLng(corners["N"], corners["W"]), zoom),
            "NE": getTileXY(LatLng(corners["N"], corners["E"]), zoom),
            "SE": getTileXY(LatLng(corners["S"], corners["E"]), zoom),
            "SW": getTileXY(LatLng(corners["S"], corners["W"]), zoom),
        }

        # Tile (X, Y) integer indices, row-major (y outer, x inner) — the same
        # order combine() walks, so a fetched-image list lines up by index.
        self.tiles = []
        self.tilesHeight = 0
        self.tilesWidth = 0
        for y in range(int(self.cornerTiles["NW"]["Y"]),
                        int(self.cornerTiles["SW"]["Y"]) + 1):
            self.tilesHeight += 1
            for x in range(int(self.cornerTiles["NW"]["X"]),
                           int(self.cornerTiles["NE"]["X"]) + 1):
                self.tiles.append((x, y))
        for _ in range(int(self.cornerTiles["NW"]["X"]),
                       int(self.cornerTiles["NE"]["X"]) + 1):
            self.tilesWidth += 1

        self.totalWidth = self.tilesWidth * TILE
        self.totalHeight = self.tilesHeight * TILE

    def __eq__(self, other):
        return (isinstance(other, RadarGeometry)
                and self.zoom == other.zoom
                and self.width == other.width
                and self.height == other.height
                and self.tiles == other.tiles)


def build_frame(basemap, tile_images, geom):
    """
    Composite `tile_images` (in geom.tiles order) over a copy of `basemap`.

    Returns a width x height QImage. Tiles that failed to load (None / empty)
    are simply skipped, so partial frames still draw the basemap.
    """
    # 1. Assemble the radar tiles into one big overlay image.
    overlay = QImage(geom.totalWidth, geom.totalHeight, QImage.Format_ARGB32)
    overlay.fill(0)  # transparent
    painter = QPainter(overlay)
    i = 0
    for y in range(0, geom.totalHeight, TILE):
        for x in range(0, geom.totalWidth, TILE):
            if i < len(tile_images):
                img = tile_images[i]
                if img is not None and not img.isNull():
                    painter.drawImage(x, y, img)
            i += 1
    painter.end()

    # 2. Crop the overlay to the viewport using the fractional tile offset.
    xo = _corner_offset(geom, "X")
    yo = _corner_offset(geom, "Y")
    cropped = overlay.copy(-xo, -yo, geom.width, geom.height)

    # 3. Paint the overlay onto a copy of the basemap.
    result = basemap.copy(0, 0, geom.width, geom.height)
    p2 = QPainter(result)
    p2.drawImage(0, 0, cropped)
    p2.end()
    return result


def _corner_offset(geom, axis):
    v = geom.cornerTiles["NW"][axis]
    return int((int(v) - v) * TILE)
