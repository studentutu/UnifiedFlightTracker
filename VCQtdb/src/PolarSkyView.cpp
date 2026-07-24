#include "PolarSkyView.h"

#include <QMouseEvent>
#include <QPaintEvent>
#include <QPainter>
#include <QRadialGradient>
#include <cmath>

namespace {
struct Band { double minAlt; QColor color; };
const QList<Band> kAltBands = {
    {     0.0, QColor("#f5b642") },   // <2 kft
    {  2000.0, QColor("#4caf50") },
    { 10000.0, QColor("#00bcd4") },
    { 25000.0, QColor("#2196f3") },
    { 40000.0, QColor("#e040fb") },
};
QColor colorForAlt(double ft) {
    for (int i = kAltBands.size() - 1; i >= 0; --i)
        if (ft >= kAltBands[i].minAlt) return kAltBands[i].color;
    return kAltBands.front().color;
}
} // namespace

PolarSkyView::PolarSkyView(QWidget *parent) : QWidget(parent) {
    setMinimumSize(360, 360);
    setMouseTracking(true);
    setAutoFillBackground(true);
    m_clock.start();
    m_anim.setInterval(33);
    connect(&m_anim, &QTimer::timeout, this, QOverload<>::of(&QWidget::update));
    m_anim.start();
}

