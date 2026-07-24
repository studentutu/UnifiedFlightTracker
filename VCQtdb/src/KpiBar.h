#pragma once

#include <QFrame>
#include <QLabel>
#include <QTimer>
#include <QWidget>

#include "Flight.h"

class StatusLED : public QWidget {
    Q_OBJECT
public:
    enum State { Unknown, Ok, Warn, Err };
    explicit StatusLED(QWidget *parent = nullptr);
    void setState(State s);
protected:
    void paintEvent(QPaintEvent *) override;
private:
    State m_state = Unknown;
    double m_pulse = 0.0;
    QTimer m_timer;
};

class KpiTile : public QFrame {
    Q_OBJECT
public:
    explicit KpiTile(const QString &title, QWidget *parent = nullptr);
    void setValue(const QString &val, const QString &sub = {});
private:
    QLabel *m_value;
    QLabel *m_sub;
};

class KpiBar : public QWidget {
    Q_OBJECT
public:
    explicit KpiBar(QWidget *parent = nullptr);
    void setOk(double elapsedMs, const QStringList &messages);
    void setError(const QString &msg);
    void setFlights(const QList<Flight> &flights);
private:
    StatusLED *m_led;
    QLabel    *m_statusText;
    KpiTile   *m_count;
    KpiTile   *m_closest;
    KpiTile   *m_highest;
    KpiTile   *m_latency;
};
