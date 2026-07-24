#pragma once

#include <QString>
#include <QMetaType>

struct Flight {
    QString hexId;
    QString callsign;
    QString type;
    QString source;
    double  lat        = 0.0;
    double  lon        = 0.0;
    double  altitudeFt = 0.0;
    double  speedKt    = 0.0;
    double  headingDeg = 0.0;
    double  distanceNm = 0.0;
    double  azimuthDeg = 0.0;
    double  elevationDeg = 0.0;
};

Q_DECLARE_METATYPE(Flight)
Q_DECLARE_METATYPE(QList<Flight>)