void PolarSkyView::setFlights(const QList<Flight> &flights) {
    const qint64 now = m_clock.elapsed();
    QSet<QString> seen;
    for (const Flight &f : flights) {
        QString id = f.hexId.isEmpty() ? f.callsign : f.hexId;
        if (id.isEmpty()) continue;
        seen.insert(id);
        m_tracks[id] = Track{ f, now };
    }
    // Drop tracks older than 120 s.
    for (auto it = m_tracks.begin(); it != m_tracks.end(); ) {
        if (now - it.value().lastSeenMs > 120'000) it = m_tracks.erase(it);
        else ++it;
    }
}

void PolarSkyView::selectHex(const QString &hex) {
    m_selected = hex;
    update();
}

QPointF PolarSkyView::project(double azDeg, double elDeg,
                              QPointF center, double rHorizon, double rOuter) const {
    double r;
    if (elDeg >= 0) {
        r = rHorizon * (1.0 - std::min(elDeg, 90.0) / 90.0);
    } else {
        r = rHorizon + (rOuter - rHorizon) * std::min(std::abs(elDeg) / 30.0, 1.0);
    }
    const double theta = (azDeg - 90.0) * M_PI / 180.0;
    return { center.x() + r * std::cos(theta),
             center.y() + r * std::sin(theta) };
}

void PolarSkyView::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing, true);

    const double side = std::min(width(), height()) - 20.0;
    const QPointF center(width()/2.0, height()/2.0);
    const double rHorizon = side/2.0 * 0.85;
    const double rOuter   = side/2.0;

    // Background gradient.
    QRadialGradient grad(center, rOuter);
    grad.setColorAt(0.0, QColor("#0f1a24"));
    grad.setColorAt(1.0, QColor("#050a10"));
    p.fillRect(rect(), grad);

    // Below-horizon band + sky disk.
    p.setPen(Qt::NoPen);
    p.setBrush(QColor(20, 24, 30, 180));
    p.drawEllipse(center, rOuter, rOuter);
    p.setBrush(QColor(18, 30, 44));
    p.drawEllipse(center, rHorizon, rHorizon);

    // Rings at 0/30/60 elevation.
    p.setBrush(Qt::NoBrush);
    p.setPen(QPen(QColor(255,255,255,45), 1.0));
    for (int el : {0, 30, 60}) {
        const double r = rHorizon * (1.0 - el/90.0);
        p.drawEllipse(center, r, r);
    }
    // Zenith dot.
    p.setBrush(QColor(255,255,255,90));
    p.setPen(Qt::NoPen);
    p.drawEllipse(center, 2.0, 2.0);

    // Radial spokes.
    p.setPen(QPen(QColor(255,255,255,60), 1.0));
    for (int az = 0; az < 360; az += 30) {
        p.drawLine(center, project(az, 0, center, rHorizon, rOuter));
    }
    // Cardinals.
    p.setPen(QPen(QColor(255,255,255,220)));
    QFont f = p.font(); f.setBold(true); p.setFont(f);
    struct Card { int az; const char *l; };
    for (const auto &c : { Card{0,"N"}, Card{90,"E"}, Card{180,"S"}, Card{270,"W"} }) {
        const QPointF pt = project(c.az, -5, center, rHorizon, rOuter);
        p.drawText(QRectF(pt.x()-12, pt.y()-10, 24, 20), Qt::AlignCenter, c.l);
    }

    // Aircraft.
    const qint64 now = m_clock.elapsed();
    for (auto it = m_tracks.constBegin(); it != m_tracks.constEnd(); ++it) {
        const Flight &fl = it->f;
        const QPointF pt = project(fl.azimuthDeg, fl.elevationDeg, center, rHorizon, rOuter);
        QColor color = colorForAlt(fl.altitudeFt);

        const double ageMs = double(now - it->lastSeenMs);
        const double halo  = std::max(0.0, 1.0 - ageMs / 3000.0);
        if (halo > 0) {
            QColor h = color; h.setAlphaF(0.30 * halo);
            p.setPen(Qt::NoPen);
            p.setBrush(h);
            const double r = 10.0 + 6.0 * halo;
            p.drawEllipse(pt, r, r);
        }

        QColor body = color;
        if (fl.elevationDeg < 0) body.setAlphaF(0.55);
        p.setBrush(body);
        p.setPen(QPen(QColor(255,255,255,200), 1.2));
        const double bodyR = (it.key() == m_selected) ? 6.5 : 5.0;
        p.drawEllipse(pt, bodyR, bodyR);

        if (fl.elevationDeg >= 0 || it.key() == m_selected || it.key() == m_hover) {
            p.setPen(QColor(255,255,255,220));
            p.drawText(QRectF(pt.x()+8, pt.y()-8, 100, 14), Qt::AlignLeft, fl.callsign);
        }
    }

    // Legend.
    const int lh = 14;
    const int pad = 8;
    const int lw = 130;
    const int rows = kAltBands.size();
    const int lheight = 6 + rows * lh + 8;
    QRectF legend(pad, height() - lheight - pad, lw, lheight);
    p.setBrush(QColor(0,0,0,140));
    p.setPen(QPen(QColor(255,255,255,60)));
    p.drawRoundedRect(legend, 5, 5);
    p.setPen(QColor(210,220,230));
    QFont lfont = p.font(); lfont.setBold(false); lfont.setPointSize(8); p.setFont(lfont);
    double y = legend.top() + 12;
    for (const Band &b : kAltBands) {
        p.setPen(Qt::NoPen);
        p.setBrush(b.color);
        p.drawEllipse(QPointF(legend.left() + 12, y - 3), 4, 4);
        p.setPen(QColor(210,220,230));
        QString label = b.minAlt == 0 ? "< 2 kft"
                                      : QString("≥ %1 kft").arg(int(b.minAlt/1000));
        p.drawText(QRectF(legend.left() + 22, y - 9, lw - 24, 14),
                   Qt::AlignLeft, label);
        y += lh;
    }
}

QString PolarSkyView::nearestHex(const QPointF &pos, double threshold) const {
    const double side = std::min(width(), height()) - 20.0;
    const QPointF center(width()/2.0, height()/2.0);
    const double rHorizon = side/2.0 * 0.85;
    const double rOuter   = side/2.0;

    QString best;
    double bestD = threshold;
    for (auto it = m_tracks.constBegin(); it != m_tracks.constEnd(); ++it) {
        const QPointF pt = project(it->f.azimuthDeg, it->f.elevationDeg, center, rHorizon, rOuter);
        const double d = std::hypot(pt.x() - pos.x(), pt.y() - pos.y());
        if (d < bestD) { bestD = d; best = it.key(); }
    }
    return best;
}

void PolarSkyView::mouseMoveEvent(QMouseEvent *ev) {
    m_hover = nearestHex(ev->position());
}

void PolarSkyView::mousePressEvent(QMouseEvent *ev) {
    QString id = nearestHex(ev->position());
    if (!id.isEmpty()) {
        m_selected = id;
        emit aircraftPicked(id);
    }
}
