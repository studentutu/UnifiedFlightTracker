#include "KpiBar.h"

#include <QFont>
#include <QHBoxLayout>
#include <QPainter>
#include <QSizePolicy>
#include <QVBoxLayout>
#include <algorithm>

// --- StatusLED ------------------------------------------------------------
StatusLED::StatusLED(QWidget *parent) : QWidget(parent) {
    setFixedSize(14, 14);
    m_timer.setInterval(60);
    connect(&m_timer, &QTimer::timeout, this, [this]{
        if (m_pulse > 0) { m_pulse = std::max(0.0, m_pulse - 0.05); update(); }
    });
    m_timer.start();
}
void StatusLED::setState(State s) { m_state = s; m_pulse = 1.0; update(); }

void StatusLED::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing, true);
    QColor c;
    switch (m_state) {
        case Ok:    c = QColor("#5cd865"); break;
        case Warn:  c = QColor("#f5b642"); break;
        case Err:   c = QColor("#e57373"); break;
        default:    c = QColor("#7c8792"); break;
    }
    if (m_pulse > 0) {
        QColor h = c; h.setAlphaF(0.35 * m_pulse);
        p.setBrush(h);
        p.setPen(Qt::NoPen);
        const int r = 7 + int(4 * m_pulse);
        p.drawEllipse(rect().center(), r, r);
    }
    p.setBrush(c);
    p.setPen(Qt::NoPen);
    p.drawEllipse(rect().center(), 5, 5);
}

// --- KpiTile --------------------------------------------------------------
KpiTile::KpiTile(const QString &title, QWidget *parent) : QFrame(parent) {
    setFrameShape(QFrame::StyledPanel);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    setStyleSheet("QFrame { background:#152030; border:1px solid #23324a; border-radius:6px; }");

    auto *t = new QLabel(title.toUpper(), this);
    t->setStyleSheet("color:#7c8ea3; font-size:9pt; letter-spacing:1px;");

    m_value = new QLabel("—", this);
    QFont f; f.setPointSize(16); f.setBold(true);
    m_value->setFont(f);
    m_value->setStyleSheet("color:#e8f0f8;");

    m_sub = new QLabel("", this);
    m_sub->setStyleSheet("color:#9fb0c2; font-size:8pt;");

    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(10, 6, 10, 8);
    lay->setSpacing(0);
    lay->addWidget(t);
    lay->addWidget(m_value);
    lay->addWidget(m_sub);
}
void KpiTile::setValue(const QString &v, const QString &s) {
    m_value->setText(v);
    m_sub->setText(s);
}

// --- KpiBar ---------------------------------------------------------------
KpiBar::KpiBar(QWidget *parent) : QWidget(parent) {
    m_led = new StatusLED(this);
    m_statusText = new QLabel("waiting for backend…", this);
    m_statusText->setStyleSheet("color:#c7d2df;");

    m_count   = new KpiTile("Aircraft in range");
    m_closest = new KpiTile("Closest");
    m_highest = new KpiTile("Highest");
    m_latency = new KpiTile("Backend latency");

    auto *top = new QHBoxLayout();
    top->setContentsMargins(0,0,0,0);
    top->setSpacing(6);
    top->addWidget(m_led);
    top->addWidget(m_statusText, 1);

    auto *tiles = new QHBoxLayout();
    tiles->setContentsMargins(0,0,0,0);
    tiles->setSpacing(8);
    tiles->addWidget(m_count);
    tiles->addWidget(m_closest);
    tiles->addWidget(m_highest);
    tiles->addWidget(m_latency);

    auto *lay = new QVBoxLayout(this);
    lay->setContentsMargins(8,8,8,4);
    lay->setSpacing(6);
    lay->addLayout(top);
    lay->addLayout(tiles);
}

void KpiBar::setOk(double elapsedMs, const QStringList &messages) {
    if (!messages.isEmpty()) {
        m_led->setState(StatusLED::Warn);
        m_statusText->setText("connected — " + messages.join("; "));
    } else {
        m_led->setState(StatusLED::Ok);
        m_statusText->setText(QString("connected — updated in %1 ms")
                              .arg(int(elapsedMs)));
    }
    m_latency->setValue(QString("%1 ms").arg(int(elapsedMs)), "round-trip to backend");
}

void KpiBar::setError(const QString &msg) {
    m_led->setState(StatusLED::Err);
    m_statusText->setText("backend error — " + msg);
}

void KpiBar::setFlights(const QList<Flight> &flights) {
    m_count->setValue(QString::number(flights.size()), "current poll");
    if (flights.isEmpty()) {
        m_closest->setValue("—");
        m_highest->setValue("—");
        return;
    }
    const Flight *closest = &flights.first();
    const Flight *highest = &flights.first();
    for (const Flight &f : flights) {
        if (f.distanceNm < closest->distanceNm) closest = &f;
        if (f.altitudeFt > highest->altitudeFt) highest = &f;
    }
    m_closest->setValue(
        QString::number(closest->distanceNm, 'f', 1) + " nm",
        QString("%1 · el %2°")
            .arg(closest->callsign.isEmpty() ? QStringLiteral("?") : closest->callsign)
            .arg(int(closest->elevationDeg))
    );
    m_highest->setValue(
        QString::number(qint64(highest->altitudeFt)) + " ft",
        QString("%1 · %2 kt")
            .arg(highest->callsign.isEmpty() ? QStringLiteral("?") : highest->callsign)
            .arg(int(highest->speedKt))
    );
}
