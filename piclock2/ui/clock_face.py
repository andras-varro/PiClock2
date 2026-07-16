import datetime
import math
import os

from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import (
    QPainter, QPixmap, QFont, QFontMetricsF, QColor, QPen, QBrush
)
from PyQt5.QtWidgets import QWidget

from astronomy import suntimes, moon_phase, moon_phase_name


class ClockFace(QWidget):
    """
    Big centered analog clock.

    Paint order:
        1. Clock face PNG (scaled to fit)
        2. Date text arc'd along inside top of dial
        3. Sun/moon text arc'd along inside bottom of dial
        4. Hour, minute, second hands (rotated)
    """

    def __init__(self, assets_dir: str, app_state, parent=None):
        super().__init__(parent)
        self.assets_dir = assets_dir
        self.app_state = app_state

        # Source pixmaps — load once.
        self.face_pix = self._load("clockface3.png")
        self.hour_pix = self._load("hourhand.png")
        self.min_pix = self._load("minhand.png")
        self.sec_pix = self._load("sechand.png")

        # Cached strings (recomputed when location/date changes).
        self._date_str = ""
        self._sunmoon_str = ""
        self._cached_for_location = -1
        self._cached_for_day = None
        self._refresh_strings()

        # Render caches keyed by dial size. The face + arc text are static for a
        # given size/string set, so we composite them into one pixmap once and
        # just blit it (plus the rotated hands) on every tick. This keeps the
        # 1 Hz repaint cheap on the Pi — important when an x11vnc encoder is also
        # competing for CPU.
        self._bg_pix = QPixmap()          # face + arc text, sized to the dial
        self._bg_side = -1
        self._bg_strings = None
        self._hands_side = -1
        self._hour_scaled = QPixmap()
        self._min_scaled = QPixmap()
        self._sec_scaled = QPixmap()

        # 1 Hz tick.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

        self.app_state.location_changed.connect(self._on_location_changed)

        self.setMinimumSize(400, 400)

    def _load(self, name: str):
        path = os.path.join(self.assets_dir, "images", name)
        pix = QPixmap(path)
        if pix.isNull():
            print("clock_face: missing or unreadable", path)
        return pix

    def _on_tick(self):
        # Cheap path: just repaint. Date/sun/moon recomputed only when day changes.
        now = datetime.datetime.now()
        if self._cached_for_day != now.date():
            self._refresh_strings()
        self.update()

    def _on_location_changed(self, _i):
        self._refresh_strings()
        self.update()

    def _refresh_strings(self):
        loc = self.app_state.active.location
        now = datetime.datetime.now()
        self._cached_for_day = now.date()
        self._cached_for_location = self.app_state.active_index

        # Date string: "Saturday June 27 2026"
        self._date_str = "{:%A %B %-d %Y}".format(now) if hasattr(now, "__format__") else now.strftime("%A %B %d %Y")
        # On Windows / for safety, use strftime that works everywhere:
        self._date_str = now.strftime("%A, %B %d, %Y")

        # Sun/moon string for active location.
        # Use a tz-aware datetime so the sunrise calc uses the right offset.
        # We approximate by assuming Pi local TZ; with multi-location this means
        # the sun rise/set is shown in Pi local time, not target-location local
        # time. That's an explicit simplification for now.
        try:
            import tzlocal
            tz = tzlocal.get_localzone()
            now_aware = datetime.datetime.now(tz=tz)
        except Exception:
            now_aware = datetime.datetime.now()

        try:
            sun = suntimes(loc.lat, loc.lng)
            rise = sun.sunrise(now_aware)
            sset = sun.sunset(now_aware)
            sun_part = "↑ {:%H:%M}   ↓ {:%H:%M}".format(rise, sset)
        except Exception as e:
            print("clock_face: sun calc failed:", e)
            sun_part = "↑ --:--   ↓ --:--"

        try:
            mp = moon_phase(now)
            moon_part = "☾ " + moon_phase_name(mp)
        except Exception:
            moon_part = "☾ —"

        self._sunmoon_str = "{}     {}".format(sun_part, moon_part)

    def paintEvent(self, _evt):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.setRenderHint(QPainter.Antialiasing)

            # Square area centered in the widget.
            side = min(self.width(), self.height())
            x0 = (self.width() - side) // 2
            y0 = (self.height() - side) // 2
            cx = x0 + side / 2.0
            cy = y0 + side / 2.0

            # 1+2+3. Static layer (face + date arc + sun/moon arc), cached.
            self._ensure_bg(side)
            if not self._bg_pix.isNull():
                p.drawPixmap(int(x0), int(y0), self._bg_pix)

            # 4. Hands. Sized so the hand image's height becomes the diameter,
            # scaled once per dial size and cached.
            self._ensure_hands(side)
            now = datetime.datetime.now()
            self._draw_hand(p, self._hour_scaled, cx, cy,
                            ((now.hour % 12) + now.minute / 60.0) * 30.0)
            self._draw_hand(p, self._min_scaled, cx, cy, now.minute * 6.0)
            self._draw_hand(p, self._sec_scaled, cx, cy, now.second * 6.0)
        finally:
            p.end()

    def _ensure_bg(self, side):
        """(Re)build the cached face + arc-text layer when size/strings change."""
        if side <= 0:
            return
        strings = (self._date_str, self._sunmoon_str)
        if side == self._bg_side and strings == self._bg_strings:
            return
        self._bg_side = side
        self._bg_strings = strings

        pix = QPixmap(side, side)
        pix.fill(Qt.transparent)
        bp = QPainter(pix)
        try:
            bp.setRenderHint(QPainter.SmoothPixmapTransform)
            bp.setRenderHint(QPainter.Antialiasing)
            bp.setRenderHint(QPainter.TextAntialiasing)

            # Face fills the layer.
            if not self.face_pix.isNull():
                scaled = self.face_pix.scaled(
                    int(side), int(side),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                bp.drawPixmap(0, 0, scaled)
            else:
                bp.setBrush(QBrush(QColor("#101820")))
                bp.setPen(QPen(QColor("#50CBEB"), 4))
                bp.drawEllipse(QRectF(0, 0, side, side))

            c = side / 2.0
            r = side / 2.0
            # Date arc (top inside), pulled to ~0.60r to clear the hour markers.
            self._draw_arc_text(
                bp, c, c, r * 0.60, self._date_str,
                center_angle_deg=-90,
                font_pt=max(14, int(side * 0.035)),
                color=QColor("#bef"),
                facing_outward=False, arc_above_center=True,
            )
            # Sun/moon arc (bottom inside).
            self._draw_arc_text(
                bp, c, c, r * 0.60, self._sunmoon_str,
                center_angle_deg=90,
                font_pt=max(12, int(side * 0.028)),
                color=QColor("#bef"),
                facing_outward=False, arc_above_center=False,
            )
        finally:
            bp.end()
        self._bg_pix = pix

    def _ensure_hands(self, side):
        """(Re)scale the three hand pixmaps when the dial size changes."""
        if side == self._hands_side or side <= 0:
            return
        self._hands_side = side
        self._hour_scaled = self._scale_hand(self.hour_pix, side)
        self._min_scaled = self._scale_hand(self.min_pix, side)
        self._sec_scaled = self._scale_hand(self.sec_pix, side)

    @staticmethod
    def _scale_hand(pix, side):
        if pix.isNull():
            return QPixmap()
        scale = side / float(pix.height())
        sw = int(pix.width() * scale)
        sh = int(pix.height() * scale)
        return pix.scaled(sw, sh, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _draw_hand(self, p, scaled, cx, cy, angle_deg):
        if scaled.isNull():
            return
        p.save()
        p.translate(cx, cy)
        p.rotate(angle_deg)
        p.drawPixmap(-scaled.width() // 2, -scaled.height() // 2, scaled)
        p.restore()

    def _draw_arc_text(self, p, cx, cy, radius, text, center_angle_deg,
                       font_pt, color, facing_outward, arc_above_center):
        """
        Render `text` along a circle of radius `radius` around (cx, cy),
        centered at angle `center_angle_deg` (0 = right, 90 = down,
        -90 = up in Qt screen coords).

        arc_above_center: if True, text follows the top arc curvature
        (concave side up). If False, follows the bottom arc (concave side down).
        """
        if not text:
            return

        font = QFont()
        font.setPointSize(font_pt)
        font.setBold(True)
        fm = QFontMetricsF(font)
        total_w = fm.horizontalAdvance(text)

        # Convert linear width to angular span.
        # arc_length = radius * theta_radians  =>  theta = w/r
        total_theta = total_w / radius
        # Start angle so text is centered at center_angle_deg.
        # For text following the top arc (arc_above_center=True), each glyph's
        # baseline tangent angle is (theta - 90). For the bottom arc, it's
        # (theta + 90) and we draw chars in reverse so they read L→R.
        p.save()
        p.setFont(font)
        p.setPen(QPen(color))
        p.translate(cx, cy)

        if arc_above_center:
            # Walk left-to-right along the top arc.
            start = math.radians(center_angle_deg) - total_theta / 2.0
            x = 0.0
            for ch in text:
                w = fm.horizontalAdvance(ch)
                dtheta = w / radius
                theta = start + x / radius + dtheta / 2.0
                p.save()
                # Translate to char center on the circle.
                gx = radius * math.cos(theta)
                gy = radius * math.sin(theta)
                p.translate(gx, gy)
                # Rotate so glyph baseline is tangent to circle, upright.
                p.rotate(math.degrees(theta) + 90.0)
                gp = QPointF(-w / 2.0, fm.ascent() / 2.0)
                p.setPen(QColor(0, 0, 0, 180))
                p.drawText(QPointF(gp.x() + 1.5, gp.y() + 1.5), ch)
                p.setPen(color)
                p.drawText(gp, ch)
                p.restore()
                x += w
        else:
            # Bottom arc: text reads L→R, but glyph rotation is flipped.
            start = math.radians(center_angle_deg) + total_theta / 2.0
            x = 0.0
            for ch in text:
                w = fm.horizontalAdvance(ch)
                dtheta = w / radius
                theta = start - x / radius - dtheta / 2.0
                p.save()
                gx = radius * math.cos(theta)
                gy = radius * math.sin(theta)
                p.translate(gx, gy)
                p.rotate(math.degrees(theta) - 90.0)
                gp = QPointF(-w / 2.0, fm.ascent() / 2.0)
                p.setPen(QColor(0, 0, 0, 180))
                p.drawText(QPointF(gp.x() + 1.5, gp.y() + 1.5), ch)
                p.setPen(color)
                p.drawText(gp, ch)
                p.restore()
                x += w

        p.restore()
