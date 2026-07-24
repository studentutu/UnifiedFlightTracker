#pragma once

#include <QElapsedTimer>
#include <QHash>
#include <QTimer>
#include <QWidget>

#include "Flight.h"

class PolarSkyView : public QWidget {
    Q_OBJECT
public:
    explicit PolarSkyView(QWidget *parent = nullptr);

    void setFlights(const QList<Flight> &flights);
    void selectHex(const QString &hex);
    QString selectedHex() const { return m_selected; }

signals:
    void aircraftPicked(const QString &hex);

protected:
    void paintEvent(QPaintEvent *) override;
    void mousePressEvent(QMouseEvent *) override;
    void mouseMoveEvent(QMouseEvent *) override;

private:
    struct Track {
        Flight f;
        qint64 lastSeenMs;
    };
    QHash<QString, Track> m_tracks;
    QTimer  m_anim;
    QElapsedTimer m_clock;
    QString m_hover;
    QString m_selected;

    QPointF project(double azDeg, double elDeg,
                    QPointF center, double rHorizon, double rOuter) const;
    QString nearestHex(const QPointF &pos, double threshold = 12.0) const;
};
