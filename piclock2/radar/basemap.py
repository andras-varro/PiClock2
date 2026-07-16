"""
Mapbox Static Images basemap URL builder.

Ported from PyQtPiClock.py mapboxurl() (lines 1841-1855). Mapbox uses 512px
tiles, so its zoom is one less than the Google/slippy (256px-tile) zoom that the
rainviewer tiles and the Mercator math use; we subtract 1 here so the basemap
covers exactly the same geographic span as the composited radar tiles.
"""


def mapbox_url(center_lat, center_lng, zoom, width, height, style, token):
    """
    Static-images URL centered on (lat, lng).

    `zoom` is the Google/slippy zoom (same one used for the radar tiles);
    we hand Mapbox zoom-1 to account for its 512px tiles.
    """
    return (
        "https://api.mapbox.com/styles/v1/" + style + "/static/"
        + str(center_lng) + "," + str(center_lat) + ","
        + str(zoom - 1) + ",0,0/"
        + str(width) + "x" + str(height)
        + "?access_token=" + token
    )
