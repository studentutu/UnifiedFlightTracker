#pragma once

#include <QElapsedTimer>
#include <QHash>
#include <QList>
#include <QTimer>
#include <QWidget>

#include "Flight.h"

class AltitudeStripChart : public QWidget {
    Q_OBJECT
public:
    explicit AltitudeStripChart(QWidget *parent = nullptr);

    void updateFromSnapshot(const QList<Flight> &flights);
    void setSelected(const QString &hex, const QString &label);

protected:
    void paintEvent(QPaintEvent *) override;

private:
    struct Sample { double t; double alt; };
    struct Envelope { double t; double lo; double hi; };

    // seconds-since-boot key so we avoid wall-clock jumps.
    QHash<QString, QList<Sample>> m_series;
    QList<Envelope> m_envelope;
    QString m_selected;
    QString m_label = "no aircraft selected";
    QElapsedTimer m_clock;
    QTimer m_anim;

    static constexpr double kHistoryS = 300.0;
    static constexpr int    kMaxSamples = 600;

    std::pair<double,double> yRange() const;
    QPointF toPoint(double t, double y, const QRectF &plot,
                    double now, double ymin, double ymax) const;
};
