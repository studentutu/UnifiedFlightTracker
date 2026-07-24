#include "AltitudeStripChart.h"

#include <QPainter>
#include <QPolygonF>
#include <algorithm>
#include <cmath>

AltitudeStripChart::AltitudeStripChart(QWidget *parent) : QWidget(parent) {
    setMinimumHeight(140);
    setAutoFillBackground(true);
    m_clock.start();
    m_anim.setInterval(200);
    connect(&m_anim, &QTimer::timeout, this, QOverload<>::of(&QWidget::update));
    m_anim.start();
}

void AltitudeStripChart::updateFromSnapshot(const QList<Flight> &flights) {
    const double now = m_clock.elapsed() / 1000.0;
    double lo = std::numeric_limits<double>::infinity();
    double hi = -std::numeric_limits<double>::infinity();
    bool any = false;
    for (const Flight &f : flights) {
        if (f.hexId.isEmpty()) continue;
        auto &q = m_series[f.hexId];
        q.push_back({ now, f.altitudeFt });
        if (q.size() > kMaxSamples) q.removeFirst();
        lo = std::min(lo, f.altitudeFt);
        hi = std::max(hi, f.altitudeFt);
        any = true;
    }
    if (any) {
        m_envelope.push_back({ now, lo, hi });
        if (m_envelope.size() > kMaxSamples) m_envelope.removeFirst();
    }
    const double cutoff = now - kHistoryS;
    for (auto it = m_series.begin(); it != m_series.end(); ) {
        auto &q = it.value();
        while (!q.isEmpty() && q.first().t < cutoff) q.removeFirst();
        if (q.isEmpty()) it = m_series.erase(it);
        else ++it;
    }
    while (!m_envelope.isEmpty() && m_envelope.first().t < cutoff)
        m_envelope.removeFirst();
}

void AltitudeStripChart::setSelected(const QString &hex, const QString &label) {
    m_selected = hex;
    m_label = label.isEmpty() ? (hex.isEmpty() ? "no aircraft selected" : hex) : label;
    update();
}

std::pair<double,double> AltitudeStripChart::yRange() const {
    QList<double> vals;
    if (!m_selected.isEmpty() && m_series.contains(m_selected)) {
        for (const auto &s : m_series[m_selected]) vals.push_back(s.alt);
    }
    for (const auto &e : m_envelope) { vals.push_back(e.lo); vals.push_back(e.hi); }
    if (vals.isEmpty()) return {0.0, 45000.0};
    double lo = *std::min_element(vals.begin(), vals.end());
    double hi = *std::max_element(vals.begin(), vals.end());
    if (hi - lo < 2000) { double mid = (hi+lo)/2; lo = mid-1000; hi = mid+1000; }
    lo = std::max(0.0, std::floor(lo/5000.0)*5000.0);
    hi = (std::floor(hi/5000.0)+1.0)*5000.0;
    return {lo, hi};
}

QPointF AltitudeStripChart::toPoint(double t, double y, const QRectF &plot,
                                    double now, double ymin, double ymax) const {
    const double x  = plot.left() + plot.width() * (1.0 - (now - t) / kHistoryS);
    const double yy = plot.bottom() - (y - ymin) / std::max(1.0, ymax - ymin) * plot.height();
    return {x, yy};
}

void AltitudeStripChart::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing, true);
    p.fillRect(rect(), QColor("#0d1620"));

    const int mL = 46, mR = 12, mT = 20, mB = 22;
    const QRectF plot(mL, mT, width()-mL-mR, height()-mT-mB);
    const double now = m_clock.elapsed() / 1000.0;
    auto [ymin, ymax] = yRange();

    // Axes.
    p.setPen(QPen(QColor(255,255,255,60)));
    p.setBrush(Qt::NoBrush);
    p.drawRect(plot);

    QFont f = p.font(); f.setPointSize(8); p.setFont(f);
    p.setPen(QColor(150,165,180));
    for (double frac : {0.0, 0.25, 0.5, 0.75, 1.0}) {
        const double y = plot.bottom() - frac * plot.height();
        const double val = ymin + frac * (ymax - ymin);
        p.setPen(QPen(QColor(255,255,255,20)));
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y));
        p.setPen(QColor(150,165,180));
        p.drawText(QRectF(0, y-8, mL-4, 16),
                   Qt::AlignRight | Qt::AlignVCenter,
                   QString::asprintf("%5d", int(val)));
    }
    for (int back : {0, 60, 120, 180, 240, 300}) {
        const double frac = 1.0 - back / kHistoryS;
        const double x = plot.left() + frac * plot.width();
        p.setPen(QPen(QColor(255,255,255,20)));
        p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()));
        p.setPen(QColor(150,165,180));
        QString lbl = (back == 0) ? "now" : QString("-%1s").arg(back);
        p.drawText(QRectF(x-22, plot.bottom()+2, 44, 14), Qt::AlignCenter, lbl);
    }

    // Envelope band.
    if (m_envelope.size() >= 2) {
        QPolygonF band;
        for (const auto &e : m_envelope) band << toPoint(e.t, e.hi, plot, now, ymin, ymax);
        for (int i = m_envelope.size()-1; i >= 0; --i)
            band << toPoint(m_envelope[i].t, m_envelope[i].lo, plot, now, ymin, ymax);
        p.setPen(Qt::NoPen);
        p.setBrush(QColor(90,130,170,45));
        p.drawPolygon(band);

        QPolygonF top, bot;
        for (const auto &e : m_envelope) {
            top << toPoint(e.t, e.hi, plot, now, ymin, ymax);
            bot << toPoint(e.t, e.lo, plot, now, ymin, ymax);
        }
        p.setPen(QPen(QColor(90,130,170,110), 1.0));
        p.setBrush(Qt::NoBrush);
        p.drawPolyline(top);
        p.drawPolyline(bot);
    }

    // Selected trace.
    if (!m_selected.isEmpty() && m_series.contains(m_selected)) {
        const auto &q = m_series[m_selected];
        if (q.size() >= 2) {
            QPolygonF poly;
            for (const auto &s : q) poly << toPoint(s.t, s.alt, plot, now, ymin, ymax);
            p.setPen(QPen(QColor("#00e5ff"), 2.0));
            p.setBrush(Qt::NoBrush);
            p.drawPolyline(poly);
            const auto &last = q.back();
            const QPointF pt = toPoint(last.t, last.alt, plot, now, ymin, ymax);
            p.setBrush(QColor("#00e5ff"));
            p.setPen(Qt::NoPen);
            p.drawEllipse(pt, 3.5, 3.5);
        }
    }

    // Title.
    QFont tf = p.font(); tf.setBold(true); p.setFont(tf);
    p.setPen(QColor(220,230,240));
    p.drawText(QRectF(mL, 0, plot.width(), mT),
               Qt::AlignLeft | Qt::AlignVCenter,
               QString("Altitude (ft) — %1").arg(m_label));
}
